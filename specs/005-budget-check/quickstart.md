# Quickstart: Validating the Budget Check

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- No LLM or interactive input needed — this node has neither
- A temporary budget config file (not the real, gitignored `config/budget.local.yaml`)

## Scenario 1 — Actual spend vs. goal (User Story 1)

1. Configure a goal for one category (e.g. "Alimentação: 500.00") in a temporary budget file.
2. Seed a few expense transactions in that category totaling less than the goal; run the check; verify
   `status = within_budget` and the exact `actual_spend`/`difference`.
3. Seed more transactions pushing the total above the goal; run the check again; verify `status = over_budget`
   with the exact amount over.
4. Seed a total exactly equal to the goal; verify `status = within_budget` (not over).
5. Configure a goal for a category with zero transactions this month; verify it's reported with
   `actual_spend = 0`, within budget.

**Expected result**: every configured category's comparison exactly matches manual arithmetic on the seeded
transactions.

## Scenario 2 — Transfers and income excluded (User Story 2)

1. Seed a transaction confirmed as "Internal Transfer" in a category that also has a configured goal (in
   practice this only happens if a goal was set for "Internal Transfer" itself, or if a transfer somehow shares a
   category with real spend — construct the fixture so the exclusion is directly observable).
2. Seed an income transaction (`type = income`) in a category with expense transactions and a configured goal.
3. Run the check; verify neither the transfer nor the income transaction affected `actual_spend`.

**Expected result**: only real expense transactions ever count toward a goal's comparison.

## Scenario 3 — Missing configuration fails explicitly

1. Point `get_budget()` at a path that doesn't exist.
2. Verify `BudgetNotConfiguredError` is raised — not an empty result.

**Expected result**: a first-time setup mistake is impossible to miss.

## Exit checklist

- [ ] Scenario 1 confirms within/over/exact-equal/no-transactions cases
- [ ] Scenario 2 confirms transfers and income never count as spend
- [ ] Scenario 3 confirms missing configuration fails loudly
- [ ] No test depends on the LLM, a real terminal, or real financial data
