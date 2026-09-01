import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db_manager
from fake_firestore import FakeFirestoreClient
from app.db.database import FirestoreManager
from app.utils.telemetry import TelemetryLogger


@pytest.fixture
def client_with_db():
    fake_db_client = FakeFirestoreClient()
    db_manager = FirestoreManager(fake_db_client)

    app.dependency_overrides[get_db_manager] = lambda: db_manager

    # Seed sample telemetry event
    logger = TelemetryLogger(db=fake_db_client, component="generation")
    logger.record_event(
        event="baseline_generation",
        request_id="req_test_100",
        component="generation",
        status="success",
        duration_ms=450.0,
        cost_usd=0.04,
        tokens=1500,
        model="gemini-3.1-flash-image",
        prompts={"user_prompt": "Editorial fashion photography"},
        outputs={"image_urls": ["/api/images/test_gen.png"]},
    )

    yield TestClient(app), db_manager, fake_db_client
    app.dependency_overrides.clear()


def test_telemetry_stats_endpoint(client_with_db):
    client, _, _ = client_with_db
    res = client.get("/api/telemetry/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_events" in data
    assert "success_rate" in data
    assert "total_cost_usd" in data
    assert "components" in data
    assert data["total_events"] >= 1
    assert data["total_cost_usd"] == 0.04


def test_telemetry_runs_endpoint(client_with_db):
    client, _, _ = client_with_db
    res = client.get("/api/telemetry/runs?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["runs"]) >= 1
    run = data["runs"][0]
    assert run["request_id"] == "req_test_100"
    assert run["status"] == "success"
    assert "/api/images/test_gen.png" in run["output_images"]
    assert run["prompt"] == "Editorial fashion photography"


def test_telemetry_events_endpoint(client_with_db):
    client, _, _ = client_with_db
    res = client.get("/api/telemetry/events?component=generation")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["events"]) >= 1
    assert data["events"][0]["event"] == "baseline_generation"


def test_telemetry_request_trace_endpoint(client_with_db):
    client, _, _ = client_with_db
    res = client.get("/api/telemetry/events/req_test_100")
    assert res.status_code == 200
    trace = res.json()
    assert len(trace) >= 1
    assert trace[0]["request_id"] == "req_test_100"


def test_telemetry_system_logs_endpoint(client_with_db):
    client, _, _ = client_with_db
    res = client.get("/api/telemetry/logs?lines=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total_lines"] >= 1
    assert len(data["logs"]) >= 1


def test_telemetry_db_summary_and_records_endpoint(client_with_db):
    client, db_manager, _ = client_with_db
    # Seed a generation doc
    db_manager.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_rec_1",
            "prompt": "Vogue editorial",
            "cost_usd": 0.04,
            "tokens": 500,
        },
    )

    # 1. Summary
    res_summary = client.get("/api/telemetry/db/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()["tables"]
    assert "generations" in summary
    assert summary["generations"]["row_count"] >= 1

    # 2. Table records with offset
    res_records = client.get("/api/telemetry/db/generations?limit=10&offset=0")
    assert res_records.status_code == 200
    records = res_records.json()
    assert records["table"] == "generations"
    assert len(records["rows"]) >= 1
    assert records["rows"][0]["id"] == "gen_rec_1"

    # 3. Invalid table name
    res_invalid = client.get("/api/telemetry/db/unknown_secret_table")
    assert res_invalid.status_code == 400
