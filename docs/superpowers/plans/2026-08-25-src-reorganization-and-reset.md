# Source Reorganization and App Reset Implementation Plan

> **For agentic workers:** Execute inline in the current workspace. Do not use Git; the user explicitly prohibited all Git operations.

**Goal:** Move backend and frontend source under `src/`, repair all references, prune redundant tests, and leave the app with no accumulated runtime or build state.

**Architecture:** Preserve the Python package name `app` at `src/app` and add `src` to pytest's import path. Preserve the Vite project intact at `src/frontend`. Keep runtime state at repository-root `storage/` and `studio.db`.

**Tech Stack:** Python, FastAPI, pytest, React, Vite, Vitest, shell scripts.

---

### Task 1: Establish path expectations

**Files:**
- Modify: `tests/test_frontend_build_freshness.py`
- Modify: `tests/test_api_endpoints.py`
- Delete: `tests/test_api_health.py`

- [ ] Change the build-freshness fixture path to `tmp_path / "src" / "frontend"` and verify the test fails before the move.
- [ ] Preserve the unique health-title assertion in `test_api_endpoints.py`, then delete the duplicate standalone health test.
- [ ] Run `GEMINI_API_KEY=test-key .venv/bin/pytest tests/test_frontend_build_freshness.py tests/test_api_endpoints.py -q`; expect a path/import failure before configuration and source migration.

### Task 2: Move both source trees and repair executable paths

**Files:**
- Move: root-level `app/` → `src/app/`
- Move: root-level `frontend/` → `src/frontend/`
- Modify: `pyproject.toml`
- Modify: `src/app/main.py`
- Modify: `src/app/utils/logger.py`
- Modify: `launch.command`
- Modify: `scripts/frontend_needs_build.sh`

- [ ] Move the two directories without changing package names or frontend internals.
- [ ] Set pytest `pythonpath = ["src"]`.
- [ ] Make logging resolve repository-root `storage/logs`, not `src/storage/logs`.
- [ ] Update launcher validation, frontend build commands/messages, and the build helper default to `src/frontend`.
- [ ] Update the fallback page's frontend commands to `src/frontend`.
- [ ] Run the focused tests from Task 1; expect them to pass.

### Task 3: Update documentation and textual references

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `docs/**/*.md`
- Modify: `prompt_history.ipynb` only if an executable old source path is present

- [ ] Replace references to the former root-level source directories with `src/app/...` and `src/frontend/...` in project documentation.
- [ ] Update commands to use `uvicorn --app-dir src app.main:app` and `cd src/frontend`.
- [ ] Ignore `studio.db`, runtime storage contents, `src/frontend/dist/`, `src/frontend/node_modules/`, Python caches, pytest caches, and `.env` while allowing required storage placeholders.
- [ ] Search non-generated files with `rg` and inspect every remaining old path; retain only intentional Python module imports (`app.*`) and runtime `storage/` paths.

### Task 4: Audit and verify the test suite

**Files:**
- Modify or delete: `tests/test_*.py` and `src/frontend/src/**/*.test.*` only where coverage is obsolete or duplicated

- [ ] Compare test names and assertions for duplicate behavior.
- [ ] Delete only the confirmed duplicate health test and any other test proven redundant; do not remove distinct regression or behavior coverage.
- [ ] Run `GEMINI_API_KEY=test-key .venv/bin/pytest -q` and resolve migration failures.
- [ ] Run `npm install` in `src/frontend`, then `npm test -- --run` and `npm run build`.

### Task 5: Reset all generated state and perform final checks

**Files:**
- Delete: `studio.db`
- Delete contents: `storage/`
- Delete: `src/frontend/dist/`
- Delete: `src/frontend/node_modules/`
- Create: `storage/moodboards/.gitkeep`
- Create: `storage/generations/.gitkeep`
- Create: `storage/logs/.gitkeep`

- [ ] Remove the approved database, logs, uploaded media, generated images, frontend build, dependency tree, Python bytecode, and pytest cache.
- [ ] Recreate only empty storage directories and placeholder files.
- [ ] Verify imports with `GEMINI_API_KEY=test-key PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import app.main"` using `PYTHONPATH=src`.
- [ ] Verify the final tree contains `src/app`, `src/frontend`, no root `app` or `frontend`, and no generated state beyond placeholders.
- [ ] Run a final stale-reference scan and report any intentionally retained references.
