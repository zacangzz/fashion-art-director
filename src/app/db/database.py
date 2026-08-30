import json
from typing import List, Dict, Any, Optional
import aiosqlite
from app.utils.logger import get_logger

logger = get_logger("database")

CREATE_MOODBOARDS_TABLE = """
CREATE TABLE IF NOT EXISTS moodboards (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_paths TEXT NOT NULL
);
"""

CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    baseline_generation_id TEXT NOT NULL,
    moodboard_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(baseline_generation_id) REFERENCES generations(id)
);
"""

CREATE_WARDROBE_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS wardrobe_items (
    id TEXT PRIMARY KEY,
    source_image_path TEXT NOT NULL,
    label TEXT NOT NULL,
    category TEXT DEFAULT 'tops',
    cropped_image_path TEXT NOT NULL,
    upscaled_image_path TEXT NULL,
    upscale_status TEXT DEFAULT 'pending',
    upscale_error TEXT NULL,
    bbox_json TEXT,
    extracted_details_json TEXT NULL,
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
"""

CREATE_COMPOSITION_ASSIGNMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS composition_assignments (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    wardrobe_item_id TEXT NOT NULL,
    pin_number INTEGER NOT NULL,
    drop_position_json TEXT,
    target_description TEXT,
    region_bbox_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(generation_id) REFERENCES generations(id),
    FOREIGN KEY(wardrobe_item_id) REFERENCES wardrobe_items(id)
);
"""

CREATE_GENERATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    parent_id TEXT NULL,
    moodboard_id TEXT NULL,
    is_baseline BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_json TEXT NOT NULL,
    compiled_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    seed INTEGER NOT NULL,
    master_image_path TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL DEFAULT '2:3',
    resolution_width INTEGER NOT NULL DEFAULT 1440,
    resolution_height INTEGER NOT NULL DEFAULT 1440,
    conversation_id TEXT NULL,
    model_name TEXT NULL,
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,
    accumulated_cost_usd REAL DEFAULT 0.0,
    accumulated_tokens INTEGER DEFAULT 0,
    FOREIGN KEY(parent_id) REFERENCES generations(id),
    FOREIGN KEY(moodboard_id) REFERENCES moodboards(id)
);
"""

