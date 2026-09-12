# Feature Specification: FastAPI core API (Phase 2 foundation)

**Feature Branch**: TBD (not started)

**Created**: 2026-09-12

**Status**: Specified, not implemented. This is the first Phase 2 feature — the
React frontend is not a separate design effort, it's a UI for the endpoints
defined here.

**Input**: A brainstorming conversation covering: where Phase 2 runs, whether
Supabase migration bundles with the API/UI work, when the LLM swap happens, what
the first UI cut includes, and how manual transaction edits should behave. See
BRD §10 "Architecture decisions (2026-09-12)" for the summary and rationale of
each call — this spec is the concrete design built on top of those decisions.

## Decisions this spec builds on (see BRD §10 for rationale)

- Local-only, no auth.
- Built against the existing local SQLite `core/` — Supabase migration is later,
  separate work, out of scope here.
- LLM stays Ollama — no swap as part of this feature.
- The CLI (`interface/cli.py`) is untouched; this adds `interface/api.py` as a
  second interface over the same `core/` graph and nodes (Principle II: nodes
  never know about interface concerns — that logic lives in `api.py`, mirroring
  how `cli.py` already keeps taxonomy/business logic out of itself).
- HITL over HTTP via polling, not push (no WebSocket/SSE).

## Problem

Today the only way to process a month is `interface/cli.py`'s `run_month()`,
which does one long blocking `graph.invoke()` call and then a synchronous
terminal `input()` loop for every pending review item. That's fine for a
terminal but has no HTTP equivalent — `interrupt()` pauses a *synchronous Python
call*, and an HTTP server can't hold a request open through minutes of LLM calls
plus an indefinite wait for the user to type an answer.

## Design

### Run model

A "run" is exactly what `thread_id = month_ref` already means in
`graph.py:build_graph()` — no new concept, no new identifier. Processing month
`2026-08` **is** the run named `2026-08`.

### Why "start" and "resume" can be the safely-repeatable same call

Feature 014 made `nodes/categorize.py` skip transactions that already have a
category (see commit `1f15917`) and `detect_and_parse` was already idempotent
via `dedup_hash`. Together, this means **a full `graph.invoke()` call is safe to
issue repeatedly for the same thread** — re-ingesting already-imported files and
re-categorizing already-categorized transactions is now a fast no-op, and the
graph naturally fast-forwards to wherever it actually is (the next pending
review item, or done). This was confirmed empirically running a real month
(2026-09-12): restarting the CLI process mid-review no longer re-runs the LLM
pass, it goes straight back to the pending item.

This is why the API doesn't need to distinguish "start a new run" from "resume
an interrupted one after a server restart" — `POST .../run` is the same call
either way, and it's what makes the in-memory (non-persisted) run-state registry
below acceptable.

### Server-side run-state registry

An in-memory, module-level registry in `interface/api.py` — **not** a new DB
table — mapping `month_ref -> RunState`:

```python
@dataclass
class RunState:
    status: Literal["processing", "pending_review", "completed", "error"]
    item: dict | None = None      # current interrupt payload, when pending_review
    report: dict | None = None    # when completed
    error: str | None = None      # when error
```

Each `POST .../run` or `POST .../review` call spawns the graph call in a
background thread (`asyncio.to_thread` / `BackgroundTasks`, no task queue needed
— single-user, local, at most a handful of concurrent months in practice) and
updates the registry when it finishes or hits an interrupt. `GET .../run` just
reads the registry.

**Why in-memory is acceptable, not a shortcut:** if the server restarts mid-run,
the registry is empty and the client's next `GET` returns "not started" — but
issuing `POST .../run` again is safe and cheap per the idempotency argument
above. No data is lost; at most the user re-clicks "process this month."

**Concurrency guard:** `POST .../run` for a `month_ref` that's already
`processing` in the registry is a no-op (returns the current state, doesn't
spawn a second background task).

### Endpoints

| Method & path | Purpose |
|---|---|
| `POST /months/{month_ref}/uploads` | Multipart upload of one or more statement files (CSV/PDF). Saves to `extracts/{month_ref}/` server-side (local disk — no object storage needed pre-Supabase). Returns the saved file paths. |
| `POST /months/{month_ref}/run` | Start/resume processing. Body: `{"files": [<paths from upload>], "budget_path"?: string}`. Spawns the graph call in the background. Returns `202` + `{"status": "processing"}` immediately. Idempotent/safe to repeat (see above). |
| `GET /months/{month_ref}/run` | Poll status. Returns one of the four `RunState` shapes below, or `{"status": "not_started"}`. |
| `POST /months/{month_ref}/review` | Answer the current pending item. Body is structured (see below), translated to the CLI's string protocol inside `api.py` — `nodes/review.py` is untouched. Returns `202` immediately; poll `GET .../run` for the next item. |
| `GET /months` | `[{"month_ref": str, "transaction_count": int, "has_pending_review": bool}, ...]` — derived from `SELECT DISTINCT month_ref` + `list_pending_review` per month. Backs the month-history list. |
| `GET /months/{month_ref}/report` | Recomputes and returns `generate_report()`'s output fresh — **never cached**, since a manual edit to a past month must be reflected immediately. |
| `GET /months/{month_ref}/transactions` | List transactions for a month. Query params: `instrument?`, `category?`, `include_deleted?` (default false). Backs the manual-edit browsing UI. |
| `PATCH /transactions/{dedup_hash}` | Manual edit — see below. |

