---

description: "Task list template for feature implementation"
---

# Tasks: Merchant Memory Update

**Input**: Design documents from `/specs/004-update-memory/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/memory-node.md, quickstart.md

**Tests**: Included — this feature has no LLM and no human interaction, so tests are plain, fast, and required by
the same testing discipline used across the project.

**Organization**: Tasks are grouped by user story (US1/US2, per spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks both user stories below. No Setup phase needed — no new dependencies or directories.

- [X] T001 Implement `upsert_merchant_category(conn, merchant_key, category, subcategory)` in
      `backend/src/financial_planner/db/repository.py`, using `INSERT ... ON CONFLICT(merchant_key) DO UPDATE`
      (see research.md — idempotency via `ON CONFLICT`)

**Checkpoint**: foundation ready — both user stories can start.

---

## Phase 2: User Story 1 - Remember confirmed categorizations for next month (Priority: P1) 🎯 MVP

**Goal**: every `confidence = high`, non-transfer transaction in a processed month gets its merchant →
category/subcategory mapping persisted, overwriting any prior mapping for that merchant.

**Independent Test**: seed a confirmed transaction, run the update, verify the mapping in `merchant_memory`
(Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T002 [P] [US1] Test: a confirmed transaction's merchant/category is persisted to `merchant_memory`, in
      `backend/tests/test_memory.py::test_memory_remembers_confirmed_categorization` (reuses
      `tests/fixtures/review/builders.py::seed_categorized_transaction`, no new fixture module needed)
- [X] T003 [P] [US1] Test: reconfirming the same merchant with a different category overwrites the stored mapping,
      in `backend/tests/test_memory.py::test_memory_overwrites_stale_mapping_with_newest`
- [X] T004 [P] [US1] Test: running the update on a month with no transactions does nothing and raises no error, in
      `backend/tests/test_memory.py::test_memory_empty_month_is_noop`

### Implementation for User Story 1

- [X] T005 [US1] Implement `nodes/memory.py`: read the month's transactions, filter to `confidence = 'high'` and
      `category != TRANSFER_CATEGORY`, upsert each via `db/repository.py` (depends on T001)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 3: User Story 2 - Never remember a transfer as a merchant category (Priority: P1)

**Goal**: a transaction confirmed as "Internal Transfer" never creates or updates a `merchant_memory` entry.

**Independent Test**: seed a transaction with `category = "Internal Transfer"`, run the update, verify no entry
was written (Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T006 [P] [US2] Test: a transaction confirmed as "Internal Transfer" never writes to `merchant_memory`, in
      `backend/tests/test_memory.py::test_memory_never_writes_transfer_category`

### Implementation for User Story 2

*No new code — already covered by the filter implemented in T005 (`category != TRANSFER_CATEGORY`). This story's
test (T006) verifies existing behavior; adjust `nodes/memory.py` only if T006 reveals a gap.*

**Checkpoint**: both user stories work together — every confirmed transaction is either remembered or correctly
excluded.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T007 [P] Extend `graph.py`: route the `human_review` conditional edge's "nothing pending" branch to
      `update_memory` instead of `END`; add `update_memory` → `END` (see research.md — where this node sits in
      the graph)
- [X] T008 [P] Add a lightweight full-chain smoke test driving the real graph (`detect_and_parse` → `categorize`
      → `human_review` → `update_memory`) end to end, confirming a merchant confirmed this month auto-categorizes
      with `confidence = high` in a later month — in `backend/tests/test_memory.py` or a new
      `test_graph_full_chain.py`, whichever reads more clearly
- [X] T009 Review `nodes/memory.py` against Principle II of the constitution (database access only via
      `db/repository.py`)
- [X] T010 [P] Run the `quickstart.md` scenarios manually against real transactions already imported/categorized/
      reviewed (via features 001-003, data outside the repository) to validate end to end
- [X] T011 [P] Document in `backend/README.md` that `merchant_memory` is now written by the pipeline, not just
      read

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: no dependencies — can start immediately
- **User Stories (Phase 2-3)**: both depend on Foundational
  - US2 depends on the filter already built in US1's implementation (T005) — its own phase adds no new code, only
    a verifying test
- **Polish (Phase 4)**: depends on both user stories being complete

### Parallel Opportunities

- T002, T003, T004 (US1 tests) in parallel with each other
- T007, T008, T010, T011 (Polish) in parallel with each other

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Foundational)
2. Complete Phase 2 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point, confirmed categorizations are already remembered — MVP of the feature

### Incremental Delivery

1. Foundational → base ready
2. US1 → categorizations remembered (MVP)
3. US2 → transfers correctly excluded (verification, not new logic)
4. Polish → wired into the real graph + end-to-end validation with real data

---

## Notes

- All test tasks reuse `tests/fixtures/review/builders.py::seed_categorized_transaction` — no new fixture module
  needed for a feature this small (Principle I)
- No LLM, no human interaction — every test in this feature is a plain, deterministic function/graph call
- Pruning or manually correcting a stale `merchant_memory` entry stays out of scope, per spec.md Assumptions
- Commit after each task or logical group of tasks

- **T010 completed** with the full graph (real Ollama), processing both real months (`2026-07`, `2026-08`) from
  Bradesco + Inter back to back on a fresh database:
  - July: 26 items reviewed. August: only 47 items reviewed (not 63, like in feature 003's isolated validation of
    that same month) — the difference is `update_memory` working as designed: July's confirmations already
    populated `merchant_memory` by the time August ran, so many August transactions resolved automatically via
    memory, with zero LLM calls and zero review prompts for those.
  - 41 unique merchants ended up in memory, 0 of them with "Internal Transfer" (SC-002 held), and all 89
    transactions ended at `confidence = high` (SC-004 equivalent — nothing altered by this feature beyond memory
    writes).
  - **Finding, not a bug**: a generic description like "PIX QR CODE DINAMICO" gets memorized as its own merchant
    key with whatever category it was confirmed as (in this run, "Outros") — the next unrelated PIX QR-code
    payment sharing that exact generic text will now skip the LLM and auto-resolve to that same category, even if
    it's actually a different kind of purchase. This is a direct, expected consequence of the "no fuzzy merchant
    matching" assumption already documented in spec.md — worth keeping in mind if categorization accuracy for
    QR-code-style payments becomes noticeably worse over time; a future refinement could require a minimum
    description specificity before memorizing, but that's out of scope here.
