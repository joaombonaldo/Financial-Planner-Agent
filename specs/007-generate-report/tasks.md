---

description: "Task list template for feature implementation"
---

# Tasks: Generate Report

**Input**: Design documents from `/specs/007-generate-report/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/report-node.md, quickstart.md

**Tests**: Included — no LLM, no human interaction, so tests are plain and fast, required by the same discipline
used across the project.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2, US3)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all three user stories below. No Setup phase needed — no new dependencies or directories.

- [X] T001 Add `CategoryBreakdownEntry` (category, type, total) and `MonthlyReport` (month_ref, total_income,
      total_expense, net_balance, transfer_total, category_breakdown, transaction_count, budget_report,
      insights_summary, insights_error) to `backend/src/financial_planner/state.py`
- [X] T002 Add a `report` field to `GraphState` in `backend/src/financial_planner/graph_state.py`

**Checkpoint**: foundation ready — all three user stories can start.

---

## Phase 2: User Story 1 - See the complete financial picture for the month in one place (Priority: P1) 🎯 MVP

**Goal**: total income, total expense, net balance, and a full category breakdown (every category with activity,
goal or no goal) are correctly assembled for the month.

**Independent Test**: seed transactions across several categories, verify the report's totals and breakdown match
manual arithmetic (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T003 [P] [US1] Test: total income, total expense, and net balance match manual arithmetic on seeded
      transactions, in `backend/tests/test_report.py::test_report_totals_match_manual_arithmetic`
- [X] T004 [P] [US1] Test: the category breakdown includes a category with no configured budget goal, in
      `backend/tests/test_report.py::test_report_breakdown_includes_non_goal_categories`
- [X] T005 [P] [US1] Test: a month with zero transactions produces all-zero totals and an empty breakdown, no
      error, in `backend/tests/test_report.py::test_report_zero_transactions_all_zero`

### Implementation for User Story 1

- [X] T006 [US1] Implement `generate_report(month_ref, db_path, budget_report=None, insights_summary=None,
      insights_error=None)` in `backend/src/financial_planner/nodes/report.py`: read the month's transactions,
      accumulate totals and the `(category, type)` breakdown, assemble `MonthlyReport` (depends on T001)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 3: User Story 2 - Keep internal transfers out of the income/expense picture (Priority: P1)

**Goal**: a confirmed internal transfer's amount appears only in `transfer_total`, never in total income, total
expense, net balance, or the category breakdown.

**Independent Test**: seed a transfer alongside real income/expense, verify it only shows up in `transfer_total`
(Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T007 [P] [US2] Test: a transaction confirmed as "Internal Transfer" is excluded from total income, total
      expense, net balance, and the category breakdown — appearing only in `transfer_total`, in
      `backend/tests/test_report.py::test_report_excludes_transfers_from_totals`

### Implementation for User Story 2

*No new code — already covered by the branch implemented in T006 (transfers routed to `transfer_total`, never to
the income/expense accumulators or the breakdown). This story's test (T007) verifies existing behavior; adjust
`nodes/report.py` only if it reveals a gap.*

**Checkpoint**: both user stories work together — the report's income/expense picture is never inflated by
transfers.

---

## Phase 4: User Story 3 - Bring the budget comparison and insights into the same report (Priority: P2)

**Goal**: the budget comparison and insights result already computed by earlier nodes appear in the assembled
report exactly as given, never recomputed or altered.

**Independent Test**: pass a constructed budget comparison and insights result in, verify they come back
unmodified in the report (Scenario 3 of `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T008 [P] [US3] Test: a given `budget_report` and `insights_summary`/`insights_error` are carried through to
      the assembled `MonthlyReport` unmodified, in
      `backend/tests/test_report.py::test_report_carries_budget_and_insights_through_unmodified`

### Implementation for User Story 3

*No new code — already covered by T006's direct pass-through of the `budget_report`/`insights_summary`/
`insights_error` parameters. This story's test (T008) verifies existing behavior.*

