---

description: "Task list template for feature implementation"
---

# Tasks: Human Review of Transactions

**Input**: Design documents from `/specs/003-human-review/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/review-node.md, quickstart.md

**Tests**: Included — the constitution requires the graph to be testable deterministically; here that means
driving the `interrupt()`/`Command(resume=...)` loop programmatically, with no real terminal.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2, US3)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Add `langgraph-checkpoint-sqlite` as a dependency (`uv add langgraph-checkpoint-sqlite` in
      `backend/`)
- [X] T002 [P] Create `backend/src/financial_planner/interface/__init__.py`
- [X] T003 [P] Create `backend/tests/fixtures/review/`

**Checkpoint**: checkpointer dependency resolved, folder structure ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all user stories below.

- [X] T004 Define `GraphState` (TypedDict: `source_files`, `month_ref`, `db_path`) in
      `backend/src/financial_planner/graph_state.py`
- [X] T005 Implement `list_pending_review(conn, month_ref)` (`WHERE month_ref = ? AND confidence != 'high'`) in
      `backend/src/financial_planner/db/repository.py` (see research.md — why this single condition already
      covers transfer candidates)

**Checkpoint**: foundation ready — all three user stories can start.

---

## Phase 3: User Story 1 - Review and correct medium/low confidence transactions (Priority: P1) 🎯 MVP

**Goal**: `confidence != high` transactions are presented to the user via `interrupt()`, one at a time, and the
decision (accept or correct) is persisted with `confidence = high`.

**Independent Test**: populate the database with medium/low confidence items, drive the graph answering each
`interrupt()`, verify the persisted result (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T006 [P] [US1] Create fixture helpers (transactions with varying `confidence`) in
      `backend/tests/fixtures/review/builders.py`
- [X] T007 [P] [US1] Test: accepting the suggestion keeps category/subcategory and becomes `confidence = high`,
      in `backend/tests/test_review.py::test_review_accept_suggestion` (depends on T006)
- [X] T008 [P] [US1] Test: correcting with a different category persists the new category with
      `confidence = high`, in `backend/tests/test_review.py::test_review_correct_with_new_category` (depends on
      T006)
- [X] T009 [P] [US1] Test: a month with nothing pending doesn't interrupt the graph, in
      `backend/tests/test_review.py::test_review_no_pending_items_never_interrupts`
- [X] T010 [P] [US1] Test: a category outside the taxonomy is rejected and the same item is asked again, in
      `backend/tests/test_review.py::test_review_rejects_invalid_category_and_reasks` (depends on T006)

### Implementation for User Story 1

- [X] T011 [US1] Implement `nodes/review.py`: queries pending items, an `interrupt()` loop per item, validates
      against the taxonomy, persists immediately, moves on (depends on T004, T005)
- [X] T012 [US1] Implement `graph.py`: `build_graph(db_path)` — builds the `StateGraph`
      (`detect_and_parse` → `categorize` → `human_review`) with `SqliteSaver` as checkpointer, `thread_id` =
      `month_ref` (depends on T011, T001)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 4: User Story 2 - Confirm or reject transfer candidates (Priority: P1)

**Goal**: transfer candidates (`category = "Transferência interna"`) are confirmed or replaced with a real
category — never left undecided.

**Independent Test**: populate the database with a transfer candidate, confirm and reject in separate runs,
verify the outcome (Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Create a transfer-candidate fixture (`category = "Transferência interna"`,
      `confidence = medium`) in `backend/tests/fixtures/review/builders.py`
- [X] T014 [P] [US2] Test: responding `"confirmar"` keeps "Transferência interna" with `confidence = high`, in
      `backend/tests/test_review.py::test_review_confirm_transfer` (depends on T013)
- [X] T015 [P] [US2] Test: responding with a category replaces "Transferência interna" with the provided
      category, with `confidence = high`, in
      `backend/tests/test_review.py::test_review_reject_transfer_with_new_category` (depends on T013)

### Implementation for User Story 2

- [X] T016 [US2] Extend `nodes/review.py` to recognize `"confirmar"` as a valid response only when the item is a
      transfer candidate, and to treat any category response as rejecting the suggestion (depends on T011)

**Checkpoint**: User Story 1 and 2 work together — every pending item (transfer or not) always ends up decided.

---

## Phase 5: User Story 3 - Resume an interrupted review without losing progress (Priority: P2)

**Goal**: interrupting the process midway through a review and resuming later doesn't lose nor repeat decisions.

**Independent Test**: decide part of the pending items, "interrupt" (stop advancing the graph), verify partial
persistence in the database, resume with the same `thread_id` and verify only the remaining items show up
(Scenario 3 of `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T017 [P] [US3] Test: decide 1 of 3 items, "stop", verify in the database that the decision is already
      persisted before the graph finishes, in
      `backend/tests/test_review.py::test_review_partial_session_persists_immediately`
