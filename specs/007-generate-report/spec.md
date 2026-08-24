# Feature Specification: Generate Report

**Feature Branch**: `007-generate-report`

**Created**: 2026-08-24

**Status**: Draft

**Input**: User description: "Generate report (the `generate_report` node of the graph): assembles the final
month's report — total income, total expense, net balance, full category breakdown, the internal-transfer total
kept separate, and the budget comparison and insights already computed by earlier nodes — into a single
structured result. Does not use an LLM; purely aggregates data already produced by features 001-006. This is the
graph's last node, closing the MVP described in the BRD."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the complete financial picture for the month in one place (Priority: P1)

As a user, I want a single assembled report with total income, total expense, net balance, and the full
category-by-category breakdown, so I can see and verify my complete financial picture for the month at a glance,
instead of piecing it together from separate outputs.

**Why this priority**: It's the entire point of this feature and of the whole pipeline — every earlier node exists
to make this final, trustworthy picture possible.

**Independent Test**: Can be tested by seeding a month's fully processed transactions and verifying the report's
total income, total expense, net balance, and category breakdown all match manual arithmetic on those
transactions.

**Acceptance Scenarios**:

1. **Given** a fully processed month with income and expense transactions across several categories, **When**
   the report is generated, **Then** it includes the correct total income, total expense, net balance
   (income minus expense), and a breakdown listing every category that had any activity, with its total.
2. **Given** a category with any confirmed spend or income this month, **When** the report is generated, **Then**
   that category appears in the breakdown — whether or not it has a configured budget goal.
3. **Given** a month with no transactions at all, **When** the report is generated, **Then** it shows all-zero
   totals and an empty breakdown, not an error.

---

### User Story 2 - Keep internal transfers out of the income/expense picture (Priority: P1)

As a user, I want confirmed internal transfers reported separately from income and expense, so the amount of
money that actually came in or went out isn't inflated by money that just moved between my own accounts.

**Why this priority**: This is the same rule the pipeline has enforced since feature 002 (transfers excluded from
totals) — the final report is exactly where getting this wrong would be most visible and most damaging to trust
in the numbers.

**Independent Test**: Can be tested by seeding a confirmed internal-transfer transaction alongside real income and
expense, and verifying its amount appears only in the separate transfer total, never in total income, total
expense, net balance, or the category breakdown.

**Acceptance Scenarios**:

1. **Given** a transaction confirmed as "Internal Transfer", **When** the report is generated, **Then** its
   amount is included in a separate transfer total and excluded from total income, total expense, net balance,
   and the category breakdown.

---

### User Story 3 - Bring the budget comparison and insights into the same report (Priority: P2)

As a user, I want the budget comparison and the generated insights summary included alongside the raw numbers in
the same report, so everything about my month lives in one place instead of being scattered across separate
pipeline steps.

**Why this priority**: The data already exists by this point in the pipeline (features 005 and 006) — assembling
it into the same result is what turns three separate computations into one coherent report.

**Independent Test**: Can be tested by running the full pipeline through budget check and insight generation, then
verifying the assembled report contains exactly the same budget comparison and insights result those earlier
steps produced, unmodified.

**Acceptance Scenarios**:

1. **Given** a budget comparison already computed for the month, **When** the report is generated, **Then** it
   includes that same comparison, unmodified.
2. **Given** an insights summary (or a recorded generation failure) already produced for the month, **When** the
   report is generated, **Then** it includes that same result, unmodified.

### Edge Cases

- A month with zero transactions: all totals are zero, the category breakdown is empty — a valid, unremarkable
  result, not an error (User Story 1, third acceptance scenario).
- A transaction whose `confidence` isn't `high` when this node runs (shouldn't happen this late in the graph):
  excluded from every total, the same safety rule already applied by `budget_check` and `generate_insights`.
- No budget comparison or insights result available (e.g. insight generation failed): the report still assembles
  successfully, carrying through whatever was actually produced (including a recorded failure reason for
  insights) rather than requiring both to have succeeded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute total income (`type = income`, `confidence = high`) for the processed
  month.
- **FR-002**: The system MUST compute total expense (`type = expense`, `confidence = high`, excluding "Internal
  Transfer") for the processed month.
- **FR-003**: The system MUST compute the net balance as total income minus total expense.
- **FR-004**: The system MUST include a category breakdown covering every category with any confirmed activity
  this month — not limited to categories with a configured budget goal.
- **FR-005**: The system MUST compute the total amount confirmed as "Internal Transfer" separately, and MUST
  exclude it from total income, total expense, net balance, and the category breakdown.
- **FR-006**: The system MUST include the budget comparison already computed by `budget_check`, unmodified.
- **FR-007**: The system MUST include the insights result already produced by `generate_insights` (summary or
  recorded failure), unmodified.
- **FR-008**: This feature MUST NOT modify any transaction, budget goal, or merchant memory entry — it only reads
  already-finalized data and assembles a computed result.
- **FR-009**: This feature MUST NOT use an LLM — it only aggregates numbers and passes through text already
  generated by an earlier node.
- **FR-010**: The assembled report MUST include the count of transactions its totals are based on, so those
  totals can be sanity-checked against the source data.

### Key Entities *(include if feature involves data)*

- **Monthly report**: this feature's assembled output — total income, total expense, net balance, transfer
  total, category breakdown, transaction count, plus the budget comparison and insights result carried through
  from earlier nodes. Not persisted — it's the graph's final computed result for the month.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Total income minus total expense always equals the reported net balance, and both are verifiable
  against a manual sum of the month's source transactions.
- **SC-002**: The transfer total never appears in total income, total expense, net balance, or the category
  breakdown.
- **SC-003**: Every category with any confirmed activity this month appears in the breakdown, whether or not it
  has a configured budget goal.
- **SC-004**: The report's budget comparison and insights sections exactly match what `budget_check` and
  `generate_insights` already produced — nothing lost, nothing re-derived differently.
- **SC-005**: No transaction, budget goal, or merchant memory entry is ever modified by this feature.

## Assumptions

- Formatting the report for display (or saving it to a file) is the CLI's responsibility, not this node's — this
  feature's job ends at producing the structured report data, the same boundary already established by
  `budget_check` and `generate_insights` handing computed data to the CLI for presentation.
- There's no persistence of past months' reports yet — like the budget comparison and insights, this is computed
  fresh each run. A history of past reports, if it turns out to be useful, is a future feature's concern.
- The category breakdown includes both income and expense categories (e.g. "Receita" alongside "Alimentação"),
  each tagged with its type, since BRD 5.4 already establishes that the system tracks complete movement, not just
  spend.
