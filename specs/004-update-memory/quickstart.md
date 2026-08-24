# Quickstart: Validating the Merchant Memory Update

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- No LLM or interactive input needed — this node has neither

## Scenario 1 — Remember a confirmed categorization (User Story 1)

1. Seed a transaction with `confidence = high`, `category = "Transportation"`, `subcategory = "Uber/99"`, for a
   given merchant description.
2. Run the merchant memory update for that month.
3. Verify `merchant_memory` now has an entry for that merchant's normalized key, with that category/subcategory.
4. Seed a second transaction for the same merchant with a **different** category, in the same or a later month.
5. Run the update again; verify the stored entry is overwritten with the newest category.
6. Run the update on an empty month (no transactions); verify it completes with no error and no writes.

**Expected result**: confirmed categorizations are remembered and stay current with the latest confirmation.

## Scenario 2 — Never remember a transfer (User Story 2)

1. Seed a transaction with `confidence = high` (or whatever value), `category = "Internal Transfer"`.
2. Run the merchant memory update for that month.
3. Verify no entry was created in `merchant_memory` for that transaction's merchant.

**Expected result**: transfer confirmations never pollute merchant memory.

## Exit checklist

- [ ] Scenario 1 confirms write + overwrite-on-reconfirmation + empty-month no-op
- [ ] Scenario 2 confirms transfers are always excluded
- [ ] No test depends on the LLM or on real financial data
