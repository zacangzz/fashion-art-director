import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from google.cloud.firestore import Client

from app.utils.logger import (
    get_logger,
    get_current_request_id,
    set_current_request_id,
    get_current_trace_id,
    set_current_trace_id,
    set_request_context,
    request_id_var,
    trace_id_var,
)

logger = get_logger("telemetry")


def generate_request_id(prefix: str = "req") -> str:
    """Generates a standardized unique request identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def format_image_url(img_ref: Any) -> Optional[str]:
    """
    Normalizes local or remote image references to a standard HTTP or API endpoint URL.
    """
    if not img_ref:
        return None
    if isinstance(img_ref, dict):
        img_ref = img_ref.get("url") or img_ref.get("image_url") or img_ref.get("path")
    if not isinstance(img_ref, str) or not img_ref.strip():
        return None
    s = img_ref.strip()
    if s.startswith("http://") or s.startswith("https://") or s.startswith("data:") or s.startswith("blob:"):
        return s
    if s.startswith("/api/images/"):
        return s
    return f"/api/images/{s.lstrip('/')}"


def extract_prompt_fields_from_event(e: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Modular extractor for positive prompt, system instruction, negative prompt,
    master prompt, and narrative across different telemetry event formats.
    """
    prompt = None
    system_instruction = None
    negative_prompt = None
    master_prompt = None
    narrative = None

    # 1. Direct prompts payload
    prompts = e.get("prompts")
    if isinstance(prompts, dict):
        prompt = prompts.get("user_prompt") or prompts.get("positive_prompt") or prompts.get("prompt")
        system_instruction = prompts.get("system_instruction")
        negative_prompt = prompts.get("negative_prompt")
    elif isinstance(prompts, str):
        prompt = prompts

    # 2. Direct inputs payload
    inputs = e.get("inputs")
    if isinstance(inputs, dict):
        if not prompt:
            prompt = inputs.get("prompt") or inputs.get("user_prompt") or inputs.get("text_prompt")
        if not system_instruction:
            system_instruction = inputs.get("system_instruction")

    # 3. Direct event attributes
    if not prompt:
        prompt = (
            e.get("extracted_master_prompt")
            or e.get("master_prompt")
            or e.get("compiled_prompt")
            or e.get("prompt")
        )

    if not system_instruction:
        system_instruction = e.get("instruction") or e.get("system_instruction")
        if not system_instruction and isinstance(e.get("config"), dict):
            system_instruction = e["config"].get("system_instruction")

    if not negative_prompt:
        negative_prompt = e.get("negative_prompt")
        if not negative_prompt and isinstance(e.get("config"), dict):
            negative_prompt = e["config"].get("negative_prompt")

    master_prompt = e.get("extracted_master_prompt") or e.get("master_prompt") or e.get("compiled_prompt")
    narrative = e.get("extracted_narrative") or e.get("narrative")

    return {
        "prompt": prompt,
        "system_instruction": system_instruction,
        "negative_prompt": negative_prompt,
        "master_prompt": master_prompt,
        "narrative": narrative,
    }


