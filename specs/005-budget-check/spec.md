# Feature Specification: Budget Check

**Feature Branch**: `005-budget-check`

**Created**: 2026-08-24

**Status**: Draft

**Input**: User description: "Budget check (the `budget_check` node of the graph): compares actual spending per
category, for a fully processed month, against the user's configured budget goals. Reads goals through a
swappable function (`get_budget()`), backed by a local config file in Phase 1. Excludes internal transfers and
income from spend totals. Does not use an LLM. Consumes the output of features 001-004 (fully categorized,
reviewed, memorized transactions); its output feeds the not-yet-built insights/report nodes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See actual spend against each budget goal (Priority: P1)

As a user, I want to see, for every category I've set a monthly goal for, how much I actually spent versus that
goal, so I know exactly where I'm within budget and where I've overspent.

**Why this priority**: It's the entire point of the feature — without this comparison there's no budget check at
all, just a pile of categorized transactions with no goals attached.

**Independent Test**: Can be tested by configuring a goal for a category, seeding transactions in that category
for a month, and verifying the reported actual spend matches the sum of those transactions, compared correctly
against the goal.

**Acceptance Scenarios**:

1. **Given** a category with a configured monthly goal and transactions in that category totaling less than the
   goal, **When** the budget check runs, **Then** the category is reported as within budget, with the exact
   amount spent and the remaining headroom.
2. **Given** a category with a configured monthly goal and transactions in that category totaling more than the
   goal, **When** the budget check runs, **Then** the category is reported as over budget, with the exact amount
   spent and the exact amount over.
3. **Given** a category with a configured monthly goal and total spend exactly equal to the goal, **When** the
   budget check runs, **Then** the category is reported as within budget (not over) — hitting the goal exactly is
   not overspending.
4. **Given** a category with a configured monthly goal but no transactions at all this month, **When** the budget
   check runs, **Then** the category is reported with zero actual spend, clearly within budget.

---

### User Story 2 - Keep transfers and income out of spend totals (Priority: P1)

As a user, I want internal transfers and income to never count as spending against any budget goal, so a goal
isn't wrongly flagged as blown by money that was never actually spent.

**Why this priority**: A transfer between the user's own accounts isn't spending, and income obviously isn't
spending either — including either would make every goal's comparison meaningless.

**Independent Test**: Can be tested by seeding a transfer-confirmed transaction and an income transaction in a
category that also has a configured goal, and verifying neither contributes to that goal's actual-spend total.

**Acceptance Scenarios**:

1. **Given** a transaction confirmed as "Internal Transfer", **When** the budget check computes spend for any
   category, **Then** that transaction's amount is never included in any total.
2. **Given** an income transaction (`type = income`) in a category that also has expense transactions and a
   configured goal, **When** the budget check runs, **Then** only the expense transactions count toward that
   category's actual spend.

### Edge Cases

- No local budget configuration exists at all (first-time setup): the system MUST fail with a clear, explicit
  message pointing the user to the example configuration — never silently produce an empty or misleading report
  that looks identical to "the user deliberately configured zero goals."
- A valid budget configuration exists but defines zero goals: this is a legitimate (if unusual) state — the
  system produces an empty comparison, not an error.
- A category appears in the budget configuration but was never seen in the categorization taxonomy (e.g. a typo
  in the goal file): still compared as configured — this feature doesn't validate goal category names against the
  taxonomy, since a goal can reasonably be set even before any transaction in that category ever appears.
- A transaction's `confidence` is somehow not `high` when this node runs (shouldn't happen, since the graph only
  reaches this node after every transaction is fully resolved): it MUST be excluded from spend totals, the same
  safety rule already applied by the merchant memory update feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every category with a configured monthly goal, the system MUST compute that category's total
  expense (`type = expense` only) for the processed month.
- **FR-002**: Transactions with `category = "Internal Transfer"` MUST NOT count toward any category's spend total.
- **FR-003**: Transactions with `type = income` MUST NOT count toward any category's spend total.
- **FR-004**: For each configured category, the system MUST report whether actual spend is within or over the
  goal, including the exact amount spent and the exact difference from the goal (remaining headroom if within,
  amount over if over).
- **FR-005**: Spend exactly equal to the goal MUST be reported as within budget, not over.
- **FR-006**: Categories without a configured goal MUST NOT appear in the comparison output.
- **FR-007**: The system MUST read budget goals through a swappable function, backed by a local configuration
  file in this phase, so the goal source can change later (e.g. to a hosted database) without changing this
  feature's comparison logic.
- **FR-008**: When no local budget configuration exists at all, the system MUST fail with an explicit, clear
  message — never silently treat a missing configuration the same as a deliberately empty one.
- **FR-009**: This feature MUST NOT modify any transaction — it only reads already-finalized transactions and
  produces a computed comparison.
- **FR-010**: The system MUST exclude any transaction whose `confidence` isn't `high` from spend totals, as a
  safety check even though the graph is expected to guarantee this never happens in practice.

### Key Entities *(include if feature involves data)*

- **Budget goal**: a category and its configured monthly spending limit, read from local configuration.
- **Category spend summary**: the computed result for one category — goal, actual spend, and whether it's within
  or over budget, with the exact difference. Not a persisted entity — it's this feature's output, meant to feed
  the not-yet-built insights/report nodes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every category with a configured goal shows its actual spend, correctly compared against that goal.
- **SC-002**: No comparison's actual-spend figure ever includes a confirmed internal transfer or an income
  transaction.
- **SC-003**: No category without a configured goal ever appears in the output.
- **SC-004**: A missing budget configuration always produces an explicit, actionable failure — never a silent
  empty report.
- **SC-005**: No transaction's `category`, `subcategory`, or `confidence` is altered by this feature.

## Assumptions

- Budget goals are monthly and apply to the same `month_ref` the rest of the pipeline already uses — there's no
  concept of a rolling or annual goal in this phase.
- A goal configured for a category that behaves unusually (e.g. someone sets a goal on "Internal Transfer" or
  "Receita") is still technically accepted by this feature — actual spend for such a category will simply always
  be zero (transfers and income never count), which is a harmless, self-explanatory outcome rather than something
  worth specially rejecting.
- This feature's output isn't written to the database — it's computed fresh each time the graph runs for a month,
  and handed to whichever node consumes it next (the future insights/report nodes). If a persisted history of past
  budget comparisons turns out to be useful, that's a future feature's concern.
- Categories without a configured goal simply don't get a comparison — this feature doesn't attempt to surface
  "you spent money in a category with no goal" as a finding; that kind of broader commentary belongs to the future
  insights node, not this one.
