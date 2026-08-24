---

description: "Task list template for feature implementation"
---

# Tasks: Generate Insights

**Input**: Design documents from `/specs/006-generate-insights/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/insights-node.md, quickstart.md

**Tests**: Included — the LLM is always mocked (constitution), so tests are deterministic and fast.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2, US3)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all three user stories below. No Setup phase needed — no new dependencies or directories.

- [X] T001 Extract `compute_category_spend(transactions)` into
      `backend/src/financial_planner/budget/spending.py`; refactor
      `backend/src/financial_planner/nodes/budget.py::check_budget` to use it; re-run `test_budget.py` to confirm
      no behavior change (see research.md — shared spend calculation)
- [X] T002 Add `InsightsResult` (summary, error) to `backend/src/financial_planner/state.py`
- [X] T003 Add `insights_summary`/`insights_error` fields to `GraphState` in
      `backend/src/financial_planner/graph_state.py`
- [X] T004 Add a `RaisingChatModel` double (raises a given exception on `invoke()`) to
      `backend/tests/fixtures/categorization/llm_double.py`, alongside the existing `FakeChatModel`

**Checkpoint**: foundation ready — all three user stories can start.

---

## Phase 2: User Story 1 - Get a plain-language summary of where the money went (Priority: P1) 🎯 MVP

**Goal**: a natural-language Portuguese summary is generated, grounded in the current month's real category spend
and budget comparison.

**Independent Test**: seed a month's data, run generation with a fake model that records its prompt, verify the
summary and the prompt content (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T005 [P] [US1] Test: the generated summary matches the fake model's response, and the prompt includes the
      real per-category spend, in
      `backend/tests/test_insights.py::test_insights_summary_grounded_in_real_data`
- [X] T006 [P] [US1] Test: the prompt includes the budget comparison when `budget_report` is given, in
      `backend/tests/test_insights.py::test_insights_includes_budget_report_in_context`

### Implementation for User Story 1

- [X] T007 [US1] Implement `generate_insights(month_ref, db_path, budget_report=None, chat_model=None)` in
      `backend/src/financial_planner/nodes/insights.py`: build the prompt from current-month spend + budget
      report, call the LLM inside a broad `try/except` (never raises, per FR-006 — built here since a correct
      implementation can't reasonably defer it), return `InsightsResult` (depends on T001, T002)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 3: User Story 2 - See how spending changed versus last month (Priority: P2)

**Goal**: when data exists for the immediately preceding month, the LLM's context includes a category-by-category
comparison; when it doesn't, generation still succeeds without a fabricated comparison.

**Independent Test**: seed two consecutive months, verify both appear in the prompt; seed only the current month,
verify generation still succeeds with no comparison claimed (Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T008 [P] [US2] Test: with data for both the current and previous month, the prompt includes both months'
      category totals, in
      `backend/tests/test_insights.py::test_insights_includes_previous_month_comparison`
- [X] T009 [P] [US2] Test: with no previous-month data, generation still succeeds and the prompt claims no
      comparison, in `backend/tests/test_insights.py::test_insights_first_month_no_comparison`

### Implementation for User Story 2

- [X] T010 [US2] Extend `generate_insights` to compute the previous `month_ref` (see research.md), read that
      month's transactions, and include its category spend in the prompt only when non-empty (depends on T007)

**Checkpoint**: User Story 1 and 2 work together — the summary reflects both the current month and, when
available, the trend against the previous one.

---

## Phase 4: User Story 3 - Never let an LLM failure block the month's processing (Priority: P2)

**Goal**: any LLM failure (error, timeout, blank/malformed response) is recorded as a clear failure reason,
without raising.

**Independent Test**: force the LLM call to fail, verify the function returns an `InsightsResult` with `error`
set instead of raising (Scenario 3 of `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T011 [P] [US3] Test: an LLM call that raises results in `InsightsResult(summary=None, error=...)`, never
      propagates, in `backend/tests/test_insights.py::test_insights_llm_failure_returns_error_not_raise` (uses
      `RaisingChatModel` from T004)
- [X] T012 [P] [US3] Test: a blank/whitespace-only response is treated the same as a failure, in
      `backend/tests/test_insights.py::test_insights_blank_response_treated_as_failure`

