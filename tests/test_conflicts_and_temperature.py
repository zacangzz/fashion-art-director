import io
import pytest
from unittest.mock import MagicMock
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.utils.image_utils import optimize_reference_image, to_image_part
from app.schemas.domain import PromptConflict, GenerateBaselinesRequest
from app.dependencies import get_vision_service


def _create_sample_png_bytes(width: int = 3000, height: int = 2000) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_optimize_reference_image_reduces_size():
    raw_png = _create_sample_png_bytes(width=3000, height=2000)
    assert len(raw_png) > 0

    opt_bytes, mime = optimize_reference_image(raw_png, max_dimension=1024, target_format="WEBP", quality=85)
    assert mime == "image/webp"
    assert len(opt_bytes) < len(raw_png)

    pil_opt = Image.open(io.BytesIO(opt_bytes))
    assert pil_opt.width <= 1024
    assert pil_opt.height <= 1024


def test_optimize_reference_image_skips_pdf():
    pdf_bytes = b"%PDF-1.5 fake pdf bytes"
    opt_bytes, mime = optimize_reference_image(pdf_bytes)
    assert opt_bytes == pdf_bytes
    assert mime == "application/pdf"


def test_check_conflicts_endpoint_success():
    mock_conflicts = [
        {
            "id": "conflict_1",
            "severity": "warning",
            "conflicting_elements": ["harsh afternoon sunlight", "soft studio strobe"],
            "categories": ["lighting"],
            "explanation": "Contradictory lighting setups.",
            "recommendation": "Use single lighting source.",
        }
    ]

    mock_vision = MagicMock()
    mock_vision.check_prompt_conflicts.return_value = mock_conflicts
    app.dependency_overrides[get_vision_service] = lambda: mock_vision

    client = TestClient(app)
    payload = {
        "master_prompt": "A model standing under harsh afternoon sunlight in soft studio strobe setup.",
        "narrative": "Studio portrait",
        "categories": {
            "lighting": [{"label": "harsh afternoon sunlight"}, {"label": "soft studio strobe"}]
        }
    }
    response = client.post("/api/moodboard/check-conflicts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["id"] == "conflict_1"
    assert data["conflicts"][0]["severity"] == "warning"

    app.dependency_overrides.clear()
