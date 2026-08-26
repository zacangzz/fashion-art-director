import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.utils.telemetry import (
    TelemetryLogger,
    query_audit_events,
    get_request_lifecycle_trace,
    get_telemetry_summary_stats,
    set_current_request_id,
    get_current_request_id,
    generate_request_id,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_telemetry_logger_basic(tmp_path):
    log_dir = tmp_path / "logs"
    gen_audit = log_dir / "generation_audit.jsonl"

    telemetry = TelemetryLogger(
        audit_path=gen_audit,
        component="generation",
        storage_dir=tmp_path,
    )

    ev1 = telemetry.record_event(
        event="test_request",
        request_id="req_test_001",
        model="gemini-3.1-flash-lite-image",
        prompts={"compiled": "cinematic scene"},
        seed=12345,
    )

    assert ev1["event"] == "test_request"
    assert ev1["event_type"] == "test_request"
    assert ev1["request_id"] == "req_test_001"
    assert ev1["component"] == "generation"
    assert ev1["seed"] == 12345

    assert gen_audit.exists()
    lines = [json.loads(line) for line in gen_audit.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 1
    assert lines[0]["request_id"] == "req_test_001"

    # Also check unified telemetry file
    unified = log_dir / "telemetry.jsonl"
    assert unified.exists()
    u_lines = [json.loads(line) for line in unified.read_text(encoding="utf-8").strip().split("\n")]
    assert len(u_lines) == 1


def test_telemetry_query_and_filtering(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    telemetry_file = log_dir / "telemetry.jsonl"

    records = [
        {
            "timestamp": "2026-08-26T10:00:00Z",
            "event": "vision_request",
            "event_type": "vision_request",
            "request_id": "req_vis_1",
            "component": "vision",
            "status": "success",
            "model": "gemini-3.1-flash-lite",
            "duration_ms": 450.0,
        },
        {
            "timestamp": "2026-08-26T10:01:00Z",
            "event": "fine_tune_request",
            "event_type": "fine_tune_request",
            "request_id": "req_gen_1",
            "component": "generation",
            "status": "success",
            "model": "gemini-3.1-flash-lite-image",
            "prompts": {"compiled": "emerald dress velvet"},
            "duration_ms": 1200.0,
        },
        {
            "timestamp": "2026-08-26T10:02:00Z",
            "event": "inpaint_error",
            "event_type": "inpaint_error",
            "request_id": "req_inp_1",
            "component": "inpaint",
            "status": "error",
            "error": "Safety block triggered",
            "duration_ms": 300.0,
        },
    ]

    with telemetry_file.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # 1. Query all
    res_all = query_audit_events(storage_dir=tmp_path)
    assert res_all["total"] == 3
    # Newest first
    assert res_all["events"][0]["request_id"] == "req_inp_1"

    # 2. Filter by component
    res_gen = query_audit_events(storage_dir=tmp_path, component="generation")
    assert res_gen["total"] == 1
    assert res_gen["events"][0]["event"] == "fine_tune_request"

    # 3. Filter by status
    res_err = query_audit_events(storage_dir=tmp_path, status="error")
    assert res_err["total"] == 1
    assert res_err["events"][0]["component"] == "inpaint"

    # 4. Text search
    res_search = query_audit_events(storage_dir=tmp_path, search="emerald")
    assert res_search["total"] == 1
    assert res_search["events"][0]["request_id"] == "req_gen_1"

    # 5. Request lifecycle trace
    trace = get_request_lifecycle_trace("req_gen_1", storage_dir=tmp_path)
    assert len(trace) == 1
    assert trace[0]["request_id"] == "req_gen_1"

    # 6. Telemetry stats
    stats = get_telemetry_summary_stats(storage_dir=tmp_path)
    assert stats["total_events"] == 3
    assert stats["error_count"] == 1
    assert stats["components"]["vision"] == 1
    assert stats["components"]["generation"] == 1
    assert stats["components"]["inpaint"] == 1
    assert "gemini-3.1-flash-lite" in stats["average_latencies_ms"]


def test_api_middleware_and_telemetry_endpoints(client):
    # 1. Test X-Request-ID propagation on normal endpoint
    custom_req_id = "test_custom_req_999"
    resp = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_req_id

    # 2. Test auto-generated request ID if header not supplied
    resp_auto = client.get("/health")
    assert resp_auto.status_code == 200
    assert resp_auto.headers.get("X-Request-ID") is not None
    assert resp_auto.headers.get("X-Request-ID").startswith("req_")

    # 3. Test GET /api/telemetry/events
    resp_events = client.get("/api/telemetry/events?limit=10")
    assert resp_events.status_code == 200
    data = resp_events.json()
    assert "total" in data
    assert "events" in data
    assert isinstance(data["events"], list)

    # 4. Test GET /api/telemetry/stats
    resp_stats = client.get("/api/telemetry/stats")
    assert resp_stats.status_code == 200
    stats = resp_stats.json()
    assert "total_events" in stats
    assert "success_rate" in stats
    assert "components" in stats

    # 5. Test GET /api/telemetry/logs
    resp_logs = client.get("/api/telemetry/logs?lines=50")
    assert resp_logs.status_code == 200
    logs_data = resp_logs.json()
    assert "total_lines" in logs_data
    assert "logs" in logs_data

    # 6. Test GET /api/telemetry/db/summary
    resp_db_sum = client.get("/api/telemetry/db/summary")
    assert resp_db_sum.status_code == 200
    db_summary = resp_db_sum.json()
    assert "tables" in db_summary
    assert "generations" in db_summary["tables"]

    # 7. Test GET /api/telemetry/db/generations
    resp_db_rows = client.get("/api/telemetry/db/generations?limit=10")
    assert resp_db_rows.status_code == 200
    rows_data = resp_db_rows.json()
    assert rows_data["table"] == "generations"
    assert "total" in rows_data
    assert isinstance(rows_data["rows"], list)

