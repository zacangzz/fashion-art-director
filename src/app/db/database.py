import json
import sqlite3
import aiosqlite
from typing import List, Dict, Any, Optional
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
    bbox_json TEXT,
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
    FOREIGN KEY(parent_id) REFERENCES generations(id),
    FOREIGN KEY(moodboard_id) REFERENCES moodboards(id)
);
"""

class DatabaseManager:
    def __init__(self, db_path: str = "./studio.db"):
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        self.db_path = db_path

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

        # Ensure is_baseline is bool
        data["is_baseline"] = bool(data.get("is_baseline", False))
        return data


    async def create_generation(self, gen_data: Dict[str, Any]) -> None:
        """
        Dynamically inspects existing table columns to support both modern and legacy schemas
        without NOT NULL constraint failures.
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

        async with aiosqlite.connect(self.db_path) as db:
            # Query existing table columns
            async with db.execute("PRAGMA table_info(generations)") as cursor:
                table_columns = {row[1] for row in await cursor.fetchall()}

            # Build insert map based on existing columns in the table
            insert_fields = {
                "id": gen_data["id"],
                "parent_id": gen_data.get("parent_id"),
                "moodboard_id": gen_data.get("moodboard_id"),
                "is_baseline": 1 if gen_data.get("is_baseline", False) else 0,
                "negative_prompt": gen_data.get("negative_prompt", "") or "",
                "seed": gen_data["seed"],
                "master_image_path": gen_data["master_image_path"],
                "aspect_ratio": gen_data.get("aspect_ratio", "2:3"),
                "resolution_width": gen_data.get("resolution_width", 1440),
                "resolution_height": gen_data.get("resolution_height", 1440),
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

            logger.info(f"Inserting generation record {gen_data['id']} (is_baseline={gen_data.get('is_baseline', False)}, seed={gen_data['seed']})")
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
                return [self._normalize_generation_row(dict(row)) for row in rows]

    async def get_lineage(self, generation_id: str) -> Dict[str, Any]:
        """
        Traces ancestor chain up to the root baseline, and finds direct descendants.
        """
        all_gens = await self.list_generations()
        gen_map = {g["id"]: g for g in all_gens}

        current = gen_map.get(generation_id)
        if not current:
            return {"root_id": generation_id, "ancestors": [], "descendants": []}

        # Find ancestors
        ancestors = []
        curr_parent_id = current.get("parent_id")
        while curr_parent_id and curr_parent_id in gen_map:
            parent = gen_map[curr_parent_id]
            ancestors.append(parent)
            curr_parent_id = parent.get("parent_id")

        root_id = ancestors[-1]["id"] if ancestors else current["id"]

        # Find descendants
        descendants = [g for g in all_gens if g.get("parent_id") == generation_id]

        return {
            "root_id": root_id,
            "ancestors": list(reversed(ancestors)),
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

    async def create_wardrobe_item(self, item_data: Dict[str, Any]) -> None:
        logger.info(f"Creating wardrobe item {item_data['id']}: {item_data.get('label')}")
        bbox_val = item_data.get("bbox_json")
        if isinstance(bbox_val, (list, dict)):
            bbox_val = json.dumps(bbox_val)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO wardrobe_items (id, source_image_path, label, category, cropped_image_path, bbox_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (
                    item_data["id"],
                    item_data["source_image_path"],
                    item_data["label"],
                    item_data.get("category", "tops"),
                    item_data["cropped_image_path"],
                    bbox_val,
                    item_data.get("created_at"),
                ),
            )
            await db.commit()

    async def get_wardrobe_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE id = ? AND deleted_at IS NULL",
                (item_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = dict(row)
                    if isinstance(data.get("bbox_json"), str):
                        try:
                            data["bbox"] = json.loads(data["bbox_json"])
                        except Exception:
                            data["bbox"] = None
                    return data
                return None

    async def list_wardrobe_items(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM wardrobe_items WHERE deleted_at IS NULL ORDER BY created_at DESC, rowid DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    if isinstance(data.get("bbox_json"), str):
                        try:
                            data["bbox"] = json.loads(data["bbox_json"])
                        except Exception:
                            data["bbox"] = None
                    results.append(data)
                return results

    async def delete_wardrobe_item(self, item_id: str) -> bool:
        logger.info(f"Soft-deleting wardrobe item {item_id}")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE wardrobe_items SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND deleted_at IS NULL",
                (item_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_all_wardrobe_items(self) -> int:
        logger.info("Soft-deleting all wardrobe items")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE wardrobe_items SET deleted_at = CURRENT_TIMESTAMP WHERE deleted_at IS NULL"
            )
            await db.commit()
            return cursor.rowcount


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

