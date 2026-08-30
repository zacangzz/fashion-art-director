import os
import pytest
from app.utils.pricing import extract_usage_metadata, calculate_cost, MODEL_PRICING
from app.db.database import DatabaseManager


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
    # gemini-3.7-flash: prompt = $0.10/M tokens, candidates = $0.40/M tokens
    # 1000 * 0.0000001 = 0.0001, 1000 * 0.0000004 = 0.0004 -> total 0.0005
    assert cost_info["breakdown"]["prompt_cost_usd"] == 0.0001
    assert cost_info["breakdown"]["candidates_cost_usd"] == 0.0004
    assert cost_info["cost_usd"] == 0.0005
    assert cost_info["total_tokens"] == 2000


def test_calculate_cost_image_model():
    cost_info = calculate_cost(
        model="gemini-3-pro-image",
        prompt_tokens=100,
        candidates_tokens=0,
        images_count=1,
    )
    assert cost_info["breakdown"]["images_cost_usd"] == 0.04
    assert cost_info["cost_usd"] >= 0.04


@pytest.mark.asyncio
async def test_db_multi_step_lineage_accumulation(tmp_path):
    db_file = str(tmp_path / "test_lineage_cost.db")
    db = DatabaseManager(db_file)
    await db.init_db()

    # Step 1: Baseline Image
    base_record = {
        "id": "gen_base_100",
        "parent_id": None,
        "moodboard_id": "mb_1",
        "is_baseline": True,
        "created_at": "2026-08-30T10:00:00Z",
        "schema_json": {},
        "compiled_prompt": "A stylish fashion model in urban setting",
        "negative_prompt": "blurry",
        "seed": 1001,
        "master_image_path": "/tmp/gen_base_100.png",
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
        "model_name": "gemini-3-pro-image",
        "cost_usd": 0.0401,
        "tokens": 120,
        "accumulated_cost_usd": 0.0401,
        "accumulated_tokens": 120,
    }
    await db.create_generation(base_record)

    # Step 2: Fine-Tuning Iteration
    iter_record = {
        "id": "gen_iter_200",
        "parent_id": "gen_base_100",
        "moodboard_id": "mb_1",
        "is_baseline": False,
        "created_at": "2026-08-30T10:01:00Z",
        "schema_json": {},
        "compiled_prompt": "A stylish fashion model with red jacket",
        "negative_prompt": "blurry",
        "seed": 1002,
        "master_image_path": "/tmp/gen_iter_200.png",
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
        "model_name": "gemini-3-pro-image",
        "cost_usd": 0.0402,
        "tokens": 150,
        "accumulated_cost_usd": 0.0803,
        "accumulated_tokens": 270,
    }
    await db.create_generation(iter_record)

    # Step 3: Refinement / Inpaint
    refine_record = {
        "id": "gen_refine_300",
        "parent_id": "gen_iter_200",
        "moodboard_id": "mb_1",
        "is_baseline": False,
        "created_at": "2026-08-30T10:02:00Z",
        "schema_json": {},
        "compiled_prompt": "[Inpaint] Fix sunglasses reflections",
        "negative_prompt": "blurry",
        "seed": 1003,
        "master_image_path": "/tmp/gen_refine_300.png",
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
        "model_name": "gemini-3-pro-image",
        "cost_usd": 0.0405,
        "tokens": 210,
        "accumulated_cost_usd": 0.1208,
        "accumulated_tokens": 480,
    }
    await db.create_generation(refine_record)

    # Check direct record retrieval
    rec3 = await db.get_generation("gen_refine_300")
    assert rec3["cost_usd"] == 0.0405
    assert rec3["accumulated_cost_usd"] == 0.1208
    assert rec3["tokens"] == 210
    assert rec3["accumulated_tokens"] == 480

    # Check lineage tree
    lineage = await db.get_lineage("gen_refine_300")
    assert lineage["root_id"] == "gen_base_100"
    assert len(lineage["ancestors"]) == 2
    assert lineage["ancestors"][0]["id"] == "gen_base_100"
    assert lineage["ancestors"][0]["accumulated_cost_usd"] == 0.0401
    assert lineage["ancestors"][1]["id"] == "gen_iter_200"
    assert lineage["ancestors"][1]["accumulated_cost_usd"] == 0.0803
