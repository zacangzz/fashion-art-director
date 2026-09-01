from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from google.cloud.firestore import Client, Increment
from app.utils.logger import get_logger

logger = get_logger("database")

ALLOWED_COLLECTIONS = [
    "users",
    "generations",
    "moodboards",
    "conversations",
    "background_references",
    "wardrobe_items",
    "composition_assignments",
    "telemetry_events",
    "usage_daily",
]


class FirestoreManager:
    """
    Unified synchronous Firestore Native database manager.
    Enforces multi-tenancy with user_id, native maps/arrays,
    pre-computed lineage costs, and zero circular dependencies.
    """
    def __init__(self, db: Client):
        self.db = db

    @property
    def client(self) -> Client:
        """Compatibility property to access underlying Firestore Client."""
        return self.db

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _to_firestore_safe(obj: Any) -> Any:
        """Recursively convert Pydantic models and other non-native types to Firestore-safe primitives."""
        if hasattr(obj, "model_dump"):
            return FirestoreManager._to_firestore_safe(obj.model_dump())
        if hasattr(obj, "dict") and not isinstance(obj, dict):
            return FirestoreManager._to_firestore_safe(obj.dict())
        if isinstance(obj, dict):
            return {k: FirestoreManager._to_firestore_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [FirestoreManager._to_firestore_safe(item) for item in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        # Fallback: try converting to string
        return str(obj)

    # -------------------------------------------------------------------------
    # 1. MOODBOARDS
    # -------------------------------------------------------------------------
    def create_moodboard(self, user_id: str, moodboard_id: str, image_paths: List[str]) -> Dict[str, Any]:
        logger.info(f"Creating moodboard record {moodboard_id} for user {user_id} with {len(image_paths)} images")
        doc_ref = self.db.collection("moodboards").document(moodboard_id)
        data = {
            "id": moodboard_id,
            "user_id": user_id,
            "image_paths": image_paths,
            "cost_usd": 0.0,
            "tokens": 0,
            "accumulated_cost_usd": 0.0,
            "accumulated_tokens": 0,
            "created_at": self._now_iso(),
        }
        doc_ref.set(data)
        return data

    def add_moodboard_cost(self, moodboard_id: str, cost_usd: float, tokens: int = 0) -> None:
        doc_ref = self.db.collection("moodboards").document(moodboard_id)
        doc_ref.update({
            "cost_usd": Increment(cost_usd),
            "tokens": Increment(tokens),
            "accumulated_cost_usd": Increment(cost_usd),
            "accumulated_tokens": Increment(tokens),
        })

    def get_moodboard(self, moodboard_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("moodboards").document(moodboard_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    # -------------------------------------------------------------------------
    # 2. GENERATIONS & LINEAGE
    # -------------------------------------------------------------------------
    def _normalize_generation_doc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        schema = data.get("schema_json") or data.get("tags_snapshot") or {}
        if isinstance(schema, str):
            import json
            try:
                schema = json.loads(schema)
            except Exception:
                schema = {}
        data["schema_json"] = schema

        if isinstance(schema, dict):
            inpaint_meta = schema.get("inpaint_metadata")
            if inpaint_meta and isinstance(inpaint_meta, dict):
                data["inpaint_metadata"] = inpaint_meta
                if "mask_url" in inpaint_meta:
                    data["mask_image_url"] = inpaint_meta["mask_url"]

        if not data.get("compiled_prompt"):
            data["compiled_prompt"] = data.get("prompt", "")
        data["prompt"] = data["compiled_prompt"]

        if not data.get("model_name") and isinstance(schema, dict):
            data["model_name"] = schema.get("imagen_model") or schema.get("model_name")

        data["cost_usd"] = float(data.get("cost_usd") or 0.0)
        data["tokens"] = int(data.get("tokens") or 0)
        data["accumulated_cost_usd"] = float(data.get("accumulated_cost_usd") or 0.0)
        data["accumulated_tokens"] = int(data.get("accumulated_tokens") or 0)
        data["is_baseline"] = bool(data.get("is_baseline", False))
        if data.get("background_reference_id"):
            data["background_reference_id"] = str(data["background_reference_id"])
            if not data.get("background_reference_url"):
                bg_ref = self.get_background_reference(data["background_reference_id"])
                if bg_ref:
                    data["background_reference_url"] = bg_ref.get("image_url")
        if data.get("background_harmonization_meta"):
            data["background_harmonization_meta"] = data["background_harmonization_meta"]
        return data

    def create_generation(self, user_id: str, gen_data: Dict[str, Any]) -> Dict[str, Any]:
        gen_id = gen_data["id"]
        parent_id = gen_data.get("parent_id")
        cost_usd = float(gen_data.get("cost_usd") or 0.0)
        tokens = int(gen_data.get("tokens") or 0)

        # Pre-compute lineage accumulation from parent if not already set
        if "accumulated_cost_usd" in gen_data:
            accum_cost = float(gen_data["accumulated_cost_usd"])
            accum_tokens = int(gen_data.get("accumulated_tokens", tokens))
        else:
            accum_cost = cost_usd
            accum_tokens = tokens
            if parent_id:
                parent = self.get_generation(parent_id)
                if parent:
                    accum_cost += float(parent.get("accumulated_cost_usd") or parent.get("cost_usd", 0.0))
                    accum_tokens += int(parent.get("accumulated_tokens") or parent.get("tokens", 0))

        schema_val = gen_data.get("schema_json") or gen_data.get("tags_snapshot") or {}
        schema_val = self._to_firestore_safe(schema_val)

        compiled_prompt = gen_data.get("compiled_prompt") or gen_data.get("prompt", "")
        model_name = gen_data.get("model_name")
        if not model_name and isinstance(schema_val, dict):
            model_name = schema_val.get("imagen_model") or schema_val.get("model_name")

        bg_ref_id = gen_data.get("background_reference_id")
        bg_meta = gen_data.get("background_harmonization_meta")
        if bg_meta is not None:
            bg_meta = self._to_firestore_safe(bg_meta)

        doc_data = {
            "id": gen_id,
            "user_id": user_id,
            "parent_id": parent_id,
            "moodboard_id": gen_data.get("moodboard_id"),
            "is_baseline": bool(gen_data.get("is_baseline", False)),
            "schema_json": schema_val,
            "compiled_prompt": compiled_prompt,
            "prompt": compiled_prompt,
            "negative_prompt": gen_data.get("negative_prompt", "") or "",
            "seed": int(gen_data.get("seed", 0)),
            "master_image_path": gen_data.get("master_image_path", ""),
            "aspect_ratio": gen_data.get("aspect_ratio", "2:3"),
            "resolution_width": int(gen_data.get("resolution_width", 3840)),
            "resolution_height": int(gen_data.get("resolution_height", 3840)),
            "conversation_id": gen_data.get("conversation_id"),
            "model_name": model_name,
            "background_reference_id": bg_ref_id,
            "background_harmonization_meta": bg_meta,
            "cost_usd": cost_usd,
            "tokens": tokens,
            "accumulated_cost_usd": round(accum_cost, 6),
            "accumulated_tokens": accum_tokens,
            "created_at": gen_data.get("created_at") or self._now_iso(),
        }

        logger.info(
            f"Creating generation {gen_id} for user {user_id} (is_baseline={doc_data['is_baseline']}, "
            f"cost=${cost_usd:.4f}, accum_cost=${accum_cost:.4f})"
        )
        self.db.collection("generations").document(gen_id).set(doc_data)
        return self._normalize_generation_doc(doc_data)

    def get_generation(self, generation_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("generations").document(generation_id).get()
        if doc.exists:
            return self._normalize_generation_doc(doc.to_dict())
        return None

    def list_generations(
        self,
        user_id: str,
        is_baseline: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = self.db.collection("generations").where("user_id", "==", user_id)
        if is_baseline is not None:
            query = query.where("is_baseline", "==", is_baseline)
        
        # Order by created_at desc
        query = query.order_by("created_at", direction="DESCENDING").limit(limit)
        docs = query.stream()
        return [self._normalize_generation_doc(d.to_dict()) for d in docs]

    def get_lineage(self, generation_id: str) -> Dict[str, Any]:
        """
        Traces ancestor chain up to the root baseline, and finds direct descendants.
        """
        target = self.get_generation(generation_id)
        if not target:
            return {"root_id": generation_id, "ancestors": [], "descendants": []}

        # 1. Traverse parent chain
        ancestors = []
        curr_parent_id = target.get("parent_id")
        while curr_parent_id:
            parent_doc = self.get_generation(curr_parent_id)
            if not parent_doc:
                break
            ancestors.append(parent_doc)
            curr_parent_id = parent_doc.get("parent_id")

        ancestors.reverse()  # chronological root -> parent
        root_id = ancestors[0]["id"] if ancestors else generation_id

        # 2. Find direct descendants
        descendant_docs = (
            self.db.collection("generations")
            .where("parent_id", "==", generation_id)
            .stream()
        )
        descendants = [self._normalize_generation_doc(d.to_dict()) for d in descendant_docs]

        return {
            "root_id": root_id,
            "ancestors": ancestors,
            "descendants": descendants,
        }

    # -------------------------------------------------------------------------
    # 3. CONVERSATIONS
    # -------------------------------------------------------------------------
    def create_conversation(
        self,
        user_id: str,
        conv_id: str,
        baseline_generation_id: str,
        moodboard_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Creating conversation {conv_id} for user {user_id}")
        data = {
            "id": conv_id,
            "user_id": user_id,
            "baseline_generation_id": baseline_generation_id,
            "moodboard_id": moodboard_id,
            "created_at": self._now_iso(),
        }
        self.db.collection("conversations").document(conv_id).set(data)
        return data

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("conversations").document(conv_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def list_conversation_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        docs = (
            self.db.collection("generations")
            .where("conversation_id", "==", conv_id)
            .order_by("created_at", direction="ASCENDING")
            .stream()
        )
        return [self._normalize_generation_doc(d.to_dict()) for d in docs]

    # -------------------------------------------------------------------------
    # 3.5 BACKGROUND REFERENCES
    # -------------------------------------------------------------------------
    def create_background_reference(self, user_id: str, bg_data: Dict[str, Any]) -> Dict[str, Any]:
        bg_id = bg_data["id"]
        doc_data = {
            "id": bg_id,
            "user_id": user_id,
            "original_filename": bg_data.get("original_filename", ""),
            "image_path": bg_data["image_path"],
            "thumbnail_path": bg_data.get("thumbnail_path"),
            "aspect_ratio": bg_data.get("aspect_ratio", "16:9"),
            "tags": bg_data.get("tags", []),
            "created_at": bg_data.get("created_at") or self._now_iso(),
            "deleted_at": None,
        }
        logger.info(f"Creating background reference {bg_id} for user {user_id}")
        self.db.collection("background_references").document(bg_id).set(doc_data)

        data = dict(doc_data)
        data["image_url"] = f"/api/images/{doc_data['image_path'].lstrip('/')}"
        if doc_data.get("thumbnail_path"):
            data["thumbnail_url"] = f"/api/images/{doc_data['thumbnail_path'].lstrip('/')}"
        else:
            data["thumbnail_url"] = data["image_url"]
        return data

    def get_background_reference(self, bg_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("background_references").document(bg_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("deleted_at") is not None:
                return None
            data["image_url"] = f"/api/images/{data['image_path'].lstrip('/')}"
            if data.get("thumbnail_path"):
                data["thumbnail_url"] = f"/api/images/{data['thumbnail_path'].lstrip('/')}"
            else:
                data["thumbnail_url"] = data["image_url"]
            return data
        return None

    def list_background_references(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            query = (
                self.db.collection("background_references")
                .where("user_id", "==", user_id)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
            )
            docs = list(query.stream())
        except Exception:
            # Fallback if compound index is pending
            query = (
                self.db.collection("background_references")
                .where("user_id", "==", user_id)
                .limit(limit)
            )
            docs = list(query.stream())

        results = []
        for doc in docs:
            d = doc.to_dict()
            if d.get("deleted_at") is not None:
                continue
            d["image_url"] = f"/api/images/{d['image_path'].lstrip('/')}"
            if d.get("thumbnail_path"):
                d["thumbnail_url"] = f"/api/images/{d['thumbnail_path'].lstrip('/')}"
            else:
                d["thumbnail_url"] = d["image_url"]
            results.append(d)
        return results

    def delete_background_reference(self, user_id: str, bg_id: str) -> bool:
        doc_ref = self.db.collection("background_references").document(bg_id)
        doc = doc_ref.get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("user_id") == user_id:
                doc_ref.update({"deleted_at": self._now_iso()})
                return True
        return False

    # -------------------------------------------------------------------------
    # 4. WARDROBE ITEMS
    # -------------------------------------------------------------------------
    def _normalize_wardrobe_doc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        item_id = data.get("id", "")
        bbox = data.get("bbox_json") or data.get("bbox")
        if isinstance(bbox, str):
            import json
            try:
                bbox = json.loads(bbox)
            except Exception:
                bbox = None
        data["bbox"] = bbox
        data["bbox_json"] = bbox

        details = data.get("extracted_details_json") or data.get("extracted_details")
        if isinstance(details, str):
            import json
            try:
                details = json.loads(details)
            except Exception:
                details = None
        data["extracted_details"] = details
        data["extracted_details_json"] = details

        if not data.get("upscale_status"):
            data["upscale_status"] = "completed" if data.get("upscaled_image_path") else "pending"
        data["is_upscaled"] = bool(data.get("upscaled_image_path") and data.get("upscale_status") == "completed")
        data["cost_usd"] = float(data.get("cost_usd") or 0.0)
        data["tokens"] = int(data.get("tokens") or 0)

        # Ensure image URLs are populated for clients
        cropped_path = data.get("cropped_image_path")
        if not data.get("image_url"):
            if cropped_path:
                if cropped_path.startswith("http://") or cropped_path.startswith("https://") or cropped_path.startswith("/api/"):
                    data["image_url"] = cropped_path
                else:
                    data["image_url"] = f"/api/images/{cropped_path.lstrip('/')}"
            elif item_id:
                data["image_url"] = f"/api/wardrobe/items/{item_id}/image"
            else:
                data["image_url"] = ""

        upscaled_path = data.get("upscaled_image_path")
        if not data.get("upscaled_image_url"):
            if upscaled_path:
                if upscaled_path.startswith("http://") or upscaled_path.startswith("https://") or upscaled_path.startswith("/api/"):
                    data["upscaled_image_url"] = upscaled_path
                else:
                    data["upscaled_image_url"] = f"/api/images/{upscaled_path.lstrip('/')}"
            elif item_id and data.get("is_upscaled"):
                data["upscaled_image_url"] = f"/api/wardrobe/items/{item_id}/upscaled-image"
            else:
                data["upscaled_image_url"] = None

        source_path = data.get("source_image_path")
        if not data.get("source_image_url"):
            if source_path:
                if source_path.startswith("http://") or source_path.startswith("https://") or source_path.startswith("/api/"):
                    data["source_image_url"] = source_path
                else:
                    data["source_image_url"] = f"/api/images/{source_path.lstrip('/')}"
            else:
                data["source_image_url"] = None

        return data

    def create_wardrobe_item(self, user_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        item_id = item_data["id"]
        logger.info(f"Creating wardrobe item {item_id} for user {user_id}: {item_data.get('label')}")

        bbox = item_data.get("bbox") or item_data.get("bbox_json")
        details = item_data.get("extracted_details") or item_data.get("extracted_details_json")

        doc_data = {
            "id": item_id,
            "user_id": user_id,
            "source_image_path": item_data.get("source_image_path", ""),
            "label": item_data.get("label", "Garment"),
            "category": item_data.get("category", "tops"),
            "cropped_image_path": item_data.get("cropped_image_path", ""),
            "upscaled_image_path": item_data.get("upscaled_image_path"),
            "upscale_status": item_data.get("upscale_status", "pending"),
            "upscale_error": item_data.get("upscale_error"),
            "bbox_json": self._to_firestore_safe(bbox),
            "extracted_details_json": self._to_firestore_safe(details),
            "cost_usd": float(item_data.get("cost_usd") or 0.0),
            "tokens": int(item_data.get("tokens") or 0),
            "created_at": item_data.get("created_at") or self._now_iso(),
            "deleted_at": None,
        }
        self.db.collection("wardrobe_items").document(item_id).set(doc_data)
        return self._normalize_wardrobe_doc(doc_data)

    def update_wardrobe_item_details(
        self,
        item_id: str,
        extracted_details: Dict[str, Any],
        cost_usd: Optional[float] = None,
        tokens: Optional[int] = None,
    ) -> bool:
        doc_ref = self.db.collection("wardrobe_items").document(item_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("deleted_at") is not None:
            return False

        update_data: Dict[str, Any] = {"extracted_details_json": self._to_firestore_safe(extracted_details)}
        if cost_usd is not None and cost_usd > 0:
            update_data["cost_usd"] = Increment(cost_usd)
        if tokens is not None and tokens > 0:
            update_data["tokens"] = Increment(tokens)

        doc_ref.update(update_data)
        return True

    def update_wardrobe_item_upscale(
        self,
        item_id: str,
        upscaled_image_path: Optional[str],
        upscale_status: str = "completed",
        upscale_error: Optional[str] = None,
        cost_usd: Optional[float] = None,
        tokens: Optional[int] = None,
    ) -> bool:
        doc_ref = self.db.collection("wardrobe_items").document(item_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("deleted_at") is not None:
            return False

        update_data: Dict[str, Any] = {
            "upscale_status": upscale_status,
            "upscale_error": upscale_error,
        }
        if upscaled_image_path:
            update_data["upscaled_image_path"] = upscaled_image_path
        if cost_usd is not None and cost_usd > 0:
            update_data["cost_usd"] = Increment(cost_usd)
        if tokens is not None and tokens > 0:
            update_data["tokens"] = Increment(tokens)

        doc_ref.update(update_data)
        return True

    def get_wardrobe_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("wardrobe_items").document(item_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("deleted_at") is None:
                return self._normalize_wardrobe_doc(data)
        return None

    def list_wardrobe_items(self, user_id: str) -> List[Dict[str, Any]]:
        docs = (
            self.db.collection("wardrobe_items")
            .where("user_id", "==", user_id)
            .where("deleted_at", "==", None)
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [self._normalize_wardrobe_doc(d.to_dict()) for d in docs]

    def delete_wardrobe_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        doc_ref = self.db.collection("wardrobe_items").document(item_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("deleted_at") is not None:
            return None

        # Soft delete
        doc_ref.update({"deleted_at": self._now_iso()})

        # Remove associated composition assignments
        assignments = (
            self.db.collection("composition_assignments")
            .where("wardrobe_item_id", "==", item_id)
            .stream()
        )
        batch = self.db.batch()
        for a in assignments:
            batch.delete(a.reference)
        batch.commit()

        return self._normalize_wardrobe_doc(data)

    def delete_all_wardrobe_items(self, user_id: str) -> List[Dict[str, Any]]:
        docs = list(
            self.db.collection("wardrobe_items")
            .where("user_id", "==", user_id)
            .where("deleted_at", "==", None)
            .stream()
        )
        if not docs:
            return []

        now_str = self._now_iso()
        batch = self.db.batch()
        deleted_items = []
        for d in docs:
            batch.update(d.reference, {"deleted_at": now_str})
            deleted_items.append(self._normalize_wardrobe_doc(d.to_dict()))

        # Remove assignments
        assignments = self.db.collection("composition_assignments").where("user_id", "==", user_id).stream()
        for a in assignments:
            batch.delete(a.reference)

        batch.commit()
        return deleted_items

    # -------------------------------------------------------------------------
    # 5. COMPOSITION ASSIGNMENTS
    # -------------------------------------------------------------------------
    def create_composition_assignment(self, user_id: str, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        assign_id = assignment_data["id"]
        doc_data = {
            "id": assign_id,
            "user_id": user_id,
            "generation_id": assignment_data["generation_id"],
            "wardrobe_item_id": assignment_data["wardrobe_item_id"],
            "pin_number": int(assignment_data["pin_number"]),
            "drop_position_json": self._to_firestore_safe(assignment_data.get("drop_position") or assignment_data.get("drop_position_json")),
            "target_description": assignment_data.get("target_description"),
            "region_bbox_json": self._to_firestore_safe(assignment_data.get("region_bbox") or assignment_data.get("region_bbox_json")),
            "created_at": assignment_data.get("created_at") or self._now_iso(),
        }
        self.db.collection("composition_assignments").document(assign_id).set(doc_data)
        return doc_data

    def list_composition_assignments(self, generation_id: str) -> List[Dict[str, Any]]:
        docs = list(
            self.db.collection("composition_assignments")
            .where("generation_id", "==", generation_id)
            .order_by("pin_number", direction="ASCENDING")
            .stream()
        )
        if not docs:
            return []

        assignments = [d.to_dict() for d in docs]
        
        # Batch fetch wardrobe item labels and cropped paths
        wardrobe_item_ids = list({a["wardrobe_item_id"] for a in assignments if a.get("wardrobe_item_id")})
        wardrobe_map = {}
        for wid in wardrobe_item_ids:
            w_doc = self.db.collection("wardrobe_items").document(wid).get()
            if w_doc.exists:
                w_data = w_doc.to_dict()
                wardrobe_map[wid] = {
                    "wardrobe_label": w_data.get("label"),
                    "cropped_image_path": w_data.get("cropped_image_path"),
                }

        results = []
        for a in assignments:
            item_info = wardrobe_map.get(a.get("wardrobe_item_id"), {})
            res = dict(a)
            res["wardrobe_label"] = item_info.get("wardrobe_label")
            res["cropped_image_path"] = item_info.get("cropped_image_path")
            res["drop_position"] = a.get("drop_position_json")
            res["region_bbox"] = a.get("region_bbox_json")
            results.append(res)

        return results

    # -------------------------------------------------------------------------
    # 6. OBSERVABILITY & INSPECTOR SUMMARY
    # -------------------------------------------------------------------------
    def get_tables_summary(self) -> Dict[str, Any]:
        summary = {}
        for coll_name in ALLOWED_COLLECTIONS:
            try:
                # Count documents using aggregation or stream
                docs = list(self.db.collection(coll_name).limit(1000).stream())
                count = len(docs)
                summary[coll_name] = {"row_count": count, "columns": []}
            except Exception as err:
                logger.warning(f"Failed to inspect collection {coll_name}: {err}")
                summary[coll_name] = {"row_count": 0, "columns": []}
        return summary

    def get_table_records(
        self,
        table_name: str,
        limit: int = 50,
        offset: int = 0,
        start_after_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if table_name not in ALLOWED_COLLECTIONS:
            raise ValueError(f"Invalid or unauthorized collection name '{table_name}'.")

        coll = self.db.collection(table_name)
        # Order by created_at desc if field exists, else document ID
        query = coll
        if start_after_id:
            start_doc = coll.document(start_after_id).get()
            if start_doc.exists:
                query = query.start_after(start_doc)
        elif offset > 0:
            query = query.offset(offset)

        query = query.limit(limit)
        docs = list(query.stream())
        rows = [d.to_dict() for d in docs]
        next_cursor = docs[-1].id if len(docs) == limit else None

        return {
            "table": table_name,
            "total": len(rows),
            "limit": limit,
            "offset": offset,
            "next_cursor": next_cursor,
            "rows": rows,
        }

    # -------------------------------------------------------------------------
    # 7. USER & PERMISSIONS MANAGEMENT
    # -------------------------------------------------------------------------
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by ID (UID or invite document ID)."""
        doc = self.db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by normalized email address."""
        if not email:
            return None
        norm_email = email.strip().lower()
        docs = list(self.db.collection("users").where("email", "==", norm_email).limit(1).stream())
        if docs:
            return docs[0].to_dict()
        return None

    def create_user_invite(self, email: str, role: str = "user", invited_by: str = "admin") -> Dict[str, Any]:
        """
        Pre-authorizes / invites an email address to the Studio whitelist.
        If an invite or user record already exists for this email, returns it.
        """
        norm_email = email.strip().lower()
        existing = self.get_user_by_email(norm_email)
        if existing:
            return existing

        invite_id = f"invite_{norm_email}"
        doc_data = {
            "id": invite_id,
            "email": norm_email,
            "display_name": norm_email.split("@")[0],
            "photo_url": None,
            "role": role if role in ("admin", "user") else "user",
            "status": "pending_invite",
            "invited_by": invited_by,
            "created_at": self._now_iso(),
            "approved_at": None,
            "last_login_at": None,
            "total_spend_usd": 0.0,
            "total_tokens": 0,
        }
        self.db.collection("users").document(invite_id).set(doc_data)
        logger.info(f"Created user invite for {norm_email} (role={role}, by={invited_by})")
        return doc_data

    def activate_user_on_login(
        self,
        uid: str,
        email: str,
        display_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        is_bootstrap_admin: bool = False,
    ) -> Dict[str, Any]:
        """
        Activates or updates a user upon successful Firebase sign-in.
        - If user already exists with ID `uid`, updates `last_login_at` and profile info.
        - If a pending invite doc exists for `email`, migrates it to document ID `uid` with status='approved'.
        - If is_bootstrap_admin is True, forces role='admin' and status='approved'.
        - If user is not invited and not bootstrap admin, creates an unapproved / unauthorized user record.
        """
        norm_email = (email or "").strip().lower()
        now_ts = self._now_iso()

        # Check existing doc by UID
        user_doc_ref = self.db.collection("users").document(uid)
        existing_doc = user_doc_ref.get()

        if existing_doc.exists:
            user_data = existing_doc.to_dict()
            updates = {
                "last_login_at": now_ts,
            }
            if display_name and not user_data.get("display_name"):
                updates["display_name"] = display_name
            if photo_url and not user_data.get("photo_url"):
                updates["photo_url"] = photo_url
            if is_bootstrap_admin and (user_data.get("role") != "admin" or user_data.get("status") != "approved"):
                updates["role"] = "admin"
                updates["status"] = "approved"
                if not user_data.get("approved_at"):
                    updates["approved_at"] = now_ts
            user_doc_ref.update(updates)
            user_data.update(updates)
            return user_data

        # Check if an invite doc exists for this email
        invite_record = self.get_user_by_email(norm_email)
        role = "admin" if is_bootstrap_admin else (invite_record.get("role", "user") if invite_record else "user")
        status = "approved" if (is_bootstrap_admin or invite_record) else "unauthorized"
        invited_by = invite_record.get("invited_by") if invite_record else ("system_bootstrap" if is_bootstrap_admin else None)
        created_at = invite_record.get("created_at") if invite_record else now_ts

        # Remove old invite doc if it had an invite_id key
        if invite_record and invite_record.get("id") and invite_record["id"] != uid:
            try:
                self.db.collection("users").document(invite_record["id"]).delete()
            except Exception as err:
                logger.warning(f"Could not delete old invite doc {invite_record['id']}: {err}")

        user_data = {
            "id": uid,
            "email": norm_email,
            "display_name": display_name or norm_email.split("@")[0] if norm_email else "Studio User",
            "photo_url": photo_url,
            "role": role,
            "status": status,
            "invited_by": invited_by,
            "created_at": created_at,
            "approved_at": now_ts if status == "approved" else None,
            "last_login_at": now_ts,
            "total_spend_usd": invite_record.get("total_spend_usd", 0.0) if invite_record else 0.0,
            "total_tokens": invite_record.get("total_tokens", 0) if invite_record else 0,
        }
        user_doc_ref.set(user_data)
        logger.info(f"Activated user doc for {norm_email} (uid={uid}, role={role}, status={status})")
        return user_data

    def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all registered and invited users."""
        docs = list(self.db.collection("users").order_by("created_at", direction="DESCENDING").limit(limit).stream())
        return [d.to_dict() for d in docs]

    def update_user_status(
        self,
        user_id: str,
        status: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update role or status of a user/invite."""
        doc_ref = self.db.collection("users").document(user_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        updates = {}
        if status in ("approved", "pending_invite", "disabled", "unauthorized"):
            updates["status"] = status
            if status == "approved" and not doc.to_dict().get("approved_at"):
                updates["approved_at"] = self._now_iso()
        if role in ("admin", "user"):
            updates["role"] = role

        if updates:
            doc_ref.update(updates)
            updated = doc.to_dict()
            updated.update(updates)
            return updated
        return doc.to_dict()

    def delete_user(self, user_id: str) -> bool:
        """Deletes a user or invite document."""
        doc_ref = self.db.collection("users").document(user_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            return True
        return False

    def add_user_spend(self, user_id: str, cost_usd: float, tokens: int = 0) -> None:
        """Increment cumulative spend and tokens for a user."""
        try:
            doc_ref = self.db.collection("users").document(user_id)
            if doc_ref.get().exists:
                doc_ref.update({
                    "total_spend_usd": Increment(cost_usd),
                    "total_tokens": Increment(tokens),
                })
        except Exception as err:
            logger.warning(f"Failed to update spend for user {user_id}: {err}")


# Alias for backward compatibility
DatabaseManager = FirestoreManager