**Checkpoint**: all three user stories work together — a single, complete, faithful report for the month.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T009 [P] Extend `graph.py`: `generate_insights` → `END` becomes `generate_insights` → `generate_report` →
      `END`; the node wrapper passes `budget_report`/`insights_summary`/`insights_error` from state straight
      through and converts the returned `MonthlyReport` into a plain dict for the `report` field
- [X] T010 [P] Add a lightweight full-chain smoke test driving the real graph end to end with a mocked LLM,
      confirming the final `report` field comes back fully populated — in `backend/tests/test_report.py`,
      following the same pattern as every prior feature's smoke test
- [X] T011 Review `nodes/report.py` against Principle II of the constitution (transactions only via
      `db/repository.py`)
- [X] T012 [P] Run the `quickstart.md` scenarios manually against real transactions already fully processed (via
      features 001-006, data outside the repository) to validate end to end — this closes out the BRD's MVP
      acceptance criteria (section 10)
- [X] T013 [P] Document in `backend/README.md` that the CLI now prints the assembled report at the end of a run,
      and update `interface/cli.py` to print `total_income`/`total_expense`/`net_balance`/`transfer_total` from
      the graph's final `report` field

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: no dependencies — can start immediately
- **User Stories (Phase 2-4)**: all depend on Foundational
  - US2 and US3 both verify behavior already built as part of US1's implementation (T006) — their phases add no
    new code, only verifying tests
- **Polish (Phase 5)**: depends on all three user stories being complete

### Parallel Opportunities

- T003, T004, T005 (US1 tests) in parallel with each other
- T009, T010, T012, T013 (Polish) in parallel with each other

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Foundational)
2. Complete Phase 2 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point, the complete financial picture for the month is already assembled — MVP of the feature, and of
   the whole pipeline

### Incremental Delivery

1. Foundational → base ready
2. US1 → complete totals and breakdown (MVP)
3. US2 → transfers correctly excluded (verification, not new logic)
4. US3 → budget/insights correctly carried through (verification, not new logic)
5. Polish → wired into the real graph + CLI prints the final report + end-to-end validation with real data,
   closing the BRD's MVP scope

---

## Notes

- No LLM, no human interaction — every test in this feature is a plain, deterministic function/graph call
- This is the graph's last node — completing this feature closes the MVP acceptance criteria in BRD section 10
- A persisted history of past reports stays out of scope, per spec.md Assumptions
- Commit after each task or logical group of tasks

- **T012 completed** with the full graph (real Ollama) against both real months (`2026-07`, `2026-08`), closing
  out BRD section 10's MVP acceptance criteria:
  - **Criterion 1** ("process a real month from 2 banks without error"): both months processed end to end,
    `insights_error = None` in both.
  - **Criterion 3** ("final report matches a manually verified sum from the statement"): `total_income`,
    `total_expense`, `net_balance`, `transfer_total`, and `transaction_count` from the graph's `report` field
    matched a manual SQL cross-check (`SUM(amount) ... GROUP BY type/category`) exactly, for both months.
  - **Finding, not a bug**: the category breakdown surfaced two real LLM categorization quirks more visibly than
    any single-transaction view had before — an income transaction ("Imobiliaria Vila Rica", a real-estate
    agency) legitimately categorized as `Moradia` + `income` (correct: money received related to housing, not a
    miscategorization — validates the design decision to key the breakdown by `(category, type)` instead of
    assuming a category is exclusively income or expense), and a CDB investment purchase miscategorized as
    `Receita` + `expense` (genuinely wrong: buying an investment isn't income) — consistent with this same
    transaction's known categorization difficulty already noted in earlier features' findings and in the BRD
    itself (an "Aplicação" category is planned for Phase 3). Not a `generate_report` bug: the node faithfully
    reflects whatever `category`/`type` the transaction already has by this point in the pipeline.
