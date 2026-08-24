# Research: Merchant Memory Update

No `NEEDS CLARIFICATION` remained in the Technical Context — the design gap (no "confirmed by a human" marker) was
already resolved as a documented assumption in spec.md.

## Idempotency via `ON CONFLICT`, not application-level dedup

- **Decision**: `upsert_merchant_category` uses `INSERT INTO merchant_memory (...) VALUES (...) ON CONFLICT
  (merchant_key) DO UPDATE SET category = excluded.category, subcategory = excluded.subcategory`.
- **Rationale**: `merchant_key` is already the table's primary key (feature 002's schema); a single SQL statement
  gives idempotency and "newest wins" for free, without needing a separate `SELECT` + branch in Python.
- **Alternatives considered**: `SELECT` to check existence, then `INSERT` or `UPDATE` — rejected as redundant
  round-trips for something `ON CONFLICT` already solves atomically, and less portable in spirit (more logic to
  re-verify when porting to Postgres later, even though the branching approach would technically also work there).

## Which transactions to write

- **Decision**: every transaction in the processed month with `confidence = 'high'` and `category != 'Internal
  Transfer'`.
- **Rationale**: matches FR-001/FR-003 directly. Since there's no field distinguishing "high via prior memory
  match" from "high via this month's human decision" (see spec.md Assumptions), re-writing memory-match-derived
  entries is unavoidable — but it's a harmless no-op (same value written again), so no extra filtering is needed
  to avoid it.
- **Alternatives considered**: adding a `reviewed_at`/`source` column to `transactions` to only write genuinely
  new decisions — rejected as premature complexity (Principle I) for a problem that's already solved by
  idempotency; worth reconsidering only if a real need for provenance tracking shows up later (e.g., an audit
  trail feature).

## Where this node sits in the graph

- **Decision**: extend `graph.py`'s existing conditional edge. Today, `_has_pending_review` routes back to
  `human_review` while there's pending work, or to `END` once there's none. It now routes to the new
  `update_memory` node instead of `END`, and `update_memory` itself routes to `END`.
- **Rationale**: `update_memory` only makes sense to run once the month has no more pending review items — running
  it earlier would write not-yet-confirmed (`medium`/`low`) categories into memory, which FR-006 explicitly
  forbids.
- **Alternatives considered**: a separate top-level call from the CLI, outside the graph — rejected because the
  whole point of the graph (and its checkpointer) is to guarantee this step only runs after review genuinely
  finishes for that month, not to leave that sequencing to whatever calls it.

## Testing strategy

- **Decision**: tests seed transactions directly (bypassing ingest/categorize/review, same pattern as feature
  003's isolated node tests) and call `nodes/memory.py`'s function directly — no graph/interrupt machinery
  needed, since this node never interrupts.
- **Rationale**: this node has no LLM and no human interaction, so there's nothing to mock — a plain function-level
  test is the simplest thing that could work (Principle I).
- **Alternatives considered**: testing only through the full `graph.py` chain — rejected as unnecessarily slow and
  indirect for logic this self-contained; a lightweight full-chain smoke test can still be added in Polish if
  useful, mirroring how quickstart.md validates the whole path manually.
