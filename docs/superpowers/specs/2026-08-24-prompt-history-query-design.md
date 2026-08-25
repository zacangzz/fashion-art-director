# Prompt History Query Design

Create one `prompt_history.sql` file for SQLite. It will configure readable
terminal output and list every generation newest-first with its timestamp, ID,
seed, aspect ratio, negative prompt, full compiled prompt, and formatted scene
JSON.

The file will query the existing `generations` table without changing data or
application code. It will run from the project root with:

```sh
sqlite3 -readonly studio.db < prompt_history.sql
```

Verification consists of running that command and confirming detailed records
are printed successfully.
