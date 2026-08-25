# Schema Observability and Adaptive Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vision extraction auditable and ensure production Visual Graph Studio renders only actual non-empty schema sections, including future unknown sections.

**Architecture:** Extend the existing recursive schema cleaner to optionally report removed JSON paths, and have `VisionService` append request/response/error JSONL audit events around the existing model call. Keep React rendering data-driven in `JsonGraphCanvas`; prevent deployment drift by moving frontend freshness detection into a small shell helper used by the launcher.

**Tech Stack:** Python 3.11, FastAPI, Google GenAI SDK, JSONL, React/Vitest, Bash/Vite.

---

### Task 1: Report recursive schema removals

**Files:**
- Modify: `tests/test_json_utils.py`
- Modify: `src/app/utils/json_utils.py`

- [ ] Add a failing test calling `strip_empty_sections(source, removed=removed)` and asserting JSON-pointer-like paths for nested empty values.
- [ ] Run `uv run pytest tests/test_json_utils.py -q` and confirm it fails because `removed` is unsupported.
- [ ] Add the optional accumulator while retaining the existing return type and preservation of `false` and `0`.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Audit the complete Vision boundary

**Files:**
- Modify: `tests/test_vision_service.py`
- Modify: `src/app/services/vision_service.py`
- Modify: `src/app/api/moodboard.py`

- [ ] Add failing tests that configure a temporary audit path and assert request/response records contain model configuration, stored image paths, assembled guide, raw response, parsed response, removed values, locked replacements, and final schema—but no image bytes or credentials.
- [ ] Run the focused Vision tests and confirm the new assertions fail.
- [ ] Add one append-only JSONL writer in `VisionService`, correlate records with a request ID, record failures without masking the original exception, and accept `image_paths` alongside bytes.
- [ ] Pass saved moodboard paths from both API endpoints and rerun focused tests.

### Task 3: Render arbitrary sparse schemas

**Files:**
- Modify: `src/frontend/src/components/JsonGraphCanvas.test.jsx`
- Modify: `src/frontend/src/components/JsonGraphCanvas.jsx`

- [ ] Add failing UI coverage showing null/empty sections are absent while a future unknown populated section appears.
- [ ] Run `npm test -- --run src/components/JsonGraphCanvas.test.jsx` and confirm the empty-section assertion fails.
- [ ] Tighten `schemaKeys` to retain only non-empty arrays/objects; keep the existing theme fallback and root-key behavior.
- [ ] Re-run the focused frontend test.

### Task 4: Rebuild stale production assets

**Files:**
- Create: `scripts/frontend_needs_build.sh`
- Create: `tests/test_frontend_build_freshness.py`
- Modify: `launch.command`

- [ ] Add a failing subprocess test covering missing, fresh, and stale output timestamps.
- [ ] Run the focused test and confirm the helper is missing.
- [ ] Implement a dependency-free shell predicate using `find -newer`, then invoke it from the launcher.
- [ ] Re-run the focused test.

### Task 5: Verify the shipped app

**Files:**
- Regenerate: `src/frontend/dist/index.html`
- Regenerate: `src/frontend/dist/assets/*`

- [ ] Run `uv run pytest -q` and confirm zero failures.
- [ ] Run `npm test -- --run` in `frontend` and confirm zero failures.
- [ ] Run `npm run build` in `frontend` and confirm success.
- [ ] Inspect the generated bundle to confirm the legacy hard-coded section array is absent and dynamic schema filtering is present.
- [ ] Run `git diff --check` and review only task-related changes before completion.
