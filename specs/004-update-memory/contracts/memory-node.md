# Contract: Node `update_memory`

## `nodes/memory.py`

**Input**: `month_ref`, `db_path`.

**Behavior**:
1. Reads every transaction for `month_ref` via `db/repository.py`.
2. Filters to `confidence == 'high'` and `category != TRANSFER_CATEGORY`.
3. For each one, computes the merchant key (reusing `categorization/merchant_memory.py`'s normalization) and
   calls `db/repository.py`'s upsert.

**Guarantees the contract requires**:
- Never writes an entry whose category is "Internal Transfer" (FR-003).
- Never touches `transactions` (FR-004) — read-only access to that table.
- Safe to call more than once for the same month (FR-005) — relies entirely on the upsert's `ON CONFLICT`
  semantics, no in-node dedup logic needed.
- Skips any transaction whose `confidence` isn't `high` (FR-006) — including "Internal Transfer" ones, which are
  always `medium` at best per feature 002/003's invariants, but the check is explicit regardless.

## `db/repository.py`

**New function**: `upsert_merchant_category(conn, merchant_key, category, subcategory)` — the only place that
issues the `INSERT ... ON CONFLICT ... DO UPDATE` against `merchant_memory`. `nodes/memory.py` never writes SQL
directly (Principle II).

## `graph.py`

**Change**: the conditional edge that used to route from `human_review` straight to `END` once there's nothing
left to review now routes to `update_memory` instead; `update_memory` then routes to `END`.
