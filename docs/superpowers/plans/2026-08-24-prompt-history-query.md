# Prompt History Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one readable, read-only SQLite query for inspecting complete historical API prompts and generation metadata.

**Architecture:** A root-level `prompt_history.sql` configures the SQLite CLI for vertical records, then selects existing fields from `generations` newest-first. It changes no application code or data.

**Tech Stack:** SQLite CLI and SQL

---

### Task 1: Add and verify the history query

**Files:**
- Create: `prompt_history.sql`

- [ ] **Step 1: Create the query**

```sql
.headers on
.mode line

SELECT
    created_at,
    id AS generation_id,
    parent_id,
    moodboard_id,
    is_baseline,
    seed,
    aspect_ratio,
    resolution_width || 'x' || resolution_height AS resolution,
    negative_prompt,
    compiled_prompt,
    json(schema_json) AS scene_json
FROM generations
ORDER BY created_at DESC;
```

- [ ] **Step 2: Run the query**

Run: `sqlite3 -readonly studio.db < prompt_history.sql`

Expected: detailed generation records print newest-first with full prompts and valid formatted scene JSON; SQLite reports no errors.

- [ ] **Step 3: Check the file**

Run: `git diff --check -- prompt_history.sql`

Expected: no output and exit status 0.

- [ ] **Step 4: Commit**

```bash
git add prompt_history.sql
git commit -m "chore: add prompt history query"
```

- [ ] **Step 5: Open in VS Code**

Run: `code prompt_history.sql`

Expected: VS Code opens the SQL file.
