import os
import pytest
from app.utils.pricing import extract_usage_metadata, calculate_cost, MODEL_PRICING
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


def test_extract_usage_metadata_from_object():
    class DummyUsage:
        prompt_token_count = 120
        candidates_token_count = 45
        total_token_count = 165

    class DummyResponse:
        usage_metadata = DummyUsage()

    usage = extract_usage_metadata(DummyResponse())
    assert usage["prompt_token_count"] == 120
    assert usage["candidates_token_count"] == 45
    assert usage["total_token_count"] == 165


def test_extract_usage_metadata_from_dict():
    resp_dict = {
        "usage_metadata": {
            "prompt_token_count": 200,
            "candidates_token_count": 80,
            "total_token_count": 280,
        }
    }
    usage = extract_usage_metadata(resp_dict)
    assert usage["prompt_token_count"] == 200
    assert usage["candidates_token_count"] == 80
    assert usage["total_token_count"] == 280


def test_calculate_cost_text_model():
    cost_info = calculate_cost(
        model="gemini-3.7-flash",
        prompt_tokens=1000,
        candidates_tokens=1000,
    )
    assert cost_info["breakdown"]["prompt_cost_usd"] == 0.00075
    assert cost_info["breakdown"]["candidates_cost_usd"] == 0.00375
    assert cost_info["cost_usd"] == 0.0045
    assert cost_info["total_tokens"] == 2000


def test_calculate_cost_image_model():
    cost_info_4k = calculate_cost(
        model="gemini-3-pro-image",
        prompt_tokens=100,
        candidates_tokens=0,
        images_count=1,
        image_size="4K",
    )
    assert cost_info_4k["breakdown"]["images_cost_usd"] == 0.24
    assert cost_info_4k["cost_usd"] >= 0.24


def test_lineage_cost_accumulation():
    fake_db = FakeFirestoreClient()
    db = FirestoreManager(fake_db)

    # 1. Base generation
    base_gen = {
        "id": "gen_base_01",
        "parent_id": None,
        "moodboard_id": None,
        "is_baseline": True,
        "cost_usd": 0.04,
        "tokens": 1500,
        "master_image_path": "/tmp/base.png",
    }
    db.create_generation(user_id="local_dev_user", gen_data=base_gen)

    # 2. Child generation 1
    child_1 = {
        "id": "gen_child_01",
        "parent_id": "gen_base_01",
        "moodboard_id": None,
        "is_baseline": False,
        "cost_usd": 0.04,
        "tokens": 1600,
        "master_image_path": "/tmp/child1.png",
    }
    db.create_generation(user_id="local_dev_user", gen_data=child_1)

    rec_child_1 = db.get_generation("gen_child_01")
    assert rec_child_1["accumulated_cost_usd"] == 0.08
    assert rec_child_1["accumulated_tokens"] == 3100

    # 3. Child generation 2 (refinement of child 1)
    child_2 = {
        "id": "gen_child_02",
        "parent_id": "gen_child_01",
        "moodboard_id": None,
        "is_baseline": False,
        "cost_usd": 0.04,
        "tokens": 1700,
        "master_image_path": "/tmp/child2.png",
    }
    db.create_generation(user_id="local_dev_user", gen_data=child_2)

    rec_child_2 = db.get_generation("gen_child_02")
    assert rec_child_2["accumulated_cost_usd"] == 0.12
    assert rec_child_2["accumulated_tokens"] == 4800
