# Schema Observability and Adaptive Frontend Design

## Goal

Ensure Vision schema extraction is fully auditable without duplicating uploaded image bytes, and ensure Visual Graph Studio renders the schema actually returned rather than a fixed legacy section list.

## Backend observability

Each Vision extraction writes structured JSON Lines events to `storage/logs/vision_audit.jsonl`. The request event includes a request ID, timestamp, model name, generation configuration, relative paths for uploaded moodboard files, the complete assembled text instruction, and locked-section inputs. The response event includes the same request ID, raw model text, parsed JSON, locked-section replacements, recursively removed empty values with JSON paths and values, the final cleaned schema, and success or error details.

Image bytes, API keys, credentials, and authorization headers are never logged. Moodboard files remain in `storage/moodboards`; audit records refer to their workspace-relative paths. The API passes saved paths to the Vision service so request logs identify the actual stored inputs.

The existing recursive empty-value behavior remains authoritative: remove `null`, empty strings, empty arrays, and empty objects while retaining `false` and `0`. It will additionally report what it removed so model output can be distinguished from post-processing.

## Adaptive frontend

Visual Graph Studio derives its cards solely from actual top-level schema keys. `schema_version` and `metadata` remain summarized by the root card; every other non-empty object or array becomes a card, including unknown future sections. Nulls, empty objects, and empty arrays are excluded defensively even if an older record contains them.

No canonical section-name array controls rendering. Known names retain their colors and icons; unknown names use the existing neutral fallback. Required sections are protected from deletion when present, but are not synthesized by the UI.

## Production asset freshness

The launcher builds the frontend when the production bundle is missing or when any file under `src/frontend/src`, `src/frontend/index.html`, or frontend build configuration is newer than `src/frontend/dist/index.html`. This preserves fast launches while preventing an existing stale bundle from masking source changes.

The FastAPI static mount remains unchanged and serves the refreshed build.

## Errors and retention

Audit logging must not hide the original Vision failure. Logging errors go to the normal application log and processing continues where safe. Vision errors are recorded with request ID and message before existing API error handling runs.

JSONL is append-only and uses the existing log directory. Rotation and retention are deliberately excluded until file size becomes operationally significant.

## Verification

- Backend tests prove the assembled guide reaches the model and audit output captures raw, parsed, removed, and final values without image bytes.
- Utility tests prove removed JSON paths and preservation of meaningful falsy values.
- Frontend tests prove sparse schemas show only populated cards and arbitrary new sections appear automatically.
- A launcher check proves newer frontend sources trigger a production rebuild.
- Full backend tests, frontend tests, and `npm run build` must pass.
