from app.schemas.domain import (
    BaselineSummary,
    FineTuneGenerationRequest,
    GenerationRecordResponse,
    SceneSchema,
)


def test_scene_schema_preserves_sparse_refined_payload():
    payload = {
        "schema_version": "1.0",
        "metadata": {"name": "Watch"},
        "canvas": {"orientation": "square"},
        "creative_direction": {"genre": "product_photography"},
        "style": {"primary_style": "minimalist_product"},
        "custom_section": {"note": "keep me"},
    }
    assert SceneSchema.model_validate(payload).model_dump() == payload


def test_scene_schema_preserves_legacy_payload_without_adding_defaults():
    payload = {"intent": {"primary_goal": "legacy campaign"}}
    assert SceneSchema.model_validate(payload).model_dump() == payload


def test_api_contract_models():
    baseline = BaselineSummary(
        id="gen_base_01",
        seed=918231,
        image_url="/api/images/gen_base_01.png",
        created_at="2026-08-24T09:30:00Z",
    )
    assert baseline.id == "gen_base_01"

    req = FineTuneGenerationRequest(
        parent_id="gen_base_01",
        schema=SceneSchema(),
        seed_mode="locked",
        seed=918231,
        use_image_reference=True,
    )
    assert req.parent_id == "gen_base_01"
    assert req.seed == 918231

    record = GenerationRecordResponse(
        id="gen_01",
        created_at="2026-08-24T09:30:00Z",
        schema_json={"intent": {"primary_goal": "test"}},
        compiled_prompt="test prompt",
        negative_prompt="test neg",
        seed=123,
        master_image_url="/api/images/gen_01.png",
        aspect_ratio="2:3",
        resolution_width=1080,
        resolution_height=1620,
    )
    assert record.id == "gen_01"
    assert record.schema_dict["intent"]["primary_goal"] == "test"
