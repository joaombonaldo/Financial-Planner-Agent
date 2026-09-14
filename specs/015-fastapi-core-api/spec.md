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

## Architecture: `api.py` never touches `db/repository.py` directly

Every existing interface (`cli.py`) only ever calls `graph.invoke()` /
`Command(resume=...)` — all DB access is behind a `nodes/*.py` function, never
called directly by an interface module. `api.py` must hold to the same rule for
**every** endpoint, including the manual-edit one, which is the one place this
draft originally got it wrong (see "Manual edit" below for the fix): a new
`nodes/transactions.py` owns the repository calls for manual edits, and `api.py`
calls that, not `repository` itself. This keeps `api.py` as thin an interface as
`cli.py` is, and keeps the dependency direction consistent everywhere:
`interface -> nodes -> db/repository`, never `interface -> db/repository`.

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

**Required: the background wrapper must never let an exception disappear.**
Without an explicit catch-all, an unhandled exception in the background
thread/task kills that task silently — the registry stays at `"processing"`
forever and the client polls indefinitely with no way to know anything failed.
The function that wraps every `graph.invoke()` call in the background must:

```python
try:
    result = graph.invoke(...)
    registry[month_ref] = RunState.from_graph_result(result)
except Exception as exc:  # noqa: BLE001 — deliberate, same pattern as
                          # nodes/insights.py: this wrapper must never let a
                          # background task die without updating the registry.
    logger.exception("run failed for month_ref=%s", month_ref)
    registry[month_ref] = RunState(status="error", error=str(exc))
```

with the *full* traceback going to the server log (`logging`, stdlib — no new
dependency) and only a message reaching the client (see "Security" below for
why those two need to differ).

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
| `POST /transactions` | Manually add a transaction the bank statement never had (e.g. cash spending). Added 2026-09-14. Body: `{date, description_raw, account, type, amount, category, subcategory?, instrument?}`. `month_ref` is derived from `date`, not supplied — same as ingest. Goes straight to `confidence='high'` and teaches `merchant_memory`, same as `PATCH`'s recategorize path (`nodes/transactions.py:create`). No repository access from `api.py`, same rule as every other handler. |
| `GET /taxonomy` | `{"<category>": ["<subcategory>", ...], ...}` — the full tree (`config/categories.yaml`). Added 2026-09-12 while specifying specs/016-frontend-core: a review item's `suggested_subcategories` only covers the *currently suggested* category, so a "correct to a different category" UI control needs the full tree, which nothing else exposed. Static config, no `db_path` needed. |

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

Two independent, mutually exclusive actions per the BRD decision. Both are
implemented in a **new `nodes/transactions.py`** (not in `api.py` — see
"Architecture" above), which is what actually calls `db/repository.py`:

```python
# nodes/transactions.py
def recategorize(dedup_hash: str, category: str, subcategory: str | None, db_path: str) -> None:
    """Behaves exactly like a real review answer: confidence=high, then teaches
    merchant_memory. Raises TransactionNotFoundError if dedup_hash doesn't exist."""

def soft_delete(dedup_hash: str, db_path: str) -> None:
    """Excluded everywhere by default. No merchant_memory involvement (see BRD)."""

def restore(dedup_hash: str, db_path: str) -> None:
    """Undo a soft_delete."""
```

`api.py`'s `PATCH` handler does argument validation + picks which of the three
to call — it contains no SQL, no direct `repository` import.

```jsonc
// Recategorize — behaves exactly like a real review answer.
{"category": "Alimentação", "subcategory": "Mercado"}
```
`recategorize()` calls `repository.update_transaction_category(conn, dedup_hash,
category, subcategory, confidence="high")`, then re-runs
`nodes.memory.update_memory(month_ref, db_path)` for that transaction's month
(already idempotent/cheap — safe to call for a single correction). This is the
"teach the LLM" path. (`month_ref` is looked up from the transaction row itself,
not supplied by the client — the client only knows `dedup_hash`.)

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

## Security

"Local-only, no auth" (BRD §10) is a real decision, not an excuse to skip the
rest of this. Concrete requirements:

