import json
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.utils.logger import get_logger

logger = get_logger("telemetry")

# Context variable for correlating async execution flow with HTTP request IDs
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_current_request_id() -> Optional[str]:
    """Returns the current request ID from the execution context, if set."""
    return request_id_var.get()


def set_current_request_id(req_id: Optional[str]) -> None:
    """Sets the current request ID in the execution context."""
    request_id_var.set(req_id)


def get_current_trace_id() -> Optional[str]:
    """Returns the current trace ID from the execution context, if set."""
    return trace_id_var.get()


def set_current_trace_id(tr_id: Optional[str]) -> None:
    """Sets the current trace ID in the execution context."""
    trace_id_var.set(tr_id)


def generate_request_id(prefix: str = "req") -> str:
    """Generates a standardized unique request identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TelemetryLogger:
    """
    Standardized telemetry and audit event logger for all studio services.
    Appends structured JSON Lines events to local audit logs with schema consistency,
    timing analysis, prompt/state captures, and error telemetry.
    """

    def __init__(
        self,
        audit_path: Optional[Union[str, Path]] = None,
        component: str = "general",
        storage_dir: Optional[Union[str, Path]] = None,
    ):
        self.component = component
        self.storage_dir = Path(storage_dir or "./storage")
        if audit_path:
            self.audit_path = Path(audit_path)
        else:
            self.audit_path = self.storage_dir / "logs" / f"{component}_audit.jsonl"
        self.unified_audit_path = self.storage_dir / "logs" / "telemetry.jsonl"

    def record_event(
        self,
        event: str,
        request_id: Optional[str] = None,
        component: Optional[str] = None,
        status: str = "success",
        duration_ms: Optional[float] = None,
        prompts: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        tokens: Optional[Dict[str, Any]] = None,
        cost_usd: Optional[float] = None,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        cumulative_cost_usd: Optional[float] = None,
        cumulative_tokens: Optional[int] = None,
        generation_id: Optional[str] = None,
        error: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """
        Constructs and records a structured audit event.
        Flattens extra fields for backwards-compatibility with existing tests.
        """
        eff_req_id = request_id or get_current_request_id() or generate_request_id("op")
        eff_component = component or self.component
        iso_timestamp = datetime.now(timezone.utc).isoformat()

        record: Dict[str, Any] = {
            "timestamp": iso_timestamp,
            "event": event,
            "event_type": event,  # Alias for legacy compatibility
            "request_id": eff_req_id,
            "component": eff_component,
            "status": status,
        }

        if duration_ms is not None:
            record["duration_ms"] = round(float(duration_ms), 2)
        if prompts is not None:
            record["prompts"] = prompts
        if model is not None:
            record["model"] = model
        if config is not None:
            record["config"] = config
        if inputs is not None:
            record["inputs"] = inputs
        if outputs is not None:
            record["outputs"] = outputs
        if metrics is not None:
            record["metrics"] = metrics
        if tokens is not None:
            record["tokens"] = tokens
        if cost_usd is not None:
            record["cost_usd"] = round(float(cost_usd), 6)
        if cost_breakdown is not None:
            record["cost_breakdown"] = cost_breakdown
        if cumulative_cost_usd is not None:
            record["cumulative_cost_usd"] = round(float(cumulative_cost_usd), 6)
        if cumulative_tokens is not None:
            record["cumulative_tokens"] = int(cumulative_tokens)
        if generation_id is not None:
            record["generation_id"] = generation_id
        if error is not None:
            record["error"] = str(error)

        # Merge extra fields at top-level for backward compatibility
        for key, val in extra.items():
            if key not in record:
                record[key] = val

        self._write_record(record)
        return record

    def _write_record(self, record: Dict[str, Any]) -> None:
        """Writes JSONL entry to service audit log and unified telemetry log."""
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"

        # 1. Write to target service audit log
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception as err:
            logger.warning(f"Could not write audit log entry to {self.audit_path}: {err}")

        # 2. Write to unified telemetry log if distinct
        try:
            if self.audit_path != self.unified_audit_path:
                self.unified_audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.unified_audit_path.open("a", encoding="utf-8") as uf:
                    uf.write(line)
        except Exception:
            pass


def query_audit_events(
    storage_dir: Union[str, Path] = "./storage",
    component: Optional[str] = None,
    event: Optional[str] = None,
    request_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Scans and filters audit records across all JSONL log files in storage/logs/.
    Returns paginated events sorted newest first.
    """
    logs_dir = Path(storage_dir) / "logs"
    if not logs_dir.exists():
        return {"total": 0, "limit": limit, "offset": offset, "events": []}

    # Discover all audit jsonl files
    jsonl_files = list(logs_dir.glob("*.jsonl"))
    # Prefer unified telemetry if exists and non-empty, else gather all specific audit logs
    unified_file = logs_dir / "telemetry.jsonl"
    target_files = [unified_file] if (unified_file.exists() and unified_file.stat().st_size > 0) else [
        f for f in jsonl_files if f.name != "telemetry.jsonl"
    ]

    all_events: List[Dict[str, Any]] = []
    seen_signatures = set()

    search_lower = search.lower() if search else None

    for file_path in target_files:
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if search_lower and search_lower not in line.lower():
                        continue
                    try:
                        record = json.loads(line)
                        sig = (record.get("timestamp"), record.get("request_id"), record.get("event"))
                        if sig in seen_signatures:
                            continue
                        seen_signatures.add(sig)

                        # Filter by component
                        if component and record.get("component") != component:
                            continue
                        # Filter by event
                        if event and record.get("event") != event and record.get("event_type") != event:
                            continue
                        # Filter by request_id
                        if request_id and record.get("request_id") != request_id:
                            continue
                        # Filter by status
                        if status and record.get("status") != status:
                            continue

                        all_events.append(record)
                    except Exception:
                        continue
        except Exception as err:
            logger.warning(f"Error reading audit file {file_path}: {err}")

    # Sort descending by timestamp
    all_events.sort(key=lambda r: str(r.get("timestamp", "")), reverse=True)

    total_count = len(all_events)
    paginated_events = all_events[offset : offset + limit]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "events": paginated_events,
    }


