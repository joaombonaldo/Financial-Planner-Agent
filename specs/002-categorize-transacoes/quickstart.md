# Quickstart: Validating Transaction Categorization

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- `config/categories.yaml` with the initial taxonomy (BRD Appendix A)
- Synthetic fixtures in `backend/tests/fixtures/categorization/` (transactions + `merchant_memory` state)
- The LLM is always mocked in automated tests — no scenario below depends on Ollama running

## Scenario 1 — Already-confirmed merchant (User Story 1)

1. Populate `merchant_memory` with a known mapping (e.g. "uber" → Transporte/Uber-99).
2. Run categorization on a transaction whose normalized description matches that merchant.
3. Verify the transaction gets the mapped category/subcategory with `confidence = high`, and that the LLM double
   was never called.

**Expected result**: automatic categorization without an LLM for already-known merchants.

## Scenario 2 — New merchant, via LLM (User Story 2)

1. Run categorization on a transaction whose merchant isn't in `merchant_memory`.
2. Configure the LLM double to return a valid taxonomy category.
3. Verify the transaction gets that category with `confidence` `medium` or `low` (never `high`).
4. Repeat, configuring the double to return a category **outside** the taxonomy.
5. Verify the transaction gets `category = "Outros"`, `confidence = low`.

**Expected result**: every transaction ends up with a valid category, even with an unexpected LLM response.

## Scenario 3 — Transfer candidate (User Story 3)

1. Create two synthetic transactions: one outgoing in one account ("PIX ENVIADO", amount X), one incoming in
   another account ("PIX RECEBIDO", same amount X), with dates up to 2 days apart.
2. Run categorization on the batch containing both.
3. Verify both get `category = "Transferência interna"`, `confidence = medium`, and that **neither** was removed
   from the total (the returned transaction list still has both).
4. Repeat with a transaction that has a transfer pattern but no mirrored pair within the window.
5. Verify that transaction follows the normal flow (Scenario 1 or 2), without becoming "Transferência interna".

**Expected result**: transfers are flagged, never automatically applied or excluded.

## Exit checklist

- [ ] Scenario 1 confirms `confidence = high` with no LLM call
- [ ] Scenario 2 confirms the "Outros"/`low` fallback for a response outside the taxonomy
- [ ] Scenario 3 confirms transfer flagging without exclusion from the total
- [ ] No test depends on the network, a real Ollama, or real financial data
