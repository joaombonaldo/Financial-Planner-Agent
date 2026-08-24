---

description: "Task list template for feature implementation"
---

# Tasks: Transaction Categorization

**Input**: Design documents from `/specs/002-categorize-transacoes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llm-categorizer.md,
contracts/transfer-detection.md, quickstart.md

**Tests**: Included — the project's constitution requires the graph to be testable with a mocked LLM, without
depending on Ollama running ("Testing Standards"), so they're not optional in this feature.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md) to allow independent implementation
and testing of each one.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2, US3)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Create directories `backend/src/financial_planner/categorization/` and
      `backend/src/financial_planner/llm/`, each with `__init__.py`
- [X] T002 [P] Create `backend/tests/fixtures/categorization/`
- [X] T003 [P] Create `backend/src/financial_planner/config/categories.yaml` with the initial taxonomy from the
      BRD's Appendix A (categories + subcategories, including "Outros" and "Transferência interna")

**Checkpoint**: folder structure and base taxonomy ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: pieces shared by all three user stories — extended schema, merchant-memory access, validated
taxonomy, and the LLM abstraction. No user story can be implemented before this phase.

**⚠️ CRITICAL**: blocks all user stories below.

- [X] T004 Add the `merchant_memory` table (`merchant_key` PK, `category`, `subcategory`) to
      `backend/src/financial_planner/db/schema.sql`, using standard SQL (Principle IV)
- [X] T005 Implement in `backend/src/financial_planner/db/repository.py`: `get_merchant_category(merchant_key)`,
      `update_transaction_category(dedup_hash, category, subcategory, confidence)`, and
      `list_transactions_by_month(month_ref)` (depends on T004)
- [X] T006 [P] Implement loading and validating the taxonomy (`config/categories.yaml` → list of valid
      categories/subcategories, including the "Outros" fallback) in
      `backend/src/financial_planner/categorization/taxonomy.py` (depends on T003)
- [X] T007 [P] Implement `backend/src/financial_planner/llm/client.py`: the single point of chat model creation
      via `init_chat_model`, configured by `OLLAMA_MODEL`/`OLLAMA_BASE_URL` (Principle III)
- [X] T008 Implement merchant key normalization (trim + lowercase of `description_raw`) and memory lookup in
      `backend/src/financial_planner/categorization/merchant_memory.py` (depends on T005)

**Checkpoint**: foundation ready — all three user stories can start.

---

## Phase 3: User Story 1 - Automatically categorize already-known merchants (Priority: P1) 🎯 MVP

**Goal**: transactions from merchants already confirmed in memory get category/subcategory with
`confidence = high`, without calling the LLM.

**Independent Test**: populate `merchant_memory` with a mapping and verify a matching transaction is categorized
correctly with no LLM call at all (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T009 [P] [US1] Create fixtures for transactions + `merchant_memory` state (known merchant) in
      `backend/tests/fixtures/categorization/`
- [X] T010 [P] [US1] Unit test: an already-confirmed merchant returns the mapped category with
      `confidence = high`, in
      `backend/tests/test_categorize.py::test_categorize_known_merchant` (depends on T009)
- [X] T011 [P] [US1] Unit test: empty memory (first run) produces `confidence = high` for no transaction, in
      `backend/tests/test_categorize.py::test_empty_merchant_memory_never_high`

### Implementation for User Story 1

- [X] T012 [US1] Implement the `categorize` node in `backend/src/financial_planner/nodes/categorize.py`,
      orchestrating: for each transaction, check `merchant_memory.py` first and update the transaction via
      `db/repository.py` when there's a match (depends on T008, T005)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 4: User Story 2 - Categorize new or ambiguous transactions via LLM (Priority: P1)

**Goal**: merchants with no memory match get categorized via the LLM, with a fallback to "Outros"/`low` when the
response doesn't belong to the taxonomy.

**Independent Test**: run categorization with the mocked LLM returning a valid category and then an invalid one,
checking `confidence` and the fallback (Scenario 2 of `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Create a deterministic LLM double (replaces `llm/client.py` in tests) in
      `backend/tests/fixtures/categorization/`
- [X] T014 [P] [US2] Unit test: a new merchant gets a taxonomy category with `confidence` `medium`/`low`, never
      `high`, in `backend/tests/test_categorize.py::test_categorize_new_merchant_via_llm` (depends on T013)
- [X] T015 [P] [US2] Unit test: an LLM response outside the taxonomy falls into `category = "Outros"`,
      `confidence = low`, in
      `backend/tests/test_categorize.py::test_llm_response_outside_taxonomy_falls_back` (depends on T013)

### Implementation for User Story 2

- [X] T016 [US2] Implement `backend/src/financial_planner/categorization/llm_categorizer.py`: calls
      `llm/client.py`, validates the response against `taxonomy.py`, applies the "Outros"/`low` fallback when
      needed (depends on T006, T007)
- [X] T017 [US2] Extend the `categorize` node to call `llm_categorizer.py` when there's no memory match, in
      `backend/src/financial_planner/nodes/categorize.py` (depends on T012, T016)

**Checkpoint**: User Story 1 and 2 work together — every transaction with no memory match is categorized via the
LLM.

---

## Phase 5: User Story 3 - Flag candidates for transfers between the user's own accounts (Priority: P2)

**Goal**: transactions with a transfer pattern (PIX/TED/DOC) and a mirrored amount in another account within ±2
days are suggested as "Transferência interna", without being excluded from the total.

