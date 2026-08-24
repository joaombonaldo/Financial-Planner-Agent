---

description: "Task list template for feature implementation"
---

# Tasks: Budget Check

**Input**: Design documents from `/specs/005-budget-check/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/budget-node.md, quickstart.md

**Tests**: Included — no LLM, no human interaction, so tests are plain and fast, required by the same discipline
used across the project.

**Organization**: Tasks are grouped by user story (US1/US2, per spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Create `backend/src/financial_planner/budget/__init__.py`
- [X] T002 [P] Create `backend/src/financial_planner/config/budget.example.yaml` with fictitious goal values
      (versioned; the real `budget.local.yaml` stays gitignored, per BRD section 8)

**Checkpoint**: directory and example config ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks both user stories below.

- [X] T003 Add `CategoryComparison` (category, goal, actual_spend, difference, status) and
      `BudgetNotConfiguredError` to `backend/src/financial_planner/state.py`
- [X] T004 Add a `budget_report` field to `GraphState` in `backend/src/financial_planner/graph_state.py`
- [X] T005 Implement `get_budget(path=None)` in `backend/src/financial_planner/budget/config.py` — reads
      `config/budget.local.yaml` by default, raises `BudgetNotConfiguredError` when missing, returns `{}` when
      present but empty (depends on T001, T003)

**Checkpoint**: foundation ready — both user stories can start.

---

## Phase 3: User Story 1 - See actual spend against each budget goal (Priority: P1) 🎯 MVP

**Goal**: for every configured category, report actual expense vs. goal, correctly classified as within or over
budget, including the zero-transactions and exact-equality edge cases.

**Independent Test**: configure a goal, seed transactions, verify the reported comparison matches manual
arithmetic (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T006 [P] [US1] Test: spend under the goal is reported `within_budget` with the correct `actual_spend`/
      `difference`, in `backend/tests/test_budget.py::test_budget_within_budget`
- [X] T007 [P] [US1] Test: spend over the goal is reported `over_budget` with the correct amount over, in
      `backend/tests/test_budget.py::test_budget_over_budget`
- [X] T008 [P] [US1] Test: spend exactly equal to the goal is reported `within_budget`, not over, in
      `backend/tests/test_budget.py::test_budget_exact_equal_is_within`
- [X] T009 [P] [US1] Test: a configured category with zero transactions this month reports `actual_spend = 0`,
      within budget, in `backend/tests/test_budget.py::test_budget_zero_transactions_category`
- [X] T010 [P] [US1] Test: a missing budget configuration raises `BudgetNotConfiguredError`, in
      `backend/tests/test_budget.py::test_budget_missing_config_raises_error`

### Implementation for User Story 1

- [X] T011 [US1] Implement `check_budget(month_ref, db_path, budget_path=None)` in
      `backend/src/financial_planner/nodes/budget.py` (depends on T003, T005)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 4: User Story 2 - Keep transfers and income out of spend totals (Priority: P1)

**Goal**: confirmed internal transfers and income transactions never count toward any category's actual spend.

**Independent Test**: seed a transfer and an income transaction alongside real expenses, verify neither affects
the comparison (Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T012 [P] [US2] Test: a transaction confirmed as "Internal Transfer" never counts toward any category's
      spend, in `backend/tests/test_budget.py::test_budget_excludes_transfers`
- [X] T013 [P] [US2] Test: an income transaction never counts toward any category's spend, in
      `backend/tests/test_budget.py::test_budget_excludes_income`

### Implementation for User Story 2

*No new code — already covered by the filter implemented in T011 (`type == 'expense'` and
`category != TRANSFER_CATEGORY`). This story's tests (T012/T013) verify existing behavior; adjust
`nodes/budget.py` only if they reveal a gap.*

**Checkpoint**: both user stories work together — every configured category's comparison reflects real spend
only.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T014 [P] Extend `graph.py`: `update_memory` → `END` becomes `update_memory` → `budget_check` → `END`; the
      node wrapper converts `check_budget()`'s dataclass list into plain dicts for `budget_report` (see
      research.md — checkpointer-safe state shape)
- [X] T015 [P] Add a lightweight full-chain smoke test driving the real graph end to end with a configured budget,
      confirming `budget_report` comes back populated and correctly excludes transfers — in
      `backend/tests/test_budget.py`, following the same no-LLM pattern as feature 004's smoke test (pre-populate
      merchant memory so `categorize` never needs the LLM)
- [X] T016 Review `nodes/budget.py` against Principle II of the constitution (transactions only via
      `db/repository.py`, goals only via `budget/config.py`)
- [X] T017 [P] Run the `quickstart.md` scenarios manually against real transactions already imported/categorized/
      reviewed (via features 001-004, data outside the repository) with a real personal budget configuration
- [X] T018 [P] Document in `backend/README.md` how to set up `config/budget.local.yaml` (copy from
      `budget.example.yaml`) and that `budget_check` is now part of the graph

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately
- **Foundational (Phase 2)**: depends on Setup — blocks both user stories
- **User Stories (Phase 3-4)**: both depend on Foundational
  - US2 depends on the filter already built in US1's implementation (T011) — its own phase adds no new code,
    only verifying tests
- **Polish (Phase 5)**: depends on both user stories being complete

### Parallel Opportunities

- T001, T002 (Setup) in parallel
- T006-T010 (US1 tests) in parallel with each other
- T012, T013 (US2 tests) in parallel with each other
- T014, T015, T017, T018 (Polish) in parallel with each other

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phase 3 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point, every configured category's spend is already compared correctly — MVP of the feature

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 → per-category comparison (MVP)
3. US2 → transfers/income correctly excluded (verification, not new logic)
4. Polish → wired into the real graph + end-to-end validation with real data

---

## Notes

- No LLM, no human interaction — every test in this feature is a plain, deterministic function/graph call
- Tests never touch the real, gitignored `config/budget.local.yaml` — they always pass an explicit `budget_path`
  pointing at a `tmp_path` fixture file
- A persisted history of past budget comparisons stays out of scope, per spec.md Assumptions
- Commit after each task or logical group of tasks

- **Cross-feature regression found and fixed during T014**: `budget_check` becoming a mandatory part of the graph
  chain (`update_memory` → `budget_check` → `END`) broke feature 004's full-chain smoke test
  (`test_full_chain_remembers_merchant_across_months`), since it invoked the graph without a `budget_path` and hit
  the real, missing `BudgetNotConfiguredError`. Fixed by adding a `budget_path` field to `GraphState` (so tests —
  and, if ever needed, callers — can point at an explicit config without touching the real file) and updating that
  test to supply one. Full suite: 38/38 passing after the fix.
- **T017 completed** with the full graph (real Ollama) against both real months (`2026-07`, `2026-08`) and an
  example budget config (copied from `budget.example.yaml`, kept local/gitignored):
  - August's "Transporte" category came back `over_budget`: R$ 433.56 spent against a R$ 300.00 goal — manually
    cross-checked against the database (`SUM(amount) WHERE category='Transporte' AND type='expense' AND
    confidence='high'` for `2026-08`) and it matches exactly.
  - Categories without a configured goal (e.g. "Outros", "Cartão de crédito/Parcelamentos", "Receita") correctly
    never appeared in the printed report (FR-006/SC-003).
  - No transfer or income transaction affected any total (verified directly on "Transporte", which had zero
    income/transfer transactions to begin with — SC-002 held throughout).