### `GET .../run` response shapes

```jsonc
{"status": "not_started"}
{"status": "processing"}
{"status": "pending_review", "item": {
  "date": "2026-08-01", "description_raw": "...", "amount": 200.0,
  "account": "inter", "category": "Outros", "subcategory": null,
  "confidence": "medium", "instrument": "debit",
  "is_transfer_candidate": false, "suggested_subcategories": [...]
}}
{"status": "completed", "report": { /* same shape nodes/report.py + graph.py already produce */ }}
{"status": "error", "message": "..."}
```

The `item` shape is exactly today's `interrupt()` payload
(`nodes/review.py:_build_payload`, already includes `instrument` per feature
014) — no new payload design needed, just exposed over HTTP instead of printed.

### `POST .../review` request body

Structured, not the CLI's raw string — a real API shouldn't ask a browser to
construct `"categoria|subcategoria"` text:

```jsonc
{"action": "accept"}
{"action": "confirm_transfer"}
{"action": "correct", "category": "Lazer", "subcategory": "Restaurante/Bar"}
```

`api.py` translates this to the string `nodes/review.py:_parse_answer` already
parses ("aceitar" / "confirmar" / "categoria|subcategoria") and calls
`graph.invoke(Command(resume=<string>), config=...)`. This keeps the
translation — an interface concern — out of `nodes/review.py`, the same
separation `cli.py` already maintains today.

### Manual edit — `PATCH /transactions/{dedup_hash}`

Two independent, mutually exclusive actions per the BRD decision:

```jsonc
// Recategorize — behaves exactly like a real review answer.
{"category": "Alimentação", "subcategory": "Mercado"}
```
Calls `repository.update_transaction_category(conn, dedup_hash, category,
subcategory, confidence="high")`, then re-runs `nodes.memory.update_memory
(month_ref, db_path)` for that transaction's month (already idempotent/cheap —
safe to call for a single correction). This is the "teach the LLM" path.

```jsonc
// Soft-delete — "this isn't mine, treat it as if it never existed."
{"deleted": true}
```
```jsonc
// Restore (undo).
{"deleted": false}
```
**No** `merchant_memory` involvement — per the BRD decision, this is usually a
one-off (paid for a friend, repaid later), not a recurring pattern worth
learning.

### Schema change required (not yet implemented)

`transactions` gains a nullable `deleted_at TEXT` column (ISO datetime, NULL =
active). Every existing read path that currently has an `instrument` default
(`list_transactions_by_month`, `list_credit_transactions_by_month`,
`list_credit_transactions_by_fatura_ref`, `list_pending_review`) needs an
additional `AND deleted_at IS NULL` — soft-deleted rows must be invisible to
`categorize`, `human_review`, `update_memory`, `budget_check`,
`generate_insights`, and `generate_report` by default, the same way credit rows
are invisible to the debit-only default today. `include_deleted=true` on `GET
.../transactions` is the one path that needs to see them (for an "undo" UI).

New repository functions: `soft_delete_transaction(conn, dedup_hash)`,
`restore_transaction(conn, dedup_hash)` — both simple, single-column updates,
same pattern as `update_transaction_category`.

**Why not a real `DELETE FROM transactions`:** re-ingest idempotency
(`transaction_exists` / `dedup_hash`) depends on the row still being present.
Hard-deleting it means re-uploading the same statement file later (e.g. adding
a missed bank file to an already-processed month) would silently re-insert the
"deleted" transaction — the exact resurrection bug this design avoids.

## Out of scope (this feature)

- The React frontend itself — a UI for these endpoints, not designed here.
- Supabase migration, auth, deployment/hosting beyond localhost.
- The LLM swap and the categorization golden set.
- A budget-goals editor endpoint (explicitly deferred past the first UI cut per
  the BRD decision).
- Any change to `interface/cli.py`, `nodes/review.py`'s payload/parsing logic,
  or the graph's node structure — this feature only adds a new interface layer
  and the soft-delete schema/repository support underneath it.

## Open questions for the planning/tasks pass

- Exact background-execution mechanism: `BackgroundTasks` (simplest, tied to
  request lifecycle) vs. a standalone `asyncio.to_thread` future stored in the
  registry (survives independent polling better). Needs a spike, not a
  brainstorm-level decision.
- Whether `POST /months/{month_ref}/uploads` should validate file
  type/bank-detectability before accepting, or defer all of that to `POST
  .../run` (which already surfaces `UnrecognizedBankError` as a run error).
  Leaning toward the latter — one error-handling path, not two.
- CORS configuration for local dev (Vite's dev server origin vs. FastAPI's).