class DatabaseManager:
    def __init__(self, db_path: str = "./storage/studio.db"):
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        self.db_path = db_path
        self._table_columns_cache: Optional[set] = None

    async def init_db(self) -> None:
        logger.info(f"Initializing SQLite database at: {self.db_path}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_MOODBOARDS_TABLE)
            await db.execute(CREATE_GENERATIONS_TABLE)
            await db.execute(CREATE_CONVERSATIONS_TABLE)
            await db.execute(CREATE_WARDROBE_ITEMS_TABLE)
            await db.execute(CREATE_COMPOSITION_ASSIGNMENTS_TABLE)

            # Check for column migrations if table already exists with legacy columns
            async with db.execute("PRAGMA table_info(generations)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if "is_baseline" not in columns:
                    logger.info("Migrating DB: adding column 'is_baseline'")
                    await db.execute("ALTER TABLE generations ADD COLUMN is_baseline BOOLEAN DEFAULT FALSE")
                if "schema_json" not in columns:
                    logger.info("Migrating DB: adding column 'schema_json'")
                    await db.execute("ALTER TABLE generations ADD COLUMN schema_json TEXT DEFAULT '{}'")
                if "compiled_prompt" not in columns:
                    logger.info("Migrating DB: adding column 'compiled_prompt'")
                    await db.execute("ALTER TABLE generations ADD COLUMN compiled_prompt TEXT DEFAULT ''")
                if "conversation_id" not in columns:
                    logger.info("Migrating DB: adding column 'conversation_id'")
                    await db.execute("ALTER TABLE generations ADD COLUMN conversation_id TEXT")
                if "aspect_ratio" not in columns:
                    logger.info("Migrating DB: adding column 'aspect_ratio'")
                    await db.execute("ALTER TABLE generations ADD COLUMN aspect_ratio TEXT DEFAULT '2:3'")
                if "model_name" not in columns:
                    logger.info("Migrating DB: adding column 'model_name'")
                    await db.execute("ALTER TABLE generations ADD COLUMN model_name TEXT")
                if "cost_usd" not in columns:
                    logger.info("Migrating DB: adding column 'cost_usd'")
                    await db.execute("ALTER TABLE generations ADD COLUMN cost_usd REAL DEFAULT 0.0")
                if "tokens" not in columns:
                    logger.info("Migrating DB: adding column 'tokens'")
                    await db.execute("ALTER TABLE generations ADD COLUMN tokens INTEGER DEFAULT 0")
                if "accumulated_cost_usd" not in columns:
                    logger.info("Migrating DB: adding column 'accumulated_cost_usd'")
                    await db.execute("ALTER TABLE generations ADD COLUMN accumulated_cost_usd REAL DEFAULT 0.0")
                if "accumulated_tokens" not in columns:
                    logger.info("Migrating DB: adding column 'accumulated_tokens'")
                    await db.execute("ALTER TABLE generations ADD COLUMN accumulated_tokens INTEGER DEFAULT 0")

            async with db.execute("PRAGMA table_info(wardrobe_items)") as cursor:
                w_cols = [row[1] for row in await cursor.fetchall()]
                if "upscaled_image_path" not in w_cols:
                    logger.info("Migrating DB: adding column 'upscaled_image_path' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN upscaled_image_path TEXT NULL")
                if "upscale_status" not in w_cols:
                    logger.info("Migrating DB: adding column 'upscale_status' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN upscale_status TEXT DEFAULT 'pending'")
                if "upscale_error" not in w_cols:
                    logger.info("Migrating DB: adding column 'upscale_error' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN upscale_error TEXT NULL")
                if "extracted_details_json" not in w_cols:
                    logger.info("Migrating DB: adding column 'extracted_details_json' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN extracted_details_json TEXT NULL")
                if "cost_usd" not in w_cols:
                    logger.info("Migrating DB: adding column 'cost_usd' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN cost_usd REAL DEFAULT 0.0")
                if "tokens" not in w_cols:
                    logger.info("Migrating DB: adding column 'tokens' to wardrobe_items")
                    await db.execute("ALTER TABLE wardrobe_items ADD COLUMN tokens INTEGER DEFAULT 0")

            # Cache current table columns for rapid future insertions
            async with db.execute("PRAGMA table_info(generations)") as cursor:
                self._table_columns_cache = {row[1] for row in await cursor.fetchall()}

            await db.commit()
            logger.info("Database schema verification and migrations complete.")

    async def create_moodboard(self, moodboard_id: str, image_paths: List[str]) -> None:
        logger.info(f"Creating moodboard record {moodboard_id} with {len(image_paths)} images")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO moodboards (id, image_paths) VALUES (?, ?)",
                (moodboard_id, json.dumps(image_paths)),
            )
            await db.commit()

    async def get_moodboard(self, moodboard_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM moodboards WHERE id = ?", (moodboard_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = dict(row)
                    if isinstance(data.get("image_paths"), str):
                        try:
                            data["image_paths"] = json.loads(data["image_paths"])
                        except Exception:
                            data["image_paths"] = []
                    return data
                return None

    def _normalize_generation_row(self, row_dict: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row_dict)
        # Parse schema_json
        schema_raw = data.get("schema_json") or data.get("tags_snapshot") or "{}"
        if isinstance(schema_raw, str):
            try:
                data["schema_json"] = json.loads(schema_raw)
            except Exception:
                data["schema_json"] = {}
        elif isinstance(schema_raw, dict):
            data["schema_json"] = schema_raw

        # Extract inpaint_metadata and mask_image_url if present
        if isinstance(data.get("schema_json"), dict):
            inpaint_meta = data["schema_json"].get("inpaint_metadata")
            if inpaint_meta and isinstance(inpaint_meta, dict):
                data["inpaint_metadata"] = inpaint_meta
                if "mask_url" in inpaint_meta:
                    data["mask_image_url"] = inpaint_meta["mask_url"]

        # Ensure compiled_prompt is present
        if "compiled_prompt" not in data or not data["compiled_prompt"]:
            data["compiled_prompt"] = data.get("prompt", "")
        data["prompt"] = data["compiled_prompt"]

        # Ensure model_name is set
        if not data.get("model_name"):
            if isinstance(data.get("schema_json"), dict):
                data["model_name"] = data["schema_json"].get("imagen_model") or data["schema_json"].get("model_name")

        # Ensure cost and token fields are set
        data["cost_usd"] = float(data.get("cost_usd") or 0.0)
        data["tokens"] = int(data.get("tokens") or 0)
        data["accumulated_cost_usd"] = float(data.get("accumulated_cost_usd") or 0.0)
        data["accumulated_tokens"] = int(data.get("accumulated_tokens") or 0)

        # Ensure is_baseline is bool
        data["is_baseline"] = bool(data.get("is_baseline", False))
        return data

    async def create_generation(self, gen_data: Dict[str, Any]) -> None:
        """
        Dynamically inspects table columns with cache to support modern and legacy schemas
        without NOT NULL constraint failures or redundant PRAGMA round-trips.
        """
        schema_val = gen_data.get("schema_json") or gen_data.get("tags_snapshot") or "{}"

        def _safe_serialize(val: Any) -> str:
            def _default(o):
                if hasattr(o, "model_dump"):
                    return o.model_dump()
                if hasattr(o, "dict"):
                    return o.dict()
                return str(o)
            return json.dumps(val, default=_default)

        if isinstance(schema_val, (dict, list)):
            schema_val = _safe_serialize(schema_val)

        compiled_prompt = gen_data.get("compiled_prompt") or gen_data.get("prompt", "")
        model_name = gen_data.get("model_name")
        if not model_name and isinstance(gen_data.get("schema_json"), dict):
            model_name = gen_data["schema_json"].get("imagen_model") or gen_data["schema_json"].get("model_name")

        cost_usd = float(gen_data.get("cost_usd") or 0.0)
        tokens = int(gen_data.get("tokens") or 0)
        accum_cost = float(gen_data.get("accumulated_cost_usd") or cost_usd)
        accum_tokens = int(gen_data.get("accumulated_tokens") or tokens)

        async with aiosqlite.connect(self.db_path) as db:
            if self._table_columns_cache is None:
                async with db.execute("PRAGMA table_info(generations)") as cursor:
                    self._table_columns_cache = {row[1] for row in await cursor.fetchall()}

            table_columns = self._table_columns_cache

            # Build insert map based on existing columns in the table
            insert_fields = {
                "id": gen_data["id"],
                "parent_id": gen_data.get("parent_id"),
                "moodboard_id": gen_data.get("moodboard_id"),
                "is_baseline": 1 if gen_data.get("is_baseline", False) else 0,
                "negative_prompt": gen_data.get("negative_prompt", "") or "",
                "seed": gen_data["seed"],
                "master_image_path": gen_data["master_image_path"],
                "aspect_ratio": gen_data.get("aspect_ratio", "1:1"),
                "resolution_width": gen_data.get("resolution_width", 3840),
                "resolution_height": gen_data.get("resolution_height", 3840),
                "conversation_id": gen_data.get("conversation_id"),
                "model_name": model_name,
                "cost_usd": cost_usd,
                "tokens": tokens,
                "accumulated_cost_usd": accum_cost,
                "accumulated_tokens": accum_tokens,
            }

            # Map schema & prompt to both modern and legacy column names if present
            if "schema_json" in table_columns:
                insert_fields["schema_json"] = schema_val
            if "tags_snapshot" in table_columns:
                insert_fields["tags_snapshot"] = schema_val

            if "compiled_prompt" in table_columns:
                insert_fields["compiled_prompt"] = compiled_prompt
            if "prompt" in table_columns:
                insert_fields["prompt"] = compiled_prompt

            # Filter down strictly to existing columns in DB
            filtered_fields = {k: v for k, v in insert_fields.items() if k in table_columns}

            keys = list(filtered_fields.keys())
            placeholders = ", ".join(["?"] * len(keys))
            col_names = ", ".join(keys)
            values = [filtered_fields[k] for k in keys]

            logger.info(f"Inserting generation record {gen_data['id']} (is_baseline={gen_data.get('is_baseline', False)}, seed={gen_data['seed']}, cost=${cost_usd:.4f}, accum_cost=${accum_cost:.4f})")
            await db.execute(
                f"INSERT INTO generations ({col_names}) VALUES ({placeholders})",
                values,
            )
            await db.commit()

    async def get_generation(self, generation_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM generations WHERE id = ?", (generation_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._normalize_generation_row(dict(row))
                return None

    async def list_generations(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM generations ORDER BY created_at DESC, rowid DESC") as cursor:
                rows = await cursor.fetchall()
                normalized = [self._normalize_generation_row(dict(row)) for row in rows]

                # If needed, resolve accumulated costs for lineage chains
                records_by_id = {r["id"]: r for r in normalized}
                for r in normalized:
                    if r.get("accumulated_cost_usd", 0.0) == 0.0 and r.get("cost_usd", 0.0) > 0:
                        # Trace ancestors to sum costs
                        total_cost = r.get("cost_usd", 0.0)
                        total_toks = r.get("tokens", 0)
                        curr_p = r.get("parent_id")
                        while curr_p and curr_p in records_by_id:
                            parent_rec = records_by_id[curr_p]
                            total_cost += parent_rec.get("cost_usd", 0.0)
                            total_toks += parent_rec.get("tokens", 0)
                            curr_p = parent_rec.get("parent_id")
                        r["accumulated_cost_usd"] = round(total_cost, 6)
                        r["accumulated_tokens"] = total_toks
                return normalized

    async def get_lineage(self, generation_id: str) -> Dict[str, Any]:
        """
        Traces ancestor chain up to the root baseline, and finds direct descendants.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id, parent_id FROM generations") as cursor:
                pairs = {row["id"]: row["parent_id"] for row in await cursor.fetchall()}

        if generation_id not in pairs:
            return {"root_id": generation_id, "ancestors": [], "descendants": []}

        # Find ancestor IDs
        ancestor_ids = []
        curr_parent_id = pairs.get(generation_id)
        while curr_parent_id and curr_parent_id in pairs:
            ancestor_ids.append(curr_parent_id)
            curr_parent_id = pairs.get(curr_parent_id)

        root_id = ancestor_ids[-1] if ancestor_ids else generation_id

        # Find descendant IDs
        descendant_ids = [gid for gid, pid in pairs.items() if pid == generation_id]

        # Fetch only required ancestor and descendant generation records
        needed_ids = set(ancestor_ids + descendant_ids + [generation_id])
        if not needed_ids:
            return {"root_id": root_id, "ancestors": [], "descendants": []}

        placeholders = ", ".join(["?"] * len(needed_ids))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT * FROM generations WHERE id IN ({placeholders})",
                list(needed_ids),
            ) as cursor:
                fetched_rows = {
                    row["id"]: self._normalize_generation_row(dict(row))
                    for row in await cursor.fetchall()
                }

        # Compute accurate accumulated costs along root -> ancestor chain
        ordered_chain = [root_id] + [aid for aid in reversed(ancestor_ids) if aid != root_id]
        running_cost = 0.0
        running_toks = 0
        for cid in ordered_chain:
            if cid in fetched_rows:
                running_cost += fetched_rows[cid].get("cost_usd", 0.0)
                running_toks += fetched_rows[cid].get("tokens", 0)
                if not fetched_rows[cid].get("accumulated_cost_usd"):
                    fetched_rows[cid]["accumulated_cost_usd"] = round(running_cost, 6)
                    fetched_rows[cid]["accumulated_tokens"] = running_toks

        ancestors = [fetched_rows[aid] for aid in reversed(ancestor_ids) if aid in fetched_rows]
        descendants = [fetched_rows[did] for did in descendant_ids if did in fetched_rows]

        return {
            "root_id": root_id,
            "ancestors": ancestors,
            "descendants": descendants,
        }

    async def create_conversation(self, conv_id: str, baseline_generation_id: str, moodboard_id: str = None) -> None:
        logger.info(f"Creating conversation {conv_id} for baseline {baseline_generation_id}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO conversations (id, baseline_generation_id, moodboard_id) VALUES (?, ?, ?)",
                (conv_id, baseline_generation_id, moodboard_id),
            )
            await db.commit()

    async def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def list_conversation_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM generations WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC",
                (conv_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._normalize_generation_row(dict(row)) for row in rows]

    def _normalize_wardrobe_row(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(data.get("bbox_json"), str):
            try:
                data["bbox"] = json.loads(data["bbox_json"])
            except Exception:
                data["bbox"] = None
        else:
            data["bbox"] = data.get("bbox_json")

        if isinstance(data.get("extracted_details_json"), str):
            try:
                data["extracted_details"] = json.loads(data["extracted_details_json"])
            except Exception:
                data["extracted_details"] = None
        elif isinstance(data.get("extracted_details_json"), dict):
            data["extracted_details"] = data.get("extracted_details_json")
        else:
            data["extracted_details"] = data.get("extracted_details")

        if not data.get("upscale_status"):
            data["upscale_status"] = "completed" if data.get("upscaled_image_path") else "pending"
        data["is_upscaled"] = bool(data.get("upscaled_image_path") and data.get("upscale_status") == "completed")
        data["cost_usd"] = float(data.get("cost_usd") or 0.0)
        data["tokens"] = int(data.get("tokens") or 0)
        return data

    async def create_wardrobe_item(self, item_data: Dict[str, Any]) -> None:
        logger.info(f"Creating wardrobe item {item_data['id']}: {item_data.get('label')}")
        bbox_val = item_data.get("bbox_json")
        if isinstance(bbox_val, (list, dict)):
            bbox_val = json.dumps(bbox_val)

        extracted_val = item_data.get("extracted_details_json") or item_data.get("extracted_details")
        if isinstance(extracted_val, dict):
            extracted_val = json.dumps(extracted_val)

        cost_usd = float(item_data.get("cost_usd") or 0.0)
        tokens = int(item_data.get("tokens") or 0)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO wardrobe_items (
                    id, source_image_path, label, category, cropped_image_path,
                    upscaled_image_path, upscale_status, upscale_error, bbox_json, extracted_details_json,
                    cost_usd, tokens, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (
                    item_data["id"],
                    item_data["source_image_path"],
                    item_data["label"],
                    item_data.get("category", "tops"),
                    item_data["cropped_image_path"],
                    item_data.get("upscaled_image_path"),
                    item_data.get("upscale_status", "pending"),
                    item_data.get("upscale_error"),
                    bbox_val,
                    extracted_val,
                    cost_usd,
                    tokens,
                    item_data.get("created_at"),
                ),
            )
            await db.commit()

    async def update_wardrobe_item_details(
        self,
        item_id: str,
        extracted_details: Dict[str, Any],
        cost_usd: Optional[float] = None,
        tokens: Optional[int] = None,
    ) -> bool:
        logger.info(f"Updating wardrobe item {item_id} extracted details")
        extracted_val = json.dumps(extracted_details) if isinstance(extracted_details, dict) else extracted_details
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE wardrobe_items
                SET extracted_details_json = ?,
                    cost_usd = CASE WHEN ? IS NOT NULL THEN cost_usd + ? ELSE cost_usd END,
                    tokens = CASE WHEN ? IS NOT NULL THEN tokens + ? ELSE tokens END
                WHERE id = ? AND deleted_at IS NULL
                """,
                (extracted_val, cost_usd, cost_usd or 0.0, tokens, tokens or 0, item_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_wardrobe_item_upscale(
        self,
        item_id: str,
        upscaled_image_path: Optional[str],
        upscale_status: str = "completed",
        upscale_error: Optional[str] = None,
        cost_usd: Optional[float] = None,
        tokens: Optional[int] = None,
    ) -> bool:
        logger.info(f"Updating wardrobe item {item_id} upscale status to '{upscale_status}' (cost_usd={cost_usd}, tokens={tokens})")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE wardrobe_items
                SET upscaled_image_path = COALESCE(?, upscaled_image_path),
                    upscale_status = ?,
                    upscale_error = ?,
                    cost_usd = CASE WHEN ? IS NOT NULL THEN cost_usd + ? ELSE cost_usd END,
                    tokens = CASE WHEN ? IS NOT NULL THEN tokens + ? ELSE tokens END
                WHERE id = ? AND deleted_at IS NULL
                """,
                (
                    upscaled_image_path,
                    upscale_status,
                    upscale_error,
                    cost_usd,
                    cost_usd or 0.0,
                    tokens,
                    tokens or 0,
                    item_id,
                ),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_wardrobe_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE id = ? AND deleted_at IS NULL",
                (item_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._normalize_wardrobe_row(dict(row))
                return None

    async def list_wardrobe_items(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE deleted_at IS NULL ORDER BY created_at DESC, rowid DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._normalize_wardrobe_row(dict(row)) for row in rows]

    async def delete_wardrobe_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"Deleting wardrobe item {item_id} and associated composition assignments")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE id = ? AND deleted_at IS NULL",
                (item_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                item_data = self._normalize_wardrobe_row(dict(row))

            await db.execute(
                "DELETE FROM composition_assignments WHERE wardrobe_item_id = ?",
                (item_id,),
            )
            await db.execute(
                "UPDATE wardrobe_items SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (item_id,),
            )
            await db.commit()
            return item_data

    async def delete_all_wardrobe_items(self) -> List[Dict[str, Any]]:
        logger.info("Deleting all wardrobe items and associated composition assignments")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE deleted_at IS NULL"
            ) as cursor:
                rows = await cursor.fetchall()
                items = [self._normalize_wardrobe_row(dict(row)) for row in rows]

            await db.execute("DELETE FROM composition_assignments")
            await db.execute(
                "UPDATE wardrobe_items SET deleted_at = CURRENT_TIMESTAMP WHERE deleted_at IS NULL"
            )
            await db.commit()
            return items


    async def create_composition_assignment(self, assignment_data: Dict[str, Any]) -> None:
        logger.info(f"Recording composition assignment for generation {assignment_data.get('generation_id')}")
        drop_pos = assignment_data.get("drop_position")
        if isinstance(drop_pos, dict):
            drop_pos = json.dumps(drop_pos)

        region_bbox = assignment_data.get("region_bbox")
        if isinstance(region_bbox, (list, dict)):
            region_bbox = json.dumps(region_bbox)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO composition_assignments (
                    id, generation_id, wardrobe_item_id, pin_number,
                    drop_position_json, target_description, region_bbox_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment_data["id"],
                    assignment_data["generation_id"],
                    assignment_data["wardrobe_item_id"],
                    assignment_data["pin_number"],
                    drop_pos,
                    assignment_data.get("target_description"),
                    region_bbox,
                ),
            )
            await db.commit()

    async def list_composition_assignments(self, generation_id: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT ca.*, wi.label as wardrobe_label, wi.cropped_image_path
                FROM composition_assignments ca
                LEFT JOIN wardrobe_items wi ON ca.wardrobe_item_id = wi.id
                WHERE ca.generation_id = ?
                ORDER BY ca.pin_number ASC
                """,
                (generation_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    if isinstance(data.get("drop_position_json"), str):
                        try:
                            data["drop_position"] = json.loads(data["drop_position_json"])
                        except Exception:
                            data["drop_position"] = None
                    if isinstance(data.get("region_bbox_json"), str):
                        try:
                            data["region_bbox"] = json.loads(data["region_bbox_json"])
                        except Exception:
                            data["region_bbox"] = None
                    results.append(data)
                return results

    async def get_tables_summary(self) -> Dict[str, Any]:
        """Returns row counts and column names for all database tables."""
        allowed_tables = [
            "generations",
            "moodboards",
            "conversations",
            "wardrobe_items",
            "composition_assignments",
        ]
        summary = {}
        async with aiosqlite.connect(self.db_path) as db:
            for table in allowed_tables:
                try:
                    async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                        row = await cursor.fetchone()
                        count = row[0] if row else 0
                    async with db.execute(f"PRAGMA table_info({table})") as cursor:
                        cols = [{"name": r[1], "type": r[2]} for r in await cursor.fetchall()]
                    summary[table] = {"row_count": count, "columns": cols}
                except Exception as err:
                    logger.warning(f"Failed to inspect table {table}: {err}")
                    summary[table] = {"row_count": 0, "columns": []}
        return summary

    async def get_table_records(
        self,
        table_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Safely queries paginated rows from a database table."""
        allowed_tables = [
            "generations",
            "moodboards",
            "conversations",
            "wardrobe_items",
            "composition_assignments",
        ]
        if table_name not in allowed_tables:
            raise ValueError(f"Invalid or unauthorized table name '{table_name}'.")

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(f"SELECT COUNT(*) FROM {table_name}") as cursor:
                total_row = await cursor.fetchone()
                total = total_row[0] if total_row else 0

            query = f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT ? OFFSET ?"
            async with db.execute(query, (limit, offset)) as cursor:
                raw_rows = await cursor.fetchall()
                rows = []
                for r in raw_rows:
                    row_dict = dict(r)
                    # For generations table, normalize schema/prompt fields
                    if table_name == "generations":
                        row_dict = self._normalize_generation_row(row_dict)
                    rows.append(row_dict)

            return {
                "table": table_name,
                "total": total,
                "limit": limit,
                "offset": offset,
                "rows": rows,
            }


