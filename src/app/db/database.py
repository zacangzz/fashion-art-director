from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from google.cloud.firestore import Client, Increment
from app.utils.logger import get_logger
from app.utils.pricing import round_up_cost, OFFICIAL_MODEL_PRICING_SEEDS
from app.utils.currency_service import get_daily_exchange_rate, get_today_iso_date

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
    "model_pricing",
    "currency_rates",
]


class FirestoreManager:
    """
    Unified synchronous Firestore Native database manager.
    Enforces multi-tenancy with user_id, native maps/arrays,
    time-based model pricing, dual-currency (USD/SGD) spend tracking,
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
    # 0. MODEL PRICING & CURRENCY RATES
    # -------------------------------------------------------------------------
    def seed_model_pricing(self) -> int:
        """
        Seeds official Google Gemini API model pricing tiers into the `model_pricing` collection
        if the collection is currently uninitialized.
        """
        try:
            coll = self.db.collection("model_pricing")
            existing = list(coll.limit(1).stream())
            if existing:
                return 0
            count = 0
            for seed in OFFICIAL_MODEL_PRICING_SEEDS:
                doc_id = f"{seed['model_name']}_{seed['effective_date']}"
                data = dict(seed)
                data["id"] = doc_id
                data["created_at"] = self._now_iso()
                coll.document(doc_id).set(data)
                count += 1
            logger.info(f"Seeded {count} official model pricing tiers into Firestore")
            return count
        except Exception as err:
            logger.warning(f"Could not seed model pricing tiers: {err}")
            return 0

    def get_effective_model_pricing(
        self,
        model_name: str,
        target_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Queries the active model pricing tier for a model as of target_date."""
        date_key = target_date or get_today_iso_date()
        m_key = model_name.lower().strip()
        try:
            docs = list(
                self.db.collection("model_pricing")
                .where("model_name", "==", m_key)
                .where("effective_date", "<=", date_key)
                .order_by("effective_date", direction="DESCENDING")
                .limit(1)
                .stream()
            )
            if docs:
                return docs[0].to_dict()
        except Exception as err:
            logger.debug(f"Model pricing query note for {model_name}: {err}")
        return None

    def save_exchange_rate(self, date_str: str, rate: float, source: str = "yahoo_finance") -> Dict[str, Any]:
        """Saves a daily USD/SGD currency conversion rate to Firestore."""
        doc_data = {
            "id": date_str,
            "date": date_str,
            "from_currency": "USD",
            "to_currency": "SGD",
            "rate": round(rate, 4),
            "source": source,
            "fetched_at": self._now_iso(),
        }
        self.db.collection("currency_rates").document(date_str).set(doc_data)
        return doc_data

    def get_exchange_rate(self, date_str: Optional[str] = None) -> float:
        """Retrieves the effective USD/SGD exchange rate for a given date."""
        return get_daily_exchange_rate(target_date=date_str, db=self.db)

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
            "cost_sgd": 0.0,
            "tokens": 0,
            "accumulated_cost_usd": 0.0,
            "accumulated_cost_sgd": 0.0,
            "accumulated_tokens": 0,
            "created_at": self._now_iso(),
        }
        doc_ref.set(data)
        return data

    def add_moodboard_cost(self, moodboard_id: str, cost_usd: float, tokens: int = 0) -> None:
        c_usd = round_up_cost(cost_usd, 3)
        eff_rate = get_daily_exchange_rate(db=self.db)
        c_sgd = round_up_cost(cost_usd * eff_rate, 3)

        doc_ref = self.db.collection("moodboards").document(moodboard_id)
        doc = doc_ref.get()
        doc_ref.update({
            "cost_usd": Increment(c_usd),
            "cost_sgd": Increment(c_sgd),
            "tokens": Increment(tokens),
            "accumulated_cost_usd": Increment(c_usd),
            "accumulated_cost_sgd": Increment(c_sgd),
            "accumulated_tokens": Increment(tokens),
        })

        if doc.exists:
            user_id = doc.to_dict().get("user_id")
            if user_id:
                self.add_user_spend(user_id=user_id, cost_usd=c_usd, cost_sgd=c_sgd, tokens=tokens)

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

        eff_rate = float(data.get("exchange_rate") or get_daily_exchange_rate(db=self.db))
        data["cost_usd"] = round_up_cost(float(data.get("cost_usd") or 0.0), 3)
        data["cost_sgd"] = round_up_cost(float(data.get("cost_sgd") or (data["cost_usd"] * eff_rate)), 3)
        data["tokens"] = int(data.get("tokens") or 0)
        data["accumulated_cost_usd"] = round_up_cost(float(data.get("accumulated_cost_usd") or data["cost_usd"]), 3)
        data["accumulated_cost_sgd"] = round_up_cost(float(data.get("accumulated_cost_sgd") or (data["accumulated_cost_usd"] * eff_rate)), 3)
        data["accumulated_tokens"] = int(data.get("accumulated_tokens") or 0)
        data["exchange_rate"] = eff_rate
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
        cost_usd = round_up_cost(float(gen_data.get("cost_usd") or 0.0), 3)
        eff_rate = float(gen_data.get("exchange_rate") or get_daily_exchange_rate(db=self.db))
        cost_sgd = round_up_cost(float(gen_data.get("cost_sgd") or (cost_usd * eff_rate)), 3)
        tokens = int(gen_data.get("tokens") or 0)

        # Pre-compute lineage accumulation from parent if not already set
        if "accumulated_cost_usd" in gen_data:
            accum_cost_usd = round_up_cost(float(gen_data["accumulated_cost_usd"]), 3)
            accum_cost_sgd = round_up_cost(float(gen_data.get("accumulated_cost_sgd") or (accum_cost_usd * eff_rate)), 3)
            accum_tokens = int(gen_data.get("accumulated_tokens", tokens))
        else:
            accum_cost_usd = cost_usd
            accum_cost_sgd = cost_sgd
            accum_tokens = tokens
            if parent_id:
                parent = self.get_generation(parent_id)
                if parent:
                    p_accum_usd = float(parent.get("accumulated_cost_usd") or parent.get("cost_usd", 0.0))
                    p_accum_sgd = float(parent.get("accumulated_cost_sgd") or (p_accum_usd * eff_rate))
                    accum_cost_usd = round_up_cost(p_accum_usd + cost_usd, 3)
                    accum_cost_sgd = round_up_cost(p_accum_sgd + cost_sgd, 3)
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

        created_at_val = gen_data.get("created_at") or self._now_iso()
        rate_date = gen_data.get("exchange_rate_date") or created_at_val[:10]

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
            "cost_sgd": cost_sgd,
            "exchange_rate": eff_rate,
            "exchange_rate_date": rate_date,
            "tokens": tokens,
            "accumulated_cost_usd": accum_cost_usd,
            "accumulated_cost_sgd": accum_cost_sgd,
            "accumulated_tokens": accum_tokens,
            "created_at": created_at_val,
        }

        logger.info(
            f"Creating generation {gen_id} for user {user_id} (is_baseline={doc_data['is_baseline']}, "
            f"cost_usd=${cost_usd:.3f}, cost_sgd=S${cost_sgd:.3f})"
        )
        self.db.collection("generations").document(gen_id).set(doc_data)

        # Increment user spend in Firestore
        if user_id and (cost_usd > 0 or cost_sgd > 0 or tokens > 0):
            self.add_user_spend(user_id=user_id, cost_usd=cost_usd, cost_sgd=cost_sgd, tokens=tokens)

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
        docs = list(query.stream())
        docs.sort(key=lambda d: d.to_dict().get("created_at", ""), reverse=True)
        return [self._normalize_generation_doc(d.to_dict()) for d in docs[:limit]]

    def get_lineage(self, generation_id: str) -> Dict[str, Any]:
        """
        Traverses upward to root ancestor via parent_id.
        Returns dictionary containing:
        - current: Dict
        - ancestors: List[Dict] in chronological order from root to immediate parent
        - descendants: List[Dict] direct children of current generation
        - root_id: str
        - total_chain_cost_usd: float (ceil 3 decimals)
        - total_chain_cost_sgd: float (ceil 3 decimals)
        - total_chain_tokens: int
        """
        current = self.get_generation(generation_id)
        if not current:
            return {"current": None, "ancestors": [], "descendants": [], "root_id": None, "total_chain_cost_usd": 0.0, "total_chain_cost_sgd": 0.0, "total_chain_tokens": 0}

        ancestors = []
        visited = {generation_id}
        curr_parent_id = current.get("parent_id")

        while curr_parent_id and curr_parent_id not in visited:
            visited.add(curr_parent_id)
            parent = self.get_generation(curr_parent_id)
            if not parent:
                break
            ancestors.append(parent)
            curr_parent_id = parent.get("parent_id")

        ancestors.reverse()
        root_id = ancestors[0]["id"] if ancestors else current["id"]

        # Find direct descendants
        desc_docs = list(self.db.collection("generations").where("parent_id", "==", generation_id).stream())
        descendants = [self._normalize_generation_doc(d.to_dict()) for d in desc_docs]

        total_cost_usd = current.get("accumulated_cost_usd") or current.get("cost_usd", 0.0)
        total_cost_sgd = current.get("accumulated_cost_sgd") or current.get("cost_sgd", 0.0)
        total_tokens = current.get("accumulated_tokens") or current.get("tokens", 0)

        return {
            "current": current,
            "ancestors": ancestors,
            "descendants": descendants,
            "root_id": root_id,
            "total_chain_cost_usd": round_up_cost(float(total_cost_usd), 3),
            "total_chain_cost_sgd": round_up_cost(float(total_cost_sgd), 3),
            "total_chain_tokens": int(total_tokens),
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
        doc_ref = self.db.collection("conversations").document(conv_id)
        data = {
            "id": conv_id,
            "user_id": user_id,
            "baseline_generation_id": baseline_generation_id,
            "moodboard_id": moodboard_id,
            "created_at": self._now_iso(),
        }
        doc_ref.set(data)
        return data

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("conversations").document(conv_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def get_conversation_history(self, conv_id: str) -> List[Dict[str, Any]]:
        gens = list(self.db.collection("generations").where("conversation_id", "==", conv_id).stream())
        if not gens:
            return []
        items = [self._normalize_generation_doc(g.to_dict()) for g in gens]
        items.sort(key=lambda x: x.get("created_at", ""))
        return items

    # -------------------------------------------------------------------------
    # 4. BACKGROUND REFERENCES
    # -------------------------------------------------------------------------
    def _normalize_bg_doc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        img_path = data.get("image_path", "")
        thumb_path = data.get("thumbnail_path") or img_path
        data["image_url"] = f"/api/images/{img_path.lstrip('/')}" if img_path else ""
        data["thumbnail_url"] = f"/api/images/{thumb_path.lstrip('/')}" if thumb_path else ""
        return data

    def create_background_reference(self, user_id: str, bg_data: Dict[str, Any]) -> Dict[str, Any]:
        bg_id = bg_data["id"]
        doc_data = {
            "id": bg_id,
            "user_id": user_id,
            "original_filename": bg_data.get("original_filename", ""),
            "image_path": bg_data.get("image_path", ""),
            "thumbnail_path": bg_data.get("thumbnail_path"),
            "aspect_ratio": bg_data.get("aspect_ratio", "16:9"),
            "tags": bg_data.get("tags") or [],
            "created_at": bg_data.get("created_at") or self._now_iso(),
            "deleted_at": None,
        }
        logger.info(f"Creating background reference {bg_id} for user {user_id}")
        self.db.collection("background_references").document(bg_id).set(doc_data)
        return self._normalize_bg_doc(doc_data)

    def get_background_reference(self, bg_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db.collection("background_references").document(bg_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("deleted_at") is None:
                return self._normalize_bg_doc(data)
        return None

    def list_background_references(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            docs = list(
                self.db.collection("background_references")
                .where("user_id", "==", user_id)
                .where("deleted_at", "==", None)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
        except Exception:
            docs = list(
                self.db.collection("background_references")
                .where("user_id", "==", user_id)
                .limit(limit)
                .stream()
            )
            docs = [d for d in docs if d.to_dict().get("deleted_at") is None]
            docs.sort(key=lambda d: d.to_dict().get("created_at", ""), reverse=True)

        return [self._normalize_bg_doc(d.to_dict()) for d in docs]

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
    # 5. WARDROBE & COMPOSITION
    # -------------------------------------------------------------------------
    def _normalize_wardrobe_doc(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        crop_path = data.get("cropped_image_path", "")
        upscale_path = data.get("upscaled_image_path")
        data["image_url"] = f"/api/images/{crop_path.lstrip('/')}" if crop_path else ""
        data["upscaled_image_url"] = f"/api/images/{upscale_path.lstrip('/')}" if upscale_path else None
        data["bbox"] = data.get("bbox_json") or data.get("bbox") or []
        data["extracted_details"] = data.get("extracted_details_json") or data.get("extracted_details") or {}
        eff_rate = float(data.get("exchange_rate") or get_daily_exchange_rate(db=self.db))
        data["cost_usd"] = round_up_cost(float(data.get("cost_usd") or 0.0), 3)
        data["cost_sgd"] = round_up_cost(float(data.get("cost_sgd") or (data["cost_usd"] * eff_rate)), 3)
        data["tokens"] = int(data.get("tokens") or 0)
        return data

    def create_wardrobe_item(self, user_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        item_id = item_data["id"]
        logger.info(f"Creating wardrobe item {item_id} for user {user_id}: {item_data.get('label')}")

        bbox = item_data.get("bbox") or item_data.get("bbox_json")
        details = item_data.get("extracted_details") or item_data.get("extracted_details_json")

        c_usd = round_up_cost(float(item_data.get("cost_usd") or 0.0), 3)
        eff_rate = get_daily_exchange_rate(db=self.db)
        c_sgd = round_up_cost(float(item_data.get("cost_sgd") or (c_usd * eff_rate)), 3)
        toks = int(item_data.get("tokens") or 0)

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
            "cost_usd": c_usd,
            "cost_sgd": c_sgd,
            "tokens": toks,
            "created_at": item_data.get("created_at") or self._now_iso(),
            "deleted_at": None,
        }
        self.db.collection("wardrobe_items").document(item_id).set(doc_data)

        if user_id and (c_usd > 0 or c_sgd > 0 or toks > 0):
            self.add_user_spend(user_id=user_id, cost_usd=c_usd, cost_sgd=c_sgd, tokens=toks)

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
            c_usd = round_up_cost(cost_usd, 3)
            eff_rate = get_daily_exchange_rate(db=self.db)
            c_sgd = round_up_cost(cost_usd * eff_rate, 3)
            update_data["cost_usd"] = Increment(c_usd)
            update_data["cost_sgd"] = Increment(c_sgd)
            toks = tokens or 0
            if toks > 0:
                update_data["tokens"] = Increment(toks)
            user_id = doc.to_dict().get("user_id")
            if user_id:
                self.add_user_spend(user_id=user_id, cost_usd=c_usd, cost_sgd=c_sgd, tokens=toks)
        elif tokens is not None and tokens > 0:
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
            c_usd = round_up_cost(cost_usd, 3)
            eff_rate = get_daily_exchange_rate(db=self.db)
            c_sgd = round_up_cost(cost_usd * eff_rate, 3)
            update_data["cost_usd"] = Increment(c_usd)
            update_data["cost_sgd"] = Increment(c_sgd)
            toks = tokens or 0
            if toks > 0:
                update_data["tokens"] = Increment(toks)
            user_id = doc.to_dict().get("user_id")
            if user_id:
                self.add_user_spend(user_id=user_id, cost_usd=c_usd, cost_sgd=c_sgd, tokens=toks)
        elif tokens is not None and tokens > 0:
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
        docs = list(
            self.db.collection("wardrobe_items")
            .where("user_id", "==", user_id)
            .stream()
        )
        active = [d.to_dict() for d in docs if d.to_dict().get("deleted_at") is None]
        active.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return [self._normalize_wardrobe_doc(d) for d in active]

    def delete_wardrobe_item(self, item_id_or_user: str, item_id: Optional[str] = None) -> bool:
        """
        Soft deletes a wardrobe item.
        Supports both signatures: delete_wardrobe_item(item_id) or delete_wardrobe_item(user_id, item_id).
        """
        target_item_id = item_id if item_id is not None else item_id_or_user
        expected_user_id = item_id_or_user if item_id is not None else None

        doc_ref = self.db.collection("wardrobe_items").document(target_item_id)
        doc = doc_ref.get()
        if doc.exists:
            d = doc.to_dict()
            if expected_user_id and d.get("user_id") != expected_user_id:
                return False
            if d.get("deleted_at") is None:
                doc_ref.update({"deleted_at": self._now_iso()})
                assignments = self.db.collection("composition_assignments").where("wardrobe_item_id", "==", target_item_id).stream()
                for a in assignments:
                    self.db.collection("composition_assignments").document(a.id).delete()
                return True
        return False

    def delete_all_wardrobe_items(self, user_id: str) -> List[Dict[str, Any]]:
        docs = list(
            self.db.collection("wardrobe_items")
            .where("user_id", "==", user_id)
            .stream()
        )
        active = [d.to_dict() for d in docs if d.to_dict().get("deleted_at") is None]
        now_ts = self._now_iso()
        for d in active:
            item_id = d["id"]
            self.db.collection("wardrobe_items").document(item_id).update({"deleted_at": now_ts})
            assignments = self.db.collection("composition_assignments").where("wardrobe_item_id", "==", item_id).stream()
            for a in assignments:
                self.db.collection("composition_assignments").document(a.id).delete()

        assignments = self.db.collection("composition_assignments").where("user_id", "==", user_id).stream()
        for a in assignments:
            self.db.collection("composition_assignments").document(a.id).delete()

        return [self._normalize_wardrobe_doc(d) for d in active]

    def create_composition_assignment(self, user_id: str, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        assignment_id = assignment_data["id"]
        doc_data = {
            "id": assignment_id,
            "user_id": user_id,
            "generation_id": assignment_data.get("generation_id"),
            "wardrobe_item_id": assignment_data.get("wardrobe_item_id"),
            "pin_number": int(assignment_data.get("pin_number", 1)),
            "drop_position": self._to_firestore_safe(assignment_data.get("drop_position") or {"x": 0.5, "y": 0.5}),
            "target_description": assignment_data.get("target_description", ""),
            "region_bbox": self._to_firestore_safe(assignment_data.get("region_bbox") or []),
            "created_at": assignment_data.get("created_at") or self._now_iso(),
        }
        self.db.collection("composition_assignments").document(assignment_id).set(doc_data)
        return doc_data

    def list_composition_assignments(self, generation_id: str) -> List[Dict[str, Any]]:
        docs = list(self.db.collection("composition_assignments").where("generation_id", "==", generation_id).stream())
        items = [d.to_dict() for d in docs]
        items.sort(key=lambda x: x.get("pin_number", 0))

        # Enrich assignments with wardrobe label & crop path if available
        for a in items:
            w_id = a.get("wardrobe_item_id")
            if w_id:
                w_item = self.get_wardrobe_item(w_id)
                if w_item:
                    a["wardrobe_label"] = w_item.get("label")
                    a["cropped_image_path"] = w_item.get("cropped_image_path")
                    a["cropped_image_url"] = w_item.get("image_url")
                    a["category"] = w_item.get("category")
        return items

    # -------------------------------------------------------------------------
    # 6. USERS, WHITELIST & AUTHENTICATION
    # -------------------------------------------------------------------------
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by ID (UID or invite document ID)."""
        doc = self.db.collection("users").document(user_id).get()
        if doc.exists:
            d = doc.to_dict()
            eff_rate = get_daily_exchange_rate(db=self.db)
            d["total_spend_usd"] = round_up_cost(float(d.get("total_spend_usd") or 0.0), 3)
            d["total_spend_sgd"] = round_up_cost(float(d.get("total_spend_sgd") or (d["total_spend_usd"] * eff_rate)), 3)
            return d
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user document by normalized email address."""
        if not email:
            return None
        norm_email = email.strip().lower()
        docs = list(self.db.collection("users").where("email", "==", norm_email).limit(1).stream())
        if docs:
            d = docs[0].to_dict()
            eff_rate = get_daily_exchange_rate(db=self.db)
            d["total_spend_usd"] = round_up_cost(float(d.get("total_spend_usd") or 0.0), 3)
            d["total_spend_sgd"] = round_up_cost(float(d.get("total_spend_sgd") or (d["total_spend_usd"] * eff_rate)), 3)
            return d
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
            "total_spend_sgd": 0.0,
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
        eff_rate = get_daily_exchange_rate(db=self.db)

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
            if "total_spend_sgd" not in user_data:
                usd = float(user_data.get("total_spend_usd") or 0.0)
                updates["total_spend_sgd"] = round_up_cost(usd * eff_rate, 3)

            user_doc_ref.update(updates)
            user_data.update(updates)
            user_data["total_spend_usd"] = round_up_cost(float(user_data.get("total_spend_usd") or 0.0), 3)
            user_data["total_spend_sgd"] = round_up_cost(float(user_data.get("total_spend_sgd") or (user_data["total_spend_usd"] * eff_rate)), 3)
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

        init_usd = round_up_cost(invite_record.get("total_spend_usd", 0.0) if invite_record else 0.0, 3)
        init_sgd = round_up_cost(invite_record.get("total_spend_sgd", init_usd * eff_rate) if invite_record else (init_usd * eff_rate), 3)

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
            "total_spend_usd": init_usd,
            "total_spend_sgd": init_sgd,
            "total_tokens": invite_record.get("total_tokens", 0) if invite_record else 0,
        }
        user_doc_ref.set(user_data)
        logger.info(f"Activated user doc for {norm_email} (uid={uid}, role={role}, status={status})")
        return user_data

    def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all registered and invited users, dynamically aggregating real-time spend
        across generations, wardrobe items, and moodboard analysis in both USD and SGD
        (rounded up to 3 decimals).
        """
        docs = list(self.db.collection("users").order_by("created_at", direction="DESCENDING").limit(limit).stream())
        users_list = [d.to_dict() for d in docs]

        eff_rate = get_daily_exchange_rate(db=self.db)

        # Aggregate generations compute spend by user_id
        spend_usd_by_uid: Dict[str, float] = {}
        spend_sgd_by_uid: Dict[str, float] = {}
        tokens_by_uid: Dict[str, int] = {}

        try:
            for g_doc in self.db.collection("generations").stream():
                g_dict = g_doc.to_dict()
                u_id = g_dict.get("user_id")
                if not u_id:
                    continue
                c_usd = float(g_dict.get("cost_usd") or 0.0)
                c_sgd = float(g_dict.get("cost_sgd") or (c_usd * eff_rate))
                t_toks = int(g_dict.get("tokens") or 0)
                if c_usd > 0:
                    spend_usd_by_uid[u_id] = spend_usd_by_uid.get(u_id, 0.0) + c_usd
                if c_sgd > 0:
                    spend_sgd_by_uid[u_id] = spend_sgd_by_uid.get(u_id, 0.0) + c_sgd
                if t_toks > 0:
                    tokens_by_uid[u_id] = tokens_by_uid.get(u_id, 0) + t_toks
        except Exception as err:
            logger.debug(f"Generation spend aggregation note: {err}")

        # Aggregate wardrobe items
        try:
            for w_doc in self.db.collection("wardrobe_items").stream():
                w_dict = w_doc.to_dict()
                u_id = w_dict.get("user_id")
                if not u_id or w_dict.get("deleted_at") is not None:
                    continue
                c_usd = float(w_dict.get("cost_usd") or 0.0)
                c_sgd = float(w_dict.get("cost_sgd") or (c_usd * eff_rate))
                t_toks = int(w_dict.get("tokens") or 0)
                if c_usd > 0:
                    spend_usd_by_uid[u_id] = spend_usd_by_uid.get(u_id, 0.0) + c_usd
                if c_sgd > 0:
                    spend_sgd_by_uid[u_id] = spend_sgd_by_uid.get(u_id, 0.0) + c_sgd
                if t_toks > 0:
                    tokens_by_uid[u_id] = tokens_by_uid.get(u_id, 0) + t_toks
        except Exception as err:
            logger.debug(f"Wardrobe spend aggregation note: {err}")

        # Update each user with accurate, ceiling-rounded spend
        for u in users_list:
            keys = {u.get("id"), u.get("uid"), u.get("email")}
            keys.discard(None)

            computed_usd = sum(spend_usd_by_uid.get(k, 0.0) for k in keys)
            computed_sgd = sum(spend_sgd_by_uid.get(k, 0.0) for k in keys)
            computed_toks = sum(tokens_by_uid.get(k, 0) for k in keys)

            stored_usd = float(u.get("total_spend_usd") or 0.0)
            stored_sgd = float(u.get("total_spend_sgd") or (stored_usd * eff_rate))
            stored_toks = int(u.get("total_tokens") or 0)

            final_usd = round_up_cost(max(stored_usd, computed_usd), 3)
            final_sgd = round_up_cost(max(stored_sgd, computed_sgd, final_usd * eff_rate), 3)
            final_toks = max(stored_toks, computed_toks)

            u["total_spend_usd"] = final_usd
            u["total_spend_sgd"] = final_sgd
            u["total_tokens"] = final_toks

            # If Firestore doc had lower/missing spend, update it
            if u.get("id") and (final_usd > stored_usd or "total_spend_sgd" not in u):
                try:
                    self.db.collection("users").document(u["id"]).update({
                        "total_spend_usd": final_usd,
                        "total_spend_sgd": final_sgd,
                        "total_tokens": final_toks,
                    })
                except Exception:
                    pass

        return users_list

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

    def add_user_spend(
        self,
        user_id: str,
        cost_usd: float,
        cost_sgd: Optional[float] = None,
        tokens: int = 0,
    ) -> None:
        """
        Increment cumulative spend (USD and SGD, ceil rounded to 3 decimals) and tokens for a user.
        """
        if not user_id or user_id in ("anonymous", "public_anonymous"):
            return

        eff_rate = get_daily_exchange_rate(db=self.db)
        c_usd = round_up_cost(cost_usd, 3)
        c_sgd = round_up_cost(cost_sgd if cost_sgd is not None else (cost_usd * eff_rate), 3)

        if c_usd <= 0 and c_sgd <= 0 and tokens <= 0:
            return

        try:
            doc_ref = self.db.collection("users").document(user_id)
            if doc_ref.get().exists:
                doc_ref.update({
                    "total_spend_usd": Increment(c_usd),
                    "total_spend_sgd": Increment(c_sgd),
                    "total_tokens": Increment(tokens),
                })
                return

            # Check if user_id is an email address
            norm_email = user_id.strip().lower() if "@" in user_id else None
            if norm_email:
                existing = self.get_user_by_email(norm_email)
                if existing and existing.get("id"):
                    self.db.collection("users").document(existing["id"]).update({
                        "total_spend_usd": Increment(c_usd),
                        "total_spend_sgd": Increment(c_sgd),
                        "total_tokens": Increment(tokens),
                    })
        except Exception as err:
            logger.warning(f"Failed to update spend for user {user_id}: {err}")

    # -------------------------------------------------------------------------
    # 7. OBSERVABILITY & DATABASE INSPECTOR
    # -------------------------------------------------------------------------
    def get_tables_summary(self) -> Dict[str, Any]:
        """Returns row counts and schema overview for all allowed collections."""
        summary = {}
        for coll_name in ALLOWED_COLLECTIONS:
            try:
                docs = list(self.db.collection(coll_name).stream())
                sample_fields = list(docs[0].to_dict().keys()) if docs else []
                summary[coll_name] = {
                    "table_name": coll_name,
                    "row_count": len(docs),
                    "columns": sample_fields,
                }
            except Exception as err:
                summary[coll_name] = {"table_name": coll_name, "row_count": 0, "columns": [], "error": str(err)}
        return summary

    def get_table_records(
        self,
        table_name: str,
        limit: int = 50,
        offset: int = 0,
        start_after_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns paginated records for a collection."""
        if table_name not in ALLOWED_COLLECTIONS:
            raise ValueError(f"Table '{table_name}' is not an accessible collection.")

        all_docs = list(self.db.collection(table_name).stream())
        total_count = len(all_docs)

        # If start_after_id is provided, find start index
        start_idx = offset
        if start_after_id:
            for idx, d in enumerate(all_docs):
                doc_dict = d.to_dict() if hasattr(d, "to_dict") else {}
                if d.id == start_after_id or doc_dict.get("id") == start_after_id:
                    start_idx = idx + 1
                    break

        sliced_docs = all_docs[start_idx : start_idx + limit]
        rows = [d.to_dict() if hasattr(d, "to_dict") else d for d in sliced_docs]

        next_cursor = None
        if start_idx + limit < total_count and sliced_docs:
            last_item = sliced_docs[-1]
            last_dict = last_item.to_dict() if hasattr(last_item, "to_dict") else {}
            next_cursor = last_dict.get("id", getattr(last_item, "id", None))

        return {
            "table": table_name,
            "total": total_count,
            "limit": limit,
            "offset": start_idx,
            "next_cursor": next_cursor,
            "rows": rows,
        }


# Alias for backward compatibility
DatabaseManager = FirestoreManager
