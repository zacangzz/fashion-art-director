# Source Reorganization and App Reset Design

## Goal

Place the Python backend and React frontend under `src/`, update every live reference to their new locations, remove accumulated application state and generated frontend artifacts, and prune tests that no longer provide distinct behavioral coverage.

## Target Layout

```text
src/
├── app/       # FastAPI backend; package name remains `app`
└── frontend/  # React/Vite frontend
```

Tests, documentation, launcher scripts, dependency manifests, notebooks, runtime storage, and the SQLite database remain rooted at the repository level. The Python configuration will add `src` to the import path so existing `app.*` imports remain unchanged.

## Migration

- Move root-level `app/` to `src/app/` without renaming the Python package.
- Move root-level `frontend/` to `src/frontend/`.
- Update executable paths in `launch.command`, build helpers, Python static-file discovery, test configuration, and frontend commands.
- Update README, documentation, notebook metadata or cells, and source-code strings that refer to the old locations.
- Do not add compatibility symlinks or duplicate packages.

## State Reset

- Delete the current `studio.db`; the application will recreate an empty schema on startup.
- Delete accumulated files under `storage/`, including logs, audit logs, moodboards, and generated images.
- Preserve the required empty storage directory structure with placeholder files where Git tracking requires them.
- Delete `src/frontend/dist/` and `src/frontend/node_modules/`; both are reproducible from the frontend package manifest and lockfile.
- Ensure generated database, storage contents, build output, dependencies, caches, and local environment files are ignored by Git.

## Test Cleanup

After moving the source trees, inspect all tests and delete only tests that are obsolete, duplicate another test's behavior, or exclusively enforce the former directory layout. Retain API, domain, service, persistence, frontend behavior, regression, security, and build-freshness coverage that remains meaningful. Update retained tests to import or locate code through `src`.

## Validation

- Search project files for stale executable references to the former root-level source directories.
- Run the retained Python test suite from the repository root.
- Reinstall locked frontend dependencies, run the frontend tests, and build the production frontend.
- Confirm the application can initialize a fresh database and empty storage directories.
- Remove regenerated database, logs, media, build output, and dependencies again after validation so the delivered repository remains reset.

## Safety

Deletion is limited to the explicitly approved generated targets: `studio.db`, contents of `storage/`, frontend `dist/`, frontend `node_modules/`, and tests proven obsolete or redundant by inspection. Source assets, prompts, configuration examples, documentation, lockfiles, and user-authored project files are preserved.
