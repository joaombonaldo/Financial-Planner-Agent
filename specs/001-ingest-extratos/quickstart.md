# Quickstart: Validating Bank Statement Ingestion

End-to-end validation guide for this feature. No implementation code — just the steps to prove the behavior
described in the spec works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- Test fixtures in `backend/tests/fixtures/bradesco/` and `backend/tests/fixtures/inter/` (small, synthetic CSVs
  covering the happy path + the spec's edge cases — never real data)
- An empty test SQLite database (a temp file, not the user's real database)

## Scenario 1 — Import a statement from each bank (User Story 1)

1. Run the ingestion process pointing at the Bradesco fixture.
2. Verify the detected bank is `bradesco`, with no manual input.
3. Verify the number of transactions returned matches the number of real transaction lines in the fixture
   (counted manually in the fixture).
4. Repeat steps 1-3 for the Inter fixture, including a line with a blank `Descrição` — verify the corresponding
   transaction uses `Histórico` as the description.

**Expected result**: normalized transactions in a single format (same field structure) for both banks, with
amount/date in canonical format, regardless of source bank.

## Scenario 2 — Reimport without duplicating (User Story 2)

1. Import the Bradesco fixture (as in Scenario 1).
2. Import the same fixture again.
3. Verify `transactions_imported` on the second run is `0` and `transactions_skipped_duplicate` matches the
   fixture's total transaction count.

**Expected result**: no duplicate transactions in the database after the second import.

## Scenario 3 — Warning on unrecognized file or inconsistent balance (User Story 3)

1. Run the ingestion process pointing at a CSV file whose column structure doesn't match either supported bank.
2. Verify the process returns an explicit "bank not recognized" error, without generating any transaction.
3. Run the process with a valid fixture where the balance column was deliberately altered to not reconcile with
   the sum of transactions.
4. Verify the `ImportResult` has `balance_reconciliation = mismatch` and contains a message in `warnings`
   explaining the discrepancy — and that the correctly recognized transactions are still imported.

**Expected result**: failures and inconsistencies are always visible to the user, never silent; a file from an
unsupported bank never generates partial transactions.

## Exit checklist

- [ ] Scenario 1 passes for Bradesco and Inter
- [ ] Scenario 2 confirms zero duplicates on reimport
- [ ] Scenario 3 confirms an explicit error (bank not recognized) and an explicit warning (balance doesn't
      reconcile)
- [ ] No test depends on the network, an LLM, or real financial data