- **CORS must be an allowlist of exactly the frontend's own origin** (e.g.
  `http://localhost:5173` in dev), never `allow_origins=["*"]`. This is the
  actual mitigation for the realistic threat model here: with no auth token,
  any webpage open in the same browser can otherwise fire requests at
  `localhost:PORT` (CSRF against a local, unauthenticated API is a known,
  real exploit class — "no auth" does not mean "not reachable by a browser
  you didn't intend"). A same-origin-only CORS policy makes the browser itself
  refuse those cross-origin requests.
- **Bind uvicorn to `127.0.0.1`, not `0.0.0.0`.** Defense in depth beyond CORS
  — keeps the API unreachable from other devices on the same network, not just
  from other browser tabs.
- **Sanitize uploaded filenames before they reach a filesystem path.**
  `POST /months/{month_ref}/uploads` must take only `Path(filename).name` (or
  equivalent) before joining it into `extracts/{month_ref}/...` — an
  unsanitized filename containing `../` or an absolute path must not be able to
  write outside that directory.
- **Upload limits**: a size cap (reject anything absurd — e.g. above ~20MB,
  well beyond any real statement file) and an extension allowlist (`.csv`,
  `.pdf` only), enforced before the file is written to disk or handed to a
  parser. Prevents both accidental resource exhaustion and feeding garbage into
  `pdfplumber`.
- **PDF parsing of an untrusted upload is accepted residual risk for this
  feature**, not solved here: malformed/adversarial PDFs are a known parser
  attack surface (hangs, decompression bombs). Acceptable for a single-user
  local tool processing your own bank's PDFs; revisit if uploads are ever
  possible from anyone other than the one local user.
- **Client-facing error messages must be sanitized; full details are
  server-log-only.** A raw Python exception string can contain local file
  paths or other internals. Every error response uses the standard envelope
  below with a short, safe message; `logging.exception(...)` on the server
  carries the real traceback (see the run-state registry's exception-handling
  requirement above — same principle, applied consistently everywhere, not
  just in the background-run wrapper).

**Standard error envelope**, used by a global FastAPI exception handler so
every endpoint fails the same shape:

```jsonc
{"error": {"code": "not_found", "message": "Transaction not found"}}
```

## Extensibility and known constraints

Naming these explicitly so they're conscious trade-offs for this feature's
scope, not gaps discovered later:

- **The in-memory run-state registry only works for a single server process.**
  If this is ever deployed behind multiple workers (gunicorn `-w N`, serverless,
  anything that isn't one long-lived local process), the registry would need to
  move to something shared (Redis, or the same Postgres this project migrates
  to for Supabase anyway) — not a concern for the local single-process target
  of this feature, but a hard blocker to flag before any future deployment
  decision, not something to rediscover then.
- **No `user_id`/tenant scoping anywhere in the schema.** Correct for a
  single-user local tool. But it means a future "add auth" feature is not just
  "add a middleware" — every table and every query gains a scoping dimension.
  Writing this down now so it's budgeted for later, not a surprise.
- **No API versioning** (`/v1/...` prefix). Explicit decision to skip for a
  personal, never-publicly-exposed API — revisit only if this is ever exposed
  beyond localhost.

## Testing strategy

Same discipline the rest of this codebase already holds itself to (BRD §9): no
test ever depends on a real Ollama call.

- FastAPI's `TestClient` for every endpoint.
- The background execution path must be runnable **synchronously** under test
  (a test-mode toggle, or simply awaiting the same coroutine directly instead of
  scheduling it) — tests must not depend on real background-thread timing or
  need to poll-with-sleep to observe a result.
- Anything that reaches `categorize`/`generate_insights` in a test uses the
  existing `tests/fixtures/categorization/llm_double.py` (`FakeChatModel`) —
  exactly like every existing node test does. No new mocking approach.
- The background-wrapper exception-handling requirement above gets its own
  test: force a node to raise, assert the registry (or the `GET .../run`
  response) surfaces `{"status": "error", ...}` rather than hanging.
- Manual-edit tests live alongside the new `nodes/transactions.py`, following
  the same pattern as `tests/test_categorize.py`/`tests/test_review.py` —
  `recategorize` teaches `merchant_memory`, `soft_delete`/`restore` are excluded
  from/restored to every existing read path (`list_transactions_by_month`,
  `list_pending_review`, the credit-stream queries, `generate_report`).

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
  brainstorm-level decision. Whatever it is, must support running synchronously
  under test (see "Testing strategy").
- Whether `POST /months/{month_ref}/uploads` should validate file
  type/bank-detectability before accepting, or defer all of that to `POST
  .../run` (which already surfaces `UnrecognizedBankError` as a run error).
  Leaning toward the latter — one error-handling path, not two. (The
  size/extension checks in "Security" happen at upload time regardless — this
  question is only about *bank-detection* validation, not the security limits.)
- Exact upload size cap value (~20MB suggested — real statement files are
  KB-to-low-single-digit-MB; needs no more precision than "generous but not
  unbounded").
