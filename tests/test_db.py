from datetime import datetime, timezone
import pytest
from google.cloud.firestore import Increment
from app.db.database import FirestoreManager

from fake_firestore import FakeFirestoreClient


@pytest.fixture
def fake_firestore():
    return FakeFirestoreClient()


@pytest.fixture
def db_manager(fake_firestore):
    return FirestoreManager(fake_firestore)


# =============================================================================
# TESTS
# =============================================================================

def test_firestore_moodboard_crud(db_manager):
    user_id = "user_1"
    mb_id = "mb_test_100"
    created = db_manager.create_moodboard(user_id, mb_id, ["path1.png", "path2.png"])
    assert created["id"] == mb_id
    assert created["user_id"] == user_id
    assert created["cost_usd"] == 0.0

    # Add cost
    db_manager.add_moodboard_cost(mb_id, cost_usd=0.05, tokens=150)
    fetched = db_manager.get_moodboard(mb_id)
    assert fetched is not None
    assert fetched["cost_usd"] == 0.05
    assert fetched["tokens"] == 150
    assert fetched["accumulated_cost_usd"] == 0.05


def test_firestore_generation_lineage_precomputation(db_manager):
    user_id = "user_1"
    # 1. Create parent baseline
    parent = db_manager.create_generation(
        user_id,
        {
            "id": "gen_parent",
            "is_baseline": True,
            "seed": 42,
            "master_image_path": "user_1/generations/parent.png",
            "cost_usd": 0.05,
            "tokens": 100,
        },
    )
    assert parent["accumulated_cost_usd"] == 0.05
    assert parent["accumulated_tokens"] == 100

    # 2. Create child generation referencing parent
    child = db_manager.create_generation(
        user_id,
        {
            "id": "gen_child",
            "parent_id": "gen_parent",
            "seed": 43,
            "master_image_path": "user_1/generations/child.png",
            "cost_usd": 0.03,
            "tokens": 50,
        },
    )
    assert child["accumulated_cost_usd"] == 0.08
    assert child["accumulated_tokens"] == 150

    # 3. Verify lineage resolution
    lineage = db_manager.get_lineage("gen_child")
    assert lineage["root_id"] == "gen_parent"
    assert len(lineage["ancestors"]) == 1
    assert lineage["ancestors"][0]["id"] == "gen_parent"


def test_firestore_user_isolation(db_manager):
    db_manager.create_generation(
        "user_A",
        {"id": "gen_A", "seed": 1, "master_image_path": "pathA.png", "created_at": "2026-09-01T10:00:00Z"},
    )
    db_manager.create_generation(
        "user_B",
        {"id": "gen_B", "seed": 2, "master_image_path": "pathB.png", "created_at": "2026-09-01T11:00:00Z"},
    )

    user_A_gens = db_manager.list_generations("user_A")
    user_B_gens = db_manager.list_generations("user_B")

    assert len(user_A_gens) == 1
    assert user_A_gens[0]["id"] == "gen_A"
    assert len(user_B_gens) == 1
    assert user_B_gens[0]["id"] == "gen_B"


def test_firestore_wardrobe_soft_delete(db_manager):
    user_id = "user_1"
    item = db_manager.create_wardrobe_item(
        user_id,
        {
            "id": "wardrobe_1",
            "source_image_path": "source.png",
            "label": "Silk Blouse",
            "cropped_image_path": "crop.png",
        },
    )
    assert item["id"] == "wardrobe_1"

    # Should be in active list
    active = db_manager.list_wardrobe_items(user_id)
    assert len(active) == 1

    # Soft delete
    deleted = db_manager.delete_wardrobe_item("wardrobe_1")
    assert deleted is not None

    # Should no longer be in active list or get_wardrobe_item
    assert len(db_manager.list_wardrobe_items(user_id)) == 0
    assert db_manager.get_wardrobe_item("wardrobe_1") is None


def test_firestore_composition_assignment_resolution(db_manager):
    user_id = "user_1"
    db_manager.create_wardrobe_item(
        user_id,
        {
            "id": "w_item_1",
            "source_image_path": "source.png",
            "label": "Velvet Blazer",
            "cropped_image_path": "user_1/wardrobe/items/crop_1.png",
        },
    )

    db_manager.create_composition_assignment(
        user_id,
        {
            "id": "ca_1",
            "generation_id": "gen_100",
            "wardrobe_item_id": "w_item_1",
            "pin_number": 1,
            "drop_position": {"x": 0.5, "y": 0.5},
            "target_description": "Wear the blazer",
        },
    )

    assignments = db_manager.list_composition_assignments("gen_100")
    assert len(assignments) == 1
    assert assignments[0]["wardrobe_label"] == "Velvet Blazer"
    assert assignments[0]["cropped_image_path"] == "user_1/wardrobe/items/crop_1.png"
    assert assignments[0]["pin_number"] == 1


def test_tables_summary_and_pagination(db_manager):
    user_id = "user_1"
    for i in range(15):
        db_manager.create_generation(
            user_id,
            {"id": f"gen_page_{i}", "seed": i, "master_image_path": f"p_{i}.png"},
        )

    summary = db_manager.get_tables_summary()
    assert "generations" in summary
    assert summary["generations"]["row_count"] == 15

    # Page 1: 10 items
    p1 = db_manager.get_table_records("generations", limit=10)
    assert len(p1["rows"]) == 10
    assert p1["next_cursor"] is not None

    # Page 2: next items
    p2 = db_manager.get_table_records("generations", limit=10, start_after_id=p1["next_cursor"])
    assert len(p2["rows"]) == 5
    assert p2["next_cursor"] is None
