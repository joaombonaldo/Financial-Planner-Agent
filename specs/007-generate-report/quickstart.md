# Quickstart: Validating Generate Report

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- No LLM or interactive input needed — this node has neither

## Scenario 1 — Complete financial picture (User Story 1)

1. Seed income and expense transactions across several categories, some with a configured budget goal and some
   without.
2. Run report generation; verify `total_income`, `total_expense`, `net_balance` match manual arithmetic.
3. Verify `category_breakdown` includes every category that had activity, including ones without a budget goal.
4. Run report generation on a month with zero transactions; verify all totals are zero and the breakdown is
   empty, with no error.

**Expected result**: the report's numbers exactly match manual arithmetic on the seeded transactions.

## Scenario 2 — Transfers kept separate (User Story 2)

1. Seed a transaction confirmed as "Internal Transfer" alongside real income and expense transactions.
2. Run report generation; verify the transfer's amount appears only in `transfer_total`, never in
   `total_income`, `total_expense`, `net_balance`, or `category_breakdown`.

**Expected result**: transfers never inflate or deflate the real income/expense picture.

## Scenario 3 — Budget and insights carried through (User Story 3)

1. Construct a budget comparison and an insights result (either a summary or a recorded failure) as if produced
   by the earlier pipeline steps.
2. Run report generation, passing both in; verify the assembled report contains them unmodified.

**Expected result**: the report is a faithful assembly of everything the pipeline already computed, nothing lost
or re-derived differently.

## Exit checklist

- [ ] Scenario 1 confirms totals, full breakdown, and the zero-transaction case
- [ ] Scenario 2 confirms transfers never affect income/expense/net/breakdown
- [ ] Scenario 3 confirms budget and insights data passes through unmodified
- [ ] No test depends on an LLM, a real terminal, or real financial data