### Implementation for User Story 3

*No new code — the broad `try/except` and blank-response check were already built as part of T007, since
`generate_insights` couldn't reasonably be implemented correctly without them. These tests verify that existing
behavior; adjust `nodes/insights.py` only if they reveal a gap.*

**Checkpoint**: all three user stories work together — a grounded, trend-aware summary that degrades safely on
any LLM problem.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T013 [P] Extend `graph.py`: `budget_check` → `END` becomes `budget_check` → `generate_insights` → `END`;
      the node wrapper passes `state.get("budget_report")` straight through to `generate_insights` (see
      research.md — no recomputation)
- [X] T014 [P] Add a lightweight full-chain smoke test driving the real graph end to end with a mocked LLM,
      confirming `insights_summary` comes back populated — in `backend/tests/test_insights.py`, following the
      same no-real-LLM pattern as features 004/005's smoke tests
- [X] T015 Review `nodes/insights.py` against Principle II of the constitution (transactions only via
      `db/repository.py`, LLM only via `llm/client.py`)
- [X] T016 [P] Run the `quickstart.md` scenarios manually against real transactions already
      imported/categorized/reviewed (via features 001-005, data outside the repository), using the real Ollama
      client, to validate end to end
- [X] T017 [P] Document in `backend/README.md` that `generate_insights` is now part of the graph and always
      produces either a summary or a recorded failure reason, never a crash

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: no dependencies — can start immediately
- **User Stories (Phase 2-4)**: all depend on Foundational
  - US2 and US3 both extend the same function built in US1 (T007 → T010), so in practice they're sequential
    (US1 → US2 → US3) even though independently testable — US3 in particular needs no new code at all, since
    T007 already had to build the failure handling to be a correct implementation in the first place
- **Polish (Phase 5)**: depends on all three user stories being complete

### Parallel Opportunities

- T002, T003, T004 (Foundational, after T001) in parallel with each other
- T005, T006 (US1 tests) in parallel with each other
- T008, T009 (US2 tests) in parallel with each other
- T011, T012 (US3 tests) in parallel with each other
- T013, T014, T016, T017 (Polish) in parallel with each other

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Foundational)
2. Complete Phase 2 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point, every processed month already gets a grounded summary — MVP of the feature

### Incremental Delivery

1. Foundational → base ready (includes the shared spend-calculation refactor)
2. US1 → grounded single-month summary (MVP)
3. US2 → trend comparison against the previous month
4. US3 → verified graceful degradation on LLM failure (no new code)
5. Polish → wired into the real graph + end-to-end validation with real data

---

## Notes

- The LLM is always mocked in automated tests — the one exception is T016's manual validation, which
  deliberately uses the real Ollama client
- No transaction, budget goal, or merchant memory entry is ever touched by this feature — purely read + generate
- A persisted history of past summaries stays out of scope, per spec.md Assumptions
- Commit after each task or logical group of tasks

- **T016 completed** with the full graph (real Ollama) against both real months (`2026-07`, `2026-08`), each
  producing a grounded Portuguese summary with `insights_error = None`:
  - August correctly identified "Transporte" as over budget by R$ 133.56 — matching the exact figure already
    validated numerically in feature 005.
  - **Finding, not a bug**: July's summary claimed "a categoria Educação excedeu significativamente o orçamento
    estabelecido" — but "Educação" has no configured goal in `budget.local.yaml` at all (only Moradia,
    Alimentação, Transporte, Saúde, Assinaturas, Lazer are configured). The LLM conflated a large number in the
    "spend per category" section of the prompt with the separate "budget comparison" section, inventing a
    goal-exceeded claim that isn't actually present anywhere in the given context. This is exactly the kind of
    LLM imprecision the categorization feature already established a trust model for (spec.md's own Assumptions:
    "the LLM is trusted to describe the numbers it's given accurately") — there's no human-review step for
    insights text the way there is for categorization, so this kind of factual slip can currently reach the user
    unfiltered. Worth a future refinement (e.g., explicitly telling the LLM which categories have no configured
    goal) if this pattern shows up often in real use; out of scope for this feature as specified.
