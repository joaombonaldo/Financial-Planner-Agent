# Data Model: Merchant Memory Update

## Merchant memory (from feature 002, now also written here)

No schema change — `merchant_memory` already exists (`merchant_key` PK, `category`, `subcategory`). This feature
adds the write path; feature 002 already established the read path.

| Field | Write rule in this feature |
|---|---|
| `merchant_key` | normalized (trim + lowercase) `description_raw` of the source transaction — same definition as feature 002 |
| `category` | the transaction's confirmed `category`, verbatim |
| `subcategory` | the transaction's confirmed `subcategory`, verbatim (nullable) |

**Upsert rule**: if `merchant_key` already has an entry, it's overwritten. If not, it's inserted. Never more than
one row per `merchant_key` (enforced by the existing primary key).

## Transaction (read-only input, no changes)

This feature reads `description_raw`, `category`, `subcategory`, and `confidence` from `transactions` — it never
writes to that table. Selection rule: `month_ref = ? AND confidence = 'high' AND category != 'Internal Transfer'`.
