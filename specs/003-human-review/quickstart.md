# Quickstart: Validating Human Review

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`), including `langgraph-checkpoint-sqlite`
- Synthetic fixtures in `backend/tests/fixtures/review/` (transactions with varying `confidence`, including at
  least one transfer candidate)
- In automated tests, the graph is driven programmatically (no real terminal) — see research.md

## Scenario 1 — Review and correct medium/low confidence (User Story 1)

1. Populate the database with `confidence = medium` and `confidence = low` transactions for a month.
2. Invoke the graph for that month; capture the first `interrupt()`'s payload.
3. Respond `"aceitar"` for the medium-confidence item; verify the transaction keeps the suggested category with
   `confidence = high`.
4. Respond with a different category (`"Alimentação|Mercado"`) for the low-confidence item; verify the
   transaction gets that category with `confidence = high`.
5. Run the graph for a month where every transaction is already `confidence = high`; verify it finishes with no
   `interrupt()` at all.

**Expected result**: every pending transaction ends up reviewed and with `confidence = high`; a month with
nothing pending doesn't interrupt.

## Scenario 2 — Confirm or reject a transfer (User Story 2)

1. Populate the database with a transaction `category = "Transferência interna"`, `confidence = medium`.
2. Invoke the graph; respond `"confirmar"` — verify the category stays "Transferência interna" with
   `confidence = high`.
3. Repeat with another equivalent transaction, responding with a different category (e.g.
   `"Alimentação|Restaurante/Delivery"`) — verify it replaces "Transferência interna" with the provided category,
   with `confidence = high`.

**Expected result**: no transfer candidate is left without an explicit decision.

## Scenario 3 — Resume an interrupted session (User Story 3)

1. Populate the database with 3 pending transactions.
2. Invoke the graph, respond to the first `interrupt()`, and then stop advancing the graph (simulating a process
   interruption — don't call `.stream()`/`.invoke()` again yet).
3. Verify directly in the database that the first decision is already persisted (`confidence = high`), even
   though the graph hasn't finished.
4. Invoke the graph again with the same `thread_id` (resuming via the checkpointer); verify the first item isn't
   presented again — the next `interrupt()` is already the second pending item.

**Expected result**: no decision already made is lost or repeated on resume.

## Exit checklist

- [ ] Scenario 1 confirms accept/correct and the "nothing pending, no interruption" case
- [ ] Scenario 2 confirms confirming/rejecting a transfer
- [ ] Scenario 3 confirms resuming neither loses nor repeats a decision
- [ ] No test depends on a real terminal nor on real financial data
