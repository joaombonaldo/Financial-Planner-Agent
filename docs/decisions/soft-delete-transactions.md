# Decision: soft-delete transactions, never a real DELETE

**Branch**: `015-fastapi-core-api` (Wave 1 of the implementation)

**Date**: 2026-09-12

**Status**: Implemented (schema + repository layer only — the manual-edit node
and API endpoint that expose this are separate, parallel work)

**Related**: [specs/015-fastapi-core-api/spec.md](../../specs/015-fastapi-core-api/spec.md)

## Problem

The Phase 2 manual-edit feature needs a way to mark a transaction "not mine" —
paid on behalf of someone else, repaid separately, should count toward nothing.
The obvious implementation is `DELETE FROM transactions WHERE dedup_hash = ?`.

## Why not a real DELETE

Re-ingest idempotency (`transaction_exists`, checked by every parser's ingest
path via `dedup_hash`) depends on the row still being present in the table. If
the row is actually removed, re-uploading the same statement file later — e.g.
adding a bank file you forgot the first time, or reprocessing a month — would
no longer see it as "already imported" and would silently re-insert exactly the
transaction you'd just excluded. A soft-delete flag keeps the dedup tombstone in
place while excluding the row from every computation.

## Implementation

- `transactions.deleted_at TEXT` (nullable, `NULL` = active) — `schema.sql`.
- `db/repository.py`: `soft_delete_transaction(conn, dedup_hash)` /
  `restore_transaction(conn, dedup_hash)`, both simple single-column updates.
- Every existing read path gained a default `deleted_at IS NULL` filter:
  `list_transactions_by_month` (now takes `include_deleted: bool = False`),
  `list_credit_transactions_by_month` (passes it through),
  `list_credit_transactions_by_fatura_ref` (always excludes — a deleted
  purchase shouldn't count toward reconciliation), `list_pending_review`
  (always excludes — nothing to review about a transaction that's been
  decided not to exist).
- `transaction_exists` is deliberately **unchanged** — it must keep seeing
  soft-deleted rows, that's the entire point.
- `Transaction` (`state.py`) gained a `deleted_at: str | None = None` field so
  an `include_deleted=True` listing can show/sort by deletion status.

## Live-DB migration (not yet run — see docs/decisions/taxonomy-reorg.md and
credit-card-stream.md for the same pattern from earlier features)

```sql
ALTER TABLE transactions ADD COLUMN deleted_at TEXT;
CREATE INDEX IF NOT EXISTS idx_transactions_deleted_at ON transactions (deleted_at);
```

No existing rows need backfilling — `ADD COLUMN` without `NOT NULL` defaults
every existing row to `NULL` (active), which is correct.

## Consequences

- A soft-deleted transaction is invisible to `categorize`, `human_review`,
  `update_memory`, `budget_check`, `generate_insights`, and `generate_report`
  by default — the same invisibility credit-card rows already get from the
  debit-only default (feature 013). No node needed to change to get this; they
  all go through `list_transactions_by_month`'s default.
- `merchant_memory` is untouched by a soft-delete — per the BRD decision, this
  is expected to usually be a one-off (see BRD §10), so there's nothing durable
  to teach the LLM from a delete.
- Test coverage: `backend/tests/test_repository.py` — exclusion from month
  listing and pending review, restore, the `deleted_at` timestamp being set,
  and explicitly confirming `transaction_exists` still sees a deleted row (the
  property this whole design exists to preserve).
