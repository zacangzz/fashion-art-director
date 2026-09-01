import time
import pytest
from app.utils.telemetry import (
    TelemetryLogger,
    query_audit_events,
    get_request_lifecycle_trace,
    get_telemetry_summary_stats,
    generate_request_id,
)
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def fake_firestore():
    return FakeFirestoreClient()


def test_telemetry_record_event_non_blocking(fake_firestore):
    logger = TelemetryLogger(db=fake_firestore, component="generation")
    start = time.perf_counter()
    record = logger.record_event(
        event="generate_image",
        status="success",
        duration_ms=120.5,
        cost_usd=0.04,
        tokens=1000,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50.0  # Fast, non-blocking return
    assert record["event"] == "generate_image"
    assert record["status"] == "success"
    assert record["cost_usd"] == 0.04

    # Wait for thread write to complete
    time.sleep(0.05)
    events = list(fake_firestore.collection("telemetry_events").stream())
    assert len(events) == 1
    assert events[0].to_dict()["event"] == "generate_image"


def test_telemetry_query_filtering(fake_firestore):
    logger = TelemetryLogger(db=fake_firestore)
    logger.record_event(event="gen_1", component="generation", status="success", cost_usd=0.01)
    logger.record_event(event="gen_2", component="generation", status="error", cost_usd=0.0)
    logger.record_event(event="vis_1", component="vision", status="success", cost_usd=0.005)

    time.sleep(0.05)
    # Query component=generation and status=success
    res = query_audit_events(db=fake_firestore, component="generation", status="success")
    assert res["total"] == 1
    assert res["events"][0]["event"] == "gen_1"

    # Query all vision
    res_vis = query_audit_events(db=fake_firestore, component="vision")
    assert res_vis["total"] == 1
    assert res_vis["events"][0]["event"] == "vis_1"


def test_telemetry_request_lifecycle_trace(fake_firestore):
    logger = TelemetryLogger(db=fake_firestore)
    req_id = generate_request_id("trace")

    logger.record_event(event="start", request_id=req_id, timestamp="2026-09-01T10:00:00Z")
    logger.record_event(event="process", request_id=req_id, timestamp="2026-09-01T10:00:01Z")
    logger.record_event(event="complete", request_id=req_id, timestamp="2026-09-01T10:00:02Z")

    time.sleep(0.05)
    trace = get_request_lifecycle_trace(db=fake_firestore, request_id=req_id)
    assert len(trace) == 3
    assert [t["event"] for t in trace] == ["start", "process", "complete"]


def test_telemetry_summary_stats(fake_firestore):
    logger = TelemetryLogger(db=fake_firestore)
    logger.record_event(event="gen", component="generation", status="success", cost_usd=0.04, tokens=100, duration_ms=200, model="gemini-3-pro-image")
    logger.record_event(event="gen_fail", component="generation", status="error", cost_usd=0.0, tokens=0, duration_ms=100, model="gemini-3-pro-image")

    time.sleep(0.05)
    stats = get_telemetry_summary_stats(db=fake_firestore)
    assert stats["total_events"] == 2
    assert stats["error_count"] == 1
    assert stats["success_rate"] == 50.0
    assert stats["total_cost_usd"] == 0.04
    assert stats["total_tokens"] == 100
    assert "gemini-3-pro-image" in stats["average_latencies_ms"]
