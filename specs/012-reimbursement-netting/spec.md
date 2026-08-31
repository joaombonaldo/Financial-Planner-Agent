# Feature Specification: Reimbursement Netting

**Feature Branch**: `012-reimbursement-netting`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "The user splits some expenses 50/50 with their brother: a shared expense (e.g.
R$200 at the supermarket under `Alimentação/Mercado`, or a house bill under `Moradia`) is followed within a few
days by an inbound PIX of roughly half — the brother's share. Today that inbound PIX inflates the income total
and hides that the real cost was only half. Categorize the repayment as `Receita / Reembolso` and have the
report and insights treat `Reembolso` specially: not added to income, instead netted against the expense
categories it offsets, showing gross / reimbursed / net per affected category."

## Problem

The user shares some expenses with a third party (typically 50/50 with their brother). The flow is: one shared
expense lands in its normal category (`Alimentação/Mercado`, `Moradia/...`, etc.), then a few days later an
inbound PIX arrives for the other person's share.

With the pipeline as built before this feature, that inbound PIX is just another `income` transaction. It
therefore (a) inflates total income with money that was never earned, and (b) leaves the shared expense recorded
at its full amount, hiding that the user's real cost was only their half. Both totals — income and expense — end
up wrong, and the net balance is wrong by twice the reimbursed amount.

## Decision (already made with the user)

The inbound repayment is categorized as **`Receita / Reembolso`** during `human_review`. That subcategory
already exists in the taxonomy (Appendix A), so no taxonomy change is needed.

`generate_report` and `generate_insights` then treat `Receita / Reembolso` specially:

- It is **excluded from `total_income`** — a refund is not earnings.
- It is **netted against expenses**. `total_expense` and `net_balance` become net of the month's total
  reimbursements.
- The category breakdown carries, per entry, **gross spend, reimbursed amount, and net spend**. The existing
  `total` field on each breakdown entry now holds the **net** figure, so the CLI printer and the graph's report
  projection keep working unchanged; `gross` and `reimbursed` are new sibling fields.
- The insights prompt receives the gross / reimbursed / net split per affected category, so the LLM summary can
  say e.g. "mercado: R$800 bruto, R$400 reembolsado, R$400 líquido". The deterministic fallback (LLM
  unreachable / blank) is unchanged.

## Attribution simplification and its limits

There is **no transaction-to-transaction matching** in this feature. All the report needs is the month's total
`Receita / Reembolso` and a way to attribute it to categories.

Attribution rule (a documented simplification): each `Reembolso` inflow is attributed to an expense category by
**best-effort substring matching of its `description_raw` against taxonomy-derived keywords** — each expense
category's name and its subcategory names, plus their slash/space-separated tokens of at least 4 characters.
Keywords that resolve to more than one category (e.g. "restaurante", which appears under both `Alimentação` and
`Lazer`) are dropped as ambiguous.

An inflow whose description matches **exactly one** expense category that **had spend this month** is attributed
to that category. Everything else — no match, multiple matches, or a match on a category with no spend — falls
into a single **"Reembolsos não atribuídos"** aggregate that reduces the overall expense total and net balance
but no specific category line.

Limits of this approach:

- It relies on the inflow description carrying a recognizable category word. Some banks (notably Bradesco) emit
  generic "PIX RECEBIDO" text with no counterparty or memo, in which case every reimbursement lands in the
  unattributed aggregate — correct at the total level, silent at the category level.
- It cannot tell which specific expense a repayment offsets, only which category, and it does not verify the
  repayment is ~half (or any fraction) of a real expense.
- If two categories are plausible from the text, the amount is not split — it goes to the unattributed
  aggregate.

These are acceptable because the total-level netting (income, expense, net balance) is always correct; only the
per-category attribution degrades, and it degrades to a visible, labeled aggregate rather than a wrong number.

## Requirements

### Functional Requirements

- **FR-001**: `generate_report` MUST exclude confirmed `Receita / Reembolso` transactions from `total_income`.
- **FR-002**: `generate_report` MUST compute `total_reimbursements` = sum of confirmed `Receita / Reembolso`
  amounts for the month.
- **FR-003**: `total_expense` and `net_balance` in the report MUST be net of `total_reimbursements`.
- **FR-004**: Each category breakdown entry MUST expose gross spend, reimbursed amount, and net spend, with the
  pre-existing `total` field equal to the net figure so existing consumers keep working.
- **FR-005**: A `Reembolso` inflow MUST be attributed to a single expense category when its description
  unambiguously matches one category that had spend this month; otherwise its amount MUST be added to an
  `unattributed_reimbursements` aggregate that still reduces `total_expense` and `net_balance`.
- **FR-006**: `generate_insights` MUST feed the gross / reimbursed / net split (per attributed category, plus the
  unattributed aggregate) into the LLM prompt context, and MUST keep its existing never-raise / blank-response
  fallback behavior.
- **FR-007**: The CLI report printer MUST show reimbursements — an aggregate line and, for any attributed
  category, its gross → net breakdown — in Portuguese, matching the existing print style.
- **FR-008**: This feature MUST NOT use an LLM in `generate_report`, MUST NOT modify any transaction, and MUST
  NOT introduce credit-card concepts.

### Key Entities

- **Reimbursement summary** (internal to `generate_report` / `generate_insights`): total reimbursed for the
  month, the per-category attributed amounts, and the unattributed remainder. Not persisted.

## Success Criteria

- **SC-001**: A month with a shared expense plus a `Receita / Reembolso` inflow reports `total_income` with the
  inflow excluded.
- **SC-002**: For that same month, `total_expense` equals gross expense minus the reimbursement, and
  `net_balance` equals `total_income - total_expense`.
- **SC-003**: When the inflow description names the shared category, that category's breakdown entry shows the
  correct gross, reimbursed, and net; when it does not, the amount appears in the unattributed aggregate and no
  category line is wrongly reduced.
- **SC-004**: The insights prompt contains the "R$ X bruto, R$ Y reembolsado, R$ Z líquido" phrasing for
  affected categories, and insights still return a deterministic error (not an exception) when the LLM fails.

## Out of Scope

- **Transaction-to-transaction matching** — pairing a specific reimbursement to the specific expense it offsets
  (a possible later refinement via `human_review`).
- **Verifying the split ratio** — checking that the inflow is ~half (or any fraction) of a real expense.
- **Splitting one reimbursement across multiple categories.**
- **Credit-card concepts** — debit vs credit streams are another feature's concern (feature C's report
  restructure); this feature keeps its changes localized to the reimbursement netting.
- **Persisting reimbursement history** across months.

## Assumptions

- The shared taxonomy dataclasses in `state.py` are not modified by this feature; `generate_report` returns a
  thin subclass carrying the extra aggregate fields, and each breakdown entry is a thin subclass carrying
  `gross` / `reimbursed` / `net`.
- Wiring the new report fields through the graph's report-dict projection (`graph.py::_report_node`) so they
  reach the live CLI run is left to feature C's report restructure; the CLI printer already reads them
  defensively (`.get(...)` with a 0 default) so it is correct either way. Tests exercise `generate_report`'s
  returned object directly.
- The user categorizes shared-expense repayments as `Receita / Reembolso` during `human_review`; this feature
  does not detect them automatically.