def get_request_lifecycle_trace(
    request_id: str,
    storage_dir: Union[str, Path] = "./storage",
) -> List[Dict[str, Any]]:
    """
    Fetches the chronological lifecycle events for a specific request ID.
    """
    res = query_audit_events(
        storage_dir=storage_dir,
        request_id=request_id,
        limit=1000,
        offset=0,
    )
    # Sort ascending for chronological trace timeline
    trace = res.get("events", [])
    trace.sort(key=lambda r: str(r.get("timestamp", "")))
    return trace


def get_telemetry_summary_stats(
    storage_dir: Union[str, Path] = "./storage",
) -> Dict[str, Any]:
    """
    Computes summary telemetry metrics across stored audit events.
    """
    res = query_audit_events(storage_dir=storage_dir, limit=5000, offset=0)
    events = res.get("events", [])

    total_events = len(events)
    events_by_component: Dict[str, int] = {}
    events_by_type: Dict[str, int] = {}
    latencies_by_model: Dict[str, List[float]] = {}
    total_cost_usd = 0.0
    total_tokens = 0
    cost_by_component: Dict[str, float] = {}
    error_count = 0

    for ev in events:
        comp = ev.get("component") or "unknown"
        ev_type = ev.get("event") or ev.get("event_type") or "unknown"
        status = ev.get("status") or "success"

        events_by_component[comp] = events_by_component.get(comp, 0) + 1
        events_by_type[ev_type] = events_by_type.get(ev_type, 0) + 1

        cost = ev.get("cost_usd")
        if cost is not None:
            try:
                c_val = float(cost)
                total_cost_usd += c_val
                cost_by_component[comp] = cost_by_component.get(comp, 0.0) + c_val
            except (ValueError, TypeError):
                pass

        toks = ev.get("tokens")
        if isinstance(toks, dict):
            t_val = toks.get("total_tokens") or toks.get("total_token_count") or 0
            try:
                total_tokens += int(t_val)
            except (ValueError, TypeError):
                pass
        elif ev.get("total_tokens") is not None:
            try:
                total_tokens += int(ev["total_tokens"])
            except (ValueError, TypeError):
                pass

        if status == "error" or "error" in ev_type.lower():
            error_count += 1

        dur = ev.get("duration_ms")
        model = ev.get("model") or (ev.get("config", {}).get("model") if isinstance(ev.get("config"), dict) else None)
        if dur is not None and model:
            if model not in latencies_by_model:
                latencies_by_model[model] = []
            latencies_by_model[model].append(float(dur))

    avg_latencies = {
        m: round(sum(lats) / len(lats), 1)
        for m, lats in latencies_by_model.items()
        if lats
    }

    return {
        "total_events": total_events,
        "error_count": error_count,
        "success_rate": round(((total_events - error_count) / total_events * 100), 1) if total_events > 0 else 100.0,
        "total_cost_usd": round(total_cost_usd, 4),
        "total_tokens": total_tokens,
        "cost_by_component": {k: round(v, 4) for k, v in cost_by_component.items()},
        "components": events_by_component,
        "event_types": events_by_type,
        "average_latencies_ms": avg_latencies,
    }
