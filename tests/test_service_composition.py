import io
import unittest.mock
import pytest
from PIL import Image
from unittest.mock import MagicMock

from app.db.database import FirestoreManager
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from app.services.vision_service import VisionService
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.services.export_service import ExportService
from app.utils.telemetry import TelemetryLogger
from fake_firestore import FakeFirestoreClient


def test_service_composition_unidirectional_dag():
    """
    Step 7 verification test:
    Validates that ImageGenerator, VisionService, WardrobeService, GenerationService,
    and ExportService can be instantiated and composed cleanly without circular references.
    """
    fake_db_client = FakeFirestoreClient()
    db_manager = FirestoreManager(fake_db_client)

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.generate_signed_url.return_value = "https://storage.googleapis.com/fake-bucket/fake.png"
    fake_blob.download_as_bytes.return_value = b"fake_bytes"
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    fake_gemini_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_text = '{"master_prompt": "Editorial fashion shoot", "narrative": "A high fashion scene", "categories": {}}'
    mock_interaction.text = mock_interaction.output_text
    fake_gemini_client.interactions.create.return_value = mock_interaction

    telemetry = TelemetryLogger(db=fake_db_client, component="test")

    # 1. ImageGenerator depends only on Client + Telemetry
    image_generator = ImageGenerator(
        client=fake_gemini_client,
        default_model="gemini-3.1-flash-image",
        telemetry=telemetry,
    )

    # 2. VisionService depends on Client + Telemetry
    vision_service = VisionService(
        api_key="fake-key",
        client=fake_gemini_client,
        telemetry=telemetry,
    )

    # 3. WardrobeService depends on DB + Storage + ImageGenerator
    wardrobe_service = WardrobeService(
        db_manager=db_manager,
        storage_service=storage_service,
        api_key="fake-key",
        client=fake_gemini_client,
        image_generator=image_generator,
        telemetry=telemetry,
    )
    assert not hasattr(wardrobe_service, "set_generation_service")

    # 4. GenerationService depends on DB + Storage + ImageGenerator + WardrobeService
    generation_service = GenerationService(
        db_manager=db_manager,
        storage_service=storage_service,
        api_key="fake-key",
        client=fake_gemini_client,
        image_generator=image_generator,
        wardrobe_service=wardrobe_service,
        telemetry=telemetry,
    )

    # 5. ExportService depends on DB + Storage + ImageGenerator
    export_service = ExportService(
        db_manager=db_manager,
        storage_service=storage_service,
        image_generator=image_generator,
    )

    assert export_service.db is db_manager
    assert export_service.storage_service is storage_service
    assert export_service.image_generator is image_generator


def test_generation_and_export_flow():
    """
    Verifies that GenerationService can create a baseline and ExportService can bundle presets.
    """
    fake_db_client = FakeFirestoreClient()
    db_manager = FirestoreManager(fake_db_client)

    # Create dummy 100x100 PNG
    dummy_img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    dummy_img.save(buf, format="PNG")
    dummy_bytes = buf.getvalue()

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.generate_signed_url.return_value = "https://storage.googleapis.com/test/img.png"
    fake_blob.download_as_bytes.return_value = dummy_bytes
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    fake_gemini_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image = MagicMock(data=dummy_bytes)
    mock_interaction.output_text = "prompt text"
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100, total_token_count=200)
    fake_gemini_client.interactions.create.return_value = mock_interaction

    image_generator = ImageGenerator(client=fake_gemini_client)
    generation_service = GenerationService(
        db_manager=db_manager,
        storage_service=storage_service,
        api_key="fake-key",
        client=fake_gemini_client,
        image_generator=image_generator,
    )
    export_service = ExportService(
        db_manager=db_manager,
        storage_service=storage_service,
        image_generator=image_generator,
    )

    # Test baseline generation
    res = generation_service.generate_single_baseline(
        moodboard_id="mb_123",
        state_dict={"narrative": "A test scene", "categories": {}},
        positive_prompt="A test photo",
        negative_prompt="",
        seed=12345,
        user_id="user_test",
    )
    assert res["id"].startswith("gen_base_")
    assert res["accumulated_cost_usd"] > 0

    # Test export bundling
    zip_bytes = export_service.bundle_export_presets(
        generation_id=res["id"],
        export_format="PNG",
        user_id="user_test",
    )
    assert len(zip_bytes) > 0
    assert zip_bytes.startswith(b"PK")  # ZIP magic header