**Independent Test**: provide two mirrored transactions in different accounts and verify both get flagged,
staying in the transaction list (Scenario 3 of `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T018 [P] [US3] Create fixtures for a mirrored transaction pair (inside and outside the 2-day window) in
      `backend/tests/fixtures/categorization/`
- [X] T019 [P] [US3] Unit test: a mirrored pair inside the window gets flagged as "Transferência interna" with
      `confidence = medium`, in
      `backend/tests/test_categorize.py::test_transfer_pair_detected` (depends on T018)
- [X] T020 [P] [US3] Unit test: a transfer pattern with no mirrored pair follows the normal flow (memory/LLM), in
      `backend/tests/test_categorize.py::test_transfer_pattern_without_mirror_falls_through` (depends on T018)

### Implementation for User Story 3

- [X] T021 [US3] Implement `backend/src/financial_planner/categorization/transfer_detection.py`: PIX/TED/DOC
      pattern + mirrored amount in a different account within ±2 days (depends on T005)
- [X] T022 [US3] Reorder the `categorize` node to check `transfer_detection.py` **before**
      `merchant_memory.py`/`llm_categorizer.py` (see research.md — evaluation order), in
      `backend/src/financial_planner/nodes/categorize.py` (depends on T017, T021)

**Checkpoint**: all three user stories work independently and together, in the correct order
(transfer → memory → LLM).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 [P] Run the `quickstart.md` scenarios manually against real transactions already imported (via feature
      001, data outside the repository) to validate end-to-end before considering the feature done
- [X] T024 Review `nodes/categorize.py` against Principle II of the constitution (the node must not import
      `init_chat_model`/`sqlite3` directly — only via `llm/client.py` and `db/repository.py`)
- [X] T025 [P] Document in `backend/README.md` the required environment variables (`OLLAMA_MODEL`,
      `OLLAMA_BASE_URL`) and how to run this feature's tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories
- **User Stories (Phase 3-5)**: all depend on Foundational
  - US1, US2, and US3 extend the same `categorize` node (T012 → T017 → T022), so in practice they're sequential
    (US1 → US2 → US3) despite being independently testable — the domain modules (`merchant_memory.py`,
    `llm_categorizer.py`, `transfer_detection.py`) are independent of each other and can be implemented in
    parallel before the final integration into the node
- **Polish (Phase 6)**: depends on all desired user stories being complete

### Within Each User Story

- Tests are written before implementation and must fail first
- Fixtures before the tests that use them
- Domain modules (`categorization/*.py`) before integration into the node
- The node's final evaluation order (transfer → memory → LLM) is only correct after T022 (US3) — during US1/US2
  the node doesn't know about `transfer_detection.py` yet

### Parallel Opportunities

- T001, T002, T003 (Setup) in parallel
- T006, T007 (Foundational) in parallel with each other
- T009 (fixtures) before T010/T011 (tests) in parallel with each other
- T013 (LLM double) before T014/T015 in parallel with each other
- T018 (fixtures) before T019/T020 in parallel with each other

---

## Parallel Example: Foundational

```bash
# Independent modules in parallel:
Task: "Implement taxonomy.py in backend/src/financial_planner/categorization/taxonomy.py"
Task: "Implement llm/client.py in backend/src/financial_planner/llm/client.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phase 3 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point, already-known merchants are categorized automatically — the feature's MVP

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 → automatic categorization of known merchants (MVP)
3. US2 → LLM categorization for new merchants, with a safe fallback
4. US3 → transfer flagging, with no automatic exclusion from the total
5. Polish → end-to-end validation with real data (outside the repo) + constitution-compliance review

---

## Notes

- All test tasks use synthetic fixtures with the LLM always mocked — no real financial data nor dependency on
  Ollama running enters the automated suite
- `merchant_memory` is only read by this feature; writing new confirmations is a future feature's responsibility
  (`update_memory`)
- Confirming/rejecting transfer candidates and persisting low/medium confidence corrections are left to the
  future human review feature (`human_review`) — this feature only suggests, never decides
- Commit after each task or logical group of tasks

- **T023 completed** with real Ollama (Qwen2.5) against the 89 real transactions imported by feature 001
  (Bradesco + Inter, Aug/2026; statements removed from `extracts/` after validation):
  - `confidence = high`: 0 (correct — merchant memory empty on the first run, SC-005 confirmed)
  - `confidence = low` from an invalid-taxonomy fallback: 0 — every LLM response already came back in a valid
    category in the expected format
  - 100% of transactions ended up with a valid category (SC-002); none was excluded from the total (89 before
    and after categorization, SC-003)
  - Real LLM quality is imperfect (expected): some categorizations were wrong (e.g. the "Raia" pharmacy
    categorized as Transporte; the "RENTAB.INVEST" investment yield categorized as Cartão de Crédito instead of
    Outros) — but always with `confidence = medium`, never `high`, so they end up correctly flagged for human
    review (a future feature), validating the constitution's design (Principle V)
  - Note for a future iteration (doesn't block this feature): the transfer pattern (`PIX`/`TED`/`DOC`) is broad
    enough to flag as "Transferência interna" a PIX QR Code purchase whose amount coincidentally matches another
    transaction in another account within the 2-day window — behavior already anticipated as an accepted edge
    case in the spec (the final decision is human review's), but worth narrowing the textual pattern if the
    false-positive rate proves high in real use
