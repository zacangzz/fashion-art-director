import pytest
import pytest_asyncio
import aiosqlite
import os
import json
from app.db.database import DatabaseManager

@pytest.fixture
def test_db_path(tmp_path):
    db_file = tmp_path / "test_studio.db"
    return str(db_file)

@pytest.mark.asyncio
async def test_init_db(test_db_path):
    db_mgr = DatabaseManager(test_db_path)
    await db_mgr.init_db()

    async with aiosqlite.connect(test_db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
            tables = [row[0] for row in await cursor.fetchall()]
            assert "moodboards" in tables
            assert "generations" in tables

@pytest.mark.asyncio
async def test_moodboard_crud(test_db_path):
    db_mgr = DatabaseManager(test_db_path)
    await db_mgr.init_db()

    mb_id = "mb_test_123"
    paths = ["storage/moodboards/img1.png", "storage/moodboards/img2.png"]
    await db_mgr.create_moodboard(mb_id, paths)

    mb = await db_mgr.get_moodboard(mb_id)
    assert mb is not None
    assert mb["id"] == mb_id
    assert mb["image_paths"] == paths

@pytest.mark.asyncio
async def test_generation_crud_and_lineage(test_db_path):
    db_mgr = DatabaseManager(test_db_path)
    await db_mgr.init_db()

    # Create root baseline
    base_data = {
        "id": "gen_base_01",
        "parent_id": None,
        "moodboard_id": "mb_test_123",
        "is_baseline": True,
        "schema_json": json.dumps({"intent": {"primary_goal": "baseline goal"}}),
        "compiled_prompt": "baseline prompt",
        "negative_prompt": "blurry",
        "seed": 918231,
        "master_image_path": "storage/generations/gen_base_01_master.png",
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    }
    await db_mgr.create_generation(base_data)

    # Create child fine-tuned iteration
    child_data = {
        "id": "gen_child_02",
        "parent_id": "gen_base_01",
        "moodboard_id": "mb_test_123",
        "is_baseline": False,
        "schema_json": json.dumps({"intent": {"primary_goal": "fine-tuned goal"}}),
        "compiled_prompt": "child prompt",
        "negative_prompt": "blurry",
        "seed": 918231,
        "master_image_path": "storage/generations/gen_child_02_master.png",
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    }
    await db_mgr.create_generation(child_data)

    # Test get_generation
    gen = await db_mgr.get_generation("gen_base_01")
    assert gen is not None
    assert gen["id"] == "gen_base_01"
    assert gen["is_baseline"] in (1, True)
    assert gen["seed"] == 918231
    assert isinstance(gen["schema_json"], dict)
    assert gen["schema_json"]["intent"]["primary_goal"] == "baseline goal"

    # Test list_generations
    all_gens = await db_mgr.list_generations()
    assert len(all_gens) == 2
    assert all_gens[0]["id"] == "gen_child_02"

    # Test get_lineage for child
    lineage = await db_mgr.get_lineage("gen_child_02")
    assert lineage["root_id"] == "gen_base_01"
    assert len(lineage["ancestors"]) == 1
    assert lineage["ancestors"][0]["id"] == "gen_base_01"

@pytest.mark.asyncio
async def test_legacy_schema_backward_compatibility(test_db_path):
    """
    Verifies that DatabaseManager gracefully handles a database with legacy NOT NULL columns
    (prompt, tags_snapshot) without failing NOT NULL constraints.
    """
    # Create legacy table structure manually
    async with aiosqlite.connect(test_db_path) as db:
        await db.execute("""
        CREATE TABLE generations (
            id TEXT PRIMARY KEY,
            parent_id TEXT NULL,
            moodboard_id TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            prompt TEXT NOT NULL,
            negative_prompt TEXT,
            seed INTEGER NOT NULL,
            tags_snapshot TEXT NOT NULL,
            master_image_path TEXT NOT NULL,
            resolution_width INTEGER NOT NULL,
            resolution_height INTEGER NOT NULL
        );
        """)
        await db.commit()

    db_mgr = DatabaseManager(test_db_path)
    await db_mgr.init_db()

    # Insert modern baseline record into legacy database
    gen_data = {
        "id": "gen_legacy_compat_01",
        "parent_id": None,
        "moodboard_id": "mb_legacy",
        "is_baseline": True,
        "schema_json": {"intent": {"primary_goal": "legacy test"}},
        "compiled_prompt": "legacy test prompt",
        "negative_prompt": "ugly",
        "seed": 777777,
        "master_image_path": "storage/generations/test.png",
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    }

    # Should succeed without NOT NULL constraint error
    await db_mgr.create_generation(gen_data)

    rec = await db_mgr.get_generation("gen_legacy_compat_01")
    assert rec is not None
    assert rec["id"] == "gen_legacy_compat_01"
    assert rec["compiled_prompt"] == "legacy test prompt"
    assert rec["is_baseline"] is True