- [X] T018 [P] [US3] Test: resuming with the same `thread_id` after deciding 1 of 3 items presents the
      **second** item next, never the first one again, in
      `backend/tests/test_review.py::test_review_resume_does_not_reask_decided_items`

### Implementation for User Story 3

- [X] T019 [US3] Verify (no code change expected — see research.md) that `list_pending_review` always queries
      the database directly on every node run, never caching the list in memory between calls — this is the
      property that, together with the checkpointer, guarantees correct resumption. Adjust `nodes/review.py`
      only if the T017/T018 tests reveal some dependency on in-memory state.

**Checkpoint**: all three user stories work independently and together.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 [P] Implement `interface/cli.py`: a minimal loop that invokes the graph, formats each
      `interrupt()`'s payload for the terminal, reads a line from `stdin`, and resumes the graph with that
      response — with no knowledge of taxonomy or business rules (see contracts/review-node.md)
- [X] T021 [P] Run the `quickstart.md` scenarios manually against real transactions already
      imported/categorized (via features 001/002, data outside the repository) using the real CLI, to validate
      end-to-end
- [X] T022 Review `nodes/review.py` against Principle II of the constitution (database access only via
      `db/repository.py`; `graph.py` and `interface/cli.py` are the only pieces that legitimately import
      `langgraph`/handle stdin directly)
- [X] T023 [P] Document in `backend/README.md` how to run a review session via CLI and how this feature's tests
      drive the graph with no real terminal

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories
- **User Stories (Phase 3-5)**: all depend on Foundational
  - US2 extends the same `nodes/review.py` created in US1 (T011 → T016), so in practice it's sequential
    (US1 → US2); US3 shouldn't require a code change if the "always query the database fresh" design holds up —
    it's mostly a verification phase
- **Polish (Phase 6)**: depends on all desired user stories being complete

### Within Each User Story

- Tests are written before implementation and must fail first
- Fixtures before the tests that use them
- `graph.py` (T012) depends on the `human_review` node already existing, since it's the third node in the chain

### Parallel Opportunities

- T001, T002, T003 (Setup) in parallel
- T007, T008, T009, T010 (US1 tests) in parallel with each other, after T006
- T014, T015 (US2 tests) in parallel with each other, after T013
- T017, T018 (US3 tests) in parallel with each other

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phase 3 (US1) — includes `graph.py`, the first real `StateGraph` assembly
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point it's already possible to review and correct any medium/low confidence transaction — the
   feature's MVP

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 → functional review + graph assembled (MVP)
3. US2 → transfers always decided, never forgotten
4. US3 → safe resumption after an interruption
5. Polish → a real minimal CLI + end-to-end validation with real data

---

## Notes

- All test tasks drive the graph programmatically (no real terminal) — none depends on real financial data nor
  on an LLM (this node doesn't use one)
- Writing confirmations into `merchant_memory` remains out of scope (future feature `update_memory`)
- Excluding confirmed transfers from totals remains out of scope (future feature `budget_check`)

- **T021 completed** with the full graph (real Ollama) against the real Bradesco + Inter data, driving the
  `interrupt()`/`Command(resume=...)` loop programmatically:
  - 89/89 transactions ended up with `confidence = high` and `category` never `NULL`, across both months
    covered by the statement (the 89 transactions split between `month_ref = "2026-07"` and `"2026-08"`, since
    the export's period runs from 24/07 to 22/08/2026)
  - **Finding, not a code bug**: the statement spans two calendar months — running the graph only for
    `"2026-08"` leaves July's transactions untouched (no category, no confidence), since `categorize`/
    `human_review` operate per `month_ref`. This is correct, expected behavior (aligned with the BRD — each
    month is processed with its own `thread_id`), but it's easy to forget when manually validating a statement
    that crosses a month boundary; a future, more complete CLI feature might be worth having automatically
    detect and process every `month_ref` present in a batch of files, instead of requiring one month per call
  - Confirmed with plain Python (not just the SQL query) that 0 transactions have `confidence != 'high'` — the
    `list_pending_review` query (`WHERE confidence != 'high'`) depends on the invariant "every `confidence` is
    filled in before `human_review` runs" (guaranteed by the graph's sequencing); `confidence IS NULL` should
    never appear in normal use, and indeed it didn't
- Commit after each task or logical group of tasks