class TelemetryLogger:
    """
    Standardized telemetry and audit event logger with Firestore backend.
    Dispatches events asynchronously via daemon background threads to ensure zero
    filesystem I/O and zero latency impact on model response times.
    """

    def __init__(
        self,
        db: Optional[Any] = None,
        component: str = "general",
        audit_path: Optional[Any] = None,
        storage_dir: Optional[Any] = None,
    ):
        self.db = db
        self.component = component

    def _get_db(self) -> Optional[Any]:
        if self.db is not None:
            return self.db
        try:
            from app.firebase_init import get_firestore_client
            return get_firestore_client()
        except Exception:
            return None

    def record_event(
        self,
        event: str,
        request_id: Optional[str] = None,
        component: Optional[str] = None,
        user_id: Optional[str] = None,
        status: str = "success",
        duration_ms: Optional[float] = None,
        prompts: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        tokens: Optional[Union[Dict[str, Any], int]] = None,
        cost_usd: Optional[float] = None,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        cumulative_cost_usd: Optional[float] = None,
        cumulative_tokens: Optional[int] = None,
        generation_id: Optional[str] = None,
        error: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        eff_req_id = request_id or get_current_request_id() or generate_request_id("op")
        eff_component = component or self.component
        iso_timestamp = datetime.now(timezone.utc).isoformat()
        event_id = str(uuid.uuid4())

        record: Dict[str, Any] = {
            "id": event_id,
            "timestamp": iso_timestamp,
            "event": event,
            "event_type": event,
            "request_id": eff_req_id,
            "component": eff_component,
            "user_id": user_id or "anonymous",
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

        for key, val in extra.items():
            if key not in record:
                record[key] = val

        # Asynchronously dispatch to Firestore
        self._dispatch_event_async(record)
        return record

    def _dispatch_event_async(self, record: Dict[str, Any]) -> None:
        def _write():
            try:
                db_client = self._get_db()
                if db_client is not None:
                    doc_id = record.get("id") or str(uuid.uuid4())
                    db_client.collection("telemetry_events").document(doc_id).set(record)
            except Exception:
                # Background telemetry should never interrupt active execution or fail tests
                pass

        # Non-blocking daemon thread execution
        thread = threading.Thread(target=_write, daemon=True)
        thread.start()


def query_audit_events(
    db: Any,
    user_id: Optional[str] = None,
    component: Optional[str] = None,
    event: Optional[str] = None,
    request_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Queries telemetry events from Firestore with filtering and sorting.
    """
    query = db.collection("telemetry_events")
    if user_id:
        query = query.where("user_id", "==", user_id)
    if component:
        query = query.where("component", "==", component)
    if event:
        query = query.where("event", "==", event)
    if request_id:
        query = query.where("request_id", "==", request_id)
    if status:
        query = query.where("status", "==", status)

    try:
        query = query.order_by("timestamp", direction="DESCENDING")
    except Exception:
        pass

    docs = list(query.stream())
    events = [d.to_dict() for d in docs]

    if search:
        search_lower = search.lower()
        events = [e for e in events if search_lower in str(e).lower()]

    total_count = len(events)
    paginated_events = events[offset : offset + limit]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "events": paginated_events,
    }


def get_request_lifecycle_trace(
    db: Any,
    request_id: str,
) -> List[Dict[str, Any]]:
    """
    Fetches the chronological lifecycle events for a specific request ID.
    """
    res = query_audit_events(db=db, request_id=request_id, limit=1000, offset=0)
    trace = res.get("events", [])
    trace.sort(key=lambda r: str(r.get("timestamp", "")))
    return trace


def get_telemetry_summary_stats(
    db: Any,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes summary telemetry metrics across stored Firestore events.
    """
    res = query_audit_events(db=db, user_id=user_id, limit=5000, offset=0)
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
        elif toks is not None:
            try:
                total_tokens += int(toks)
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


def get_generation_runs(
    db: Any,
    user_id: Optional[str] = None,
    component: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Groups telemetry events by request_id into end-to-end generation run summaries.
    """
    res = query_audit_events(db=db, user_id=user_id, limit=5000, offset=0)
    all_events = res.get("events", [])

    # Group by request_id
    # Pre-cache recent generation records from Firestore if db provided
    gens_by_id: Dict[str, Dict[str, Any]] = {}
    gens_by_seed: Dict[Any, Dict[str, Any]] = {}
    if db and hasattr(db, "collection"):
        try:
            gens_stream = (
                db.collection("generations")
                .order_by("created_at", direction="DESCENDING")
                .limit(60)
                .stream()
            )
            for g in gens_stream:
                gd = g.to_dict() if hasattr(g, "to_dict") else {}
                g_id = getattr(g, "id", None) or gd.get("id")
                if g_id:
                    gens_by_id[g_id] = gd
                if gd.get("seed") is not None:
                    gens_by_seed[gd["seed"]] = gd
        except Exception:
            try:
                for g in db.collection("generations").limit(60).stream():
                    gd = g.to_dict() if hasattr(g, "to_dict") else {}
                    g_id = getattr(g, "id", None) or gd.get("id")
                    if g_id:
                        gens_by_id[g_id] = gd
                    if gd.get("seed") is not None:
                        gens_by_seed[gd["seed"]] = gd
            except Exception as e:
                logger.debug(f"Could not pre-fetch generations for telemetry prompt enrichment: {e}")

    runs_map: Dict[str, List[Dict[str, Any]]] = {}
    for ev in all_events:
        req_id = ev.get("request_id") or "req_unknown"
        if req_id not in runs_map:
            runs_map[req_id] = []
        runs_map[req_id].append(ev)

    runs_list: List[Dict[str, Any]] = []
    for req_id, events in runs_map.items():
        # Sort events chronologically
        events.sort(key=lambda r: str(r.get("timestamp", "")))
        first_ev = events[0]
        last_ev = events[-1]

        components = set(e.get("component") for e in events if e.get("component"))

        # If filtering all or not specified, exclude standalone pure middleware HTTP request/response logs
        if (not component or component == "all") and components == {"api"}:
            continue

        # Determine overall status
        has_error = any(
            e.get("status") == "error" or "error" in (e.get("event") or "").lower()
            for e in events
        )
        run_status = "error" if has_error else (last_ev.get("status") or "success")

        # Sum durations, costs, tokens
        total_duration_ms = 0.0
        total_cost = 0.0
        total_tokens = 0
        models_used = set()
        prompt_snippet = ""
        system_instruction = ""
        negative_prompt = ""
        master_prompt = ""
        narrative = ""
        seed = None
        gen_id = None
        input_images = []
        output_images = []

        for e in events:
            dur = e.get("duration_ms")
            if dur is not None:
                try:
                    total_duration_ms += float(dur)
                except (ValueError, TypeError):
                    pass

            c = e.get("cost_usd")
            if c is not None:
                try:
                    total_cost += float(c)
                except (ValueError, TypeError):
                    pass

            toks = e.get("tokens")
            if isinstance(toks, dict):
                t_val = toks.get("total_tokens") or toks.get("total_token_count") or 0
                try:
                    total_tokens += int(t_val)
                except (ValueError, TypeError):
                    pass
            elif toks is not None:
                try:
                    total_tokens += int(toks)
                except (ValueError, TypeError):
                    pass

            mod = e.get("model") or (e.get("config", {}).get("model") if isinstance(e.get("config"), dict) else None)
            if mod:
                models_used.add(mod)

            # Extract Prompt text and directives via modular helper
            extracted_fields = extract_prompt_fields_from_event(e)
            if not prompt_snippet and extracted_fields.get("prompt"):
                prompt_snippet = extracted_fields["prompt"]
            if not system_instruction and extracted_fields.get("system_instruction"):
                system_instruction = extracted_fields["system_instruction"]
            if not negative_prompt and extracted_fields.get("negative_prompt"):
                negative_prompt = extracted_fields["negative_prompt"]
            if not master_prompt and extracted_fields.get("master_prompt"):
                master_prompt = extracted_fields["master_prompt"]
            if not narrative and extracted_fields.get("narrative"):
                narrative = extracted_fields["narrative"]

            # Extract Seed and Generation ID
            if seed is None and isinstance(e.get("config"), dict):
                seed = e["config"].get("seed")
            if seed is None and e.get("seed") is not None:
                seed = e.get("seed")
            if not gen_id:
                gen_id = e.get("generation_id")

            # Extract Images
            inputs = e.get("inputs")
            if isinstance(inputs, dict):
                inp_imgs = inputs.get("image_urls") or inputs.get("input_images") or inputs.get("files") or inputs.get("image_paths") or []
                if isinstance(inp_imgs, list):
                    for img in inp_imgs:
                        formatted = format_image_url(img)
                        if formatted and formatted not in input_images:
                            input_images.append(formatted)

            raw_paths = e.get("image_paths") or []
            if isinstance(raw_paths, list):
                for img in raw_paths:
                    formatted = format_image_url(img)
                    if formatted and formatted not in input_images:
                        input_images.append(formatted)

            outputs = e.get("outputs")
            if isinstance(outputs, dict):
                out_imgs = outputs.get("image_urls") or outputs.get("images") or outputs.get("results") or []
                if isinstance(out_imgs, list):
                    for img in out_imgs:
                        formatted = format_image_url(img)
                        if formatted and formatted not in output_images:
                            output_images.append(formatted)

        # Cross-reference with Firestore generations if prompt or outputs are missing
        matched_gen = None
        if gen_id and gen_id in gens_by_id:
            matched_gen = gens_by_id[gen_id]
        elif seed is not None and seed in gens_by_seed:
            matched_gen = gens_by_seed[seed]

        if matched_gen:
            if not prompt_snippet:
                prompt_snippet = matched_gen.get("compiled_prompt") or matched_gen.get("prompt") or ""
            if not negative_prompt:
                negative_prompt = matched_gen.get("negative_prompt") or ""
            if not master_prompt:
                master_prompt = matched_gen.get("compiled_prompt") or ""
            gen_img = matched_gen.get("master_image_path")
            if gen_img:
                fmt_gen_img = format_image_url(gen_img)
                if fmt_gen_img and fmt_gen_img not in output_images:
                    output_images.append(fmt_gen_img)

        run_summary = {
            "request_id": req_id,
            "timestamp": last_ev.get("timestamp") or first_ev.get("timestamp"),
            "status": run_status,
            "duration_ms": round(total_duration_ms, 2),
            "cost_usd": round(total_cost, 6),
            "tokens": total_tokens,
            "models": list(models_used),
            "primary_model": list(models_used)[0] if models_used else "gemini-3.7-flash",
            "component": list(components)[0] if components else "generation",
            "components": list(components),
            "prompt": prompt_snippet,
            "system_instruction": system_instruction,
            "negative_prompt": negative_prompt,
            "master_prompt": master_prompt,
            "narrative": narrative,
            "step_count": len(events),
            "events": events,
            "input_images": input_images,
            "output_images": output_images,
        }

        # Apply filters
        if component and component != "all" and component not in components:
            continue
        if status and status != "all" and run_status != status:
            continue
        if search:
            s_low = search.lower()
            match_search = (
                s_low in req_id.lower()
                or s_low in prompt_snippet.lower()
                or s_low in system_instruction.lower()
                or any(s_low in m.lower() for m in models_used)
                or any(s_low in c.lower() for c in components)
            )
            if not match_search:
                continue

        runs_list.append(run_summary)

    # Sort runs by timestamp descending
    runs_list.sort(key=lambda r: str(r.get("timestamp", "")), reverse=True)

    total_runs = len(runs_list)
    paginated_runs = runs_list[offset : offset + limit]

    return {
        "total": total_runs,
        "limit": limit,
        "offset": offset,
        "runs": paginated_runs,
    }

