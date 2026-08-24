---

description: "Task list template for feature implementation"
---

# Tasks: Bank Statement Ingestion

**Input**: Design documents from `/specs/001-ingest-extratos/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/parser-adapter.md, quickstart.md

**Tests**: Included — the project's constitution requires deterministic unit tests per bank with small fixtures
("Testing Standards"), so they're not optional in this feature.

**Organization**: Tasks are grouped by user story (US1/US2/US3, per spec.md) to allow independent implementation
and testing of each one.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: which user story the task belongs to (US1, US2, US3)

## Path Conventions

Single project in `backend/`, per `plan.md`. All paths below are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: prepare the `backend/` project to receive this feature's code (nothing exists yet beyond the
skeleton created by `uv init`).

- [X] T001 Add `pytest` as a development dependency (`uv add --dev pytest` in `backend/`)
- [X] T002 [P] Create directories `backend/src/financial_planner/nodes/`, `backend/src/financial_planner/parsers/`,
      and `backend/src/financial_planner/db/`, each with `__init__.py`
- [X] T003 [P] Create `backend/tests/__init__.py`, `backend/tests/fixtures/bradesco/`, and
      `backend/tests/fixtures/inter/`

**Checkpoint**: folder structure ready to receive domain code and tests.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: pieces shared by all three user stories — transaction schema, database access, and the parser
contract. No user story can be implemented before this phase.

**⚠️ CRITICAL**: blocks all user stories below.

- [X] T004 Define the typed schema for the normalized Transaction and for `ImportResult` (this feature's fields,
      see `data-model.md`) in `backend/src/financial_planner/state.py`
- [X] T005 Create `backend/src/financial_planner/db/schema.sql` with the `transactions` table (subset used by this
      feature: `dedup_hash`, `date`, `description_raw`, `account`, `type`, `amount`, `month_ref`, plus nullable
      `category`/`subcategory`/`confidence`/`installment_id` columns reserved for future features), using
      standard SQL (Principle IV — portable persistence)
- [X] T006 Implement `backend/src/financial_planner/db/repository.py` with `transaction_exists(dedup_hash)` and
      `insert_transaction(transaction)`, the only points of SQLite access (depends on T005)
- [X] T007 [P] Define the shared adapter contract (detection and parsing signatures, see
      `contracts/parser-adapter.md`) in `backend/src/financial_planner/parsers/base.py`
- [X] T008 Implement amount normalization (Brazilian format → decimal) and date normalization (`DD/MM/YYYY` → ISO)
      in `backend/src/financial_planner/parsers/normalize.py` (depends on T004)
- [X] T009 Implement the deduplication hash computation (SHA-256 over normalized
      `date+description_raw+amount+account`, see `research.md`) in
      `backend/src/financial_planner/parsers/dedup.py` (depends on T008)

**Checkpoint**: foundation ready — all three user stories can start.

---

## Phase 3: User Story 1 - Import a statement from a supported bank (Priority: P1) 🎯 MVP

**Goal**: given a CSV from Bradesco or Inter, automatically detect the bank and get the month's transactions in a
single normalized format.

**Independent Test**: run ingestion against a fixture from each bank and verify the output is a list of
transactions in the normalized schema (Scenario 1 of `quickstart.md`).

### Tests for User Story 1 ⚠️

> Write these tests first; they must fail before implementation.

- [X] T010 [P] [US1] Create Bradesco CSV fixtures (happy path + BOM + duplicated "Últimos Lancamentos" header +
      "Total" footer) in `backend/tests/fixtures/bradesco/`
- [X] T011 [P] [US1] Create Inter CSV fixtures (happy path + blank `Descrição` + metadata lines) in
      `backend/tests/fixtures/inter/`
- [X] T012 [P] [US1] Unit test for Bradesco parsing in
      `backend/tests/test_parsers.py::test_parse_bradesco` (depends on T010)
- [X] T013 [P] [US1] Unit test for Inter parsing, including the `Descrição` → `Histórico` fallback, in
      `backend/tests/test_parsers.py::test_parse_inter` (depends on T011)
- [X] T014 [P] [US1] Unit test for automatic bank detection (Bradesco, Inter) in
      `backend/tests/test_parsers.py::test_detect_bank` (depends on T010, T011)

### Implementation for User Story 1

- [X] T015 [US1] Implement the transaction-line filter via date regex (`^\d{2}/\d{2}/\d{4};`), reusable by both
      adapters, in `backend/src/financial_planner/parsers/base.py` (depends on T007)
- [X] T016 [P] [US1] Implement the Bradesco adapter (two Credit/Debit columns, `Docto.`) in
      `backend/src/financial_planner/parsers/bradesco.py` (depends on T015, T008, T009)
- [X] T017 [P] [US1] Implement the Inter adapter (signed `Valor` column, description fallback) in
      `backend/src/financial_planner/parsers/inter.py` (depends on T015, T008, T009)
- [X] T018 [US1] Implement automatic bank detection by column structure in
      `backend/src/financial_planner/parsers/detect.py` (depends on T016, T017)
- [X] T019 [US1] Implement the `detect_and_parse` node, orchestrating detection + adapter + persistence via
      `db/repository.py`, in `backend/src/financial_planner/nodes/ingest.py` (depends on T006, T018)

**Checkpoint**: User Story 1 complete and independently testable.

---

## Phase 4: User Story 2 - Reimport a statement without duplicating transactions (Priority: P2)

**Goal**: reimporting the same file (or one with an overlapping period) must not create duplicate transactions.

**Independent Test**: import the same fixture twice and verify the second run inserts nothing new (Scenario 2 of
`quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T020 [P] [US2] Unit test: reimporting the same Bradesco fixture results in zero new transactions, in
      `backend/tests/test_parsers.py::test_reimport_skips_duplicates` (depends on T010)
- [X] T021 [P] [US2] Unit test: two equivalent transactions coming from different sections of the same Bradesco
      file (main statement + "Últimos Lancamentos") produce only one transaction, in
      `backend/tests/test_parsers.py::test_dedup_within_same_file`

### Implementation for User Story 2

- [X] T022 [US2] Extend the `detect_and_parse` node to check `transaction_exists(dedup_hash)` before inserting and
      to track `transactions_imported` / `transactions_skipped_duplicate` in `ImportResult`, in
      `backend/src/financial_planner/nodes/ingest.py` (depends on T019, T006, T004)

**Checkpoint**: User Story 1 and 2 work together — reimport is safe.

---

## Phase 5: User Story 3 - Be warned when a file couldn't be processed correctly (Priority: P3)

**Goal**: an unrecognized bank or a balance that doesn't reconcile produces an explicit warning/error, never a
silent failure.

**Independent Test**: run ingestion against an unsupported-bank file and against a fixture with a deliberately
wrong balance (Scenario 3 of `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Unit test: a file with an unrecognized layout returns an explicit error and no transaction,
      in `backend/tests/test_parsers.py::test_detect_unknown_bank`
- [X] T024 [P] [US3] Unit test: a fixture with a deliberately altered balance produces
      `balance_reconciliation = mismatch` and a message in `warnings`, while still importing the correctly
      recognized transactions, in `backend/tests/test_parsers.py::test_balance_reconciliation_mismatch`

### Implementation for User Story 3

- [X] T025 [US3] Implement an explicit error return for an unrecognized bank in
      `backend/src/financial_planner/parsers/detect.py` (depends on T018)
- [X] T026 [US3] Implement the balance check (previous balance ± transaction amount == declared balance, with a
      rounding tolerance) in `backend/src/financial_planner/parsers/reconcile.py` (depends on T015)
- [X] T027 [US3] Wire the unrecognized-bank error and reconciliation warnings into the `ImportResult` returned by
      the `detect_and_parse` node, in `backend/src/financial_planner/nodes/ingest.py` (depends on T022, T025, T026)

**Checkpoint**: all three user stories work independently and together.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Run the `quickstart.md` scenarios manually against a real statement (outside the repository, via
      `extracts/`) to validate end-to-end before considering the feature done
- [X] T029 Review `nodes/ingest.py` against Principle II of the constitution (the node must not import `pandas`
      or `sqlite3` directly — only via `parsers/` and `db/repository.py`)
- [X] T030 [P] Document in `backend/README.md` how to run this feature's tests (`uv run pytest`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories
- **User Stories (Phase 3-5)**: all depend on Foundational
  - US1 is the functional base; US2 and US3 extend the node created in US1 (T019), so in practice they're
    sequential (US1 → US2 → US3) despite being independently testable
- **Polish (Phase 6)**: depends on all desired user stories being complete

### Within Each User Story

- Tests are written before implementation and must fail first
- Fixtures before the tests that use them
- `parsers/base.py` (transaction line) before the specific adapters
- Adapters before automatic detection
- Detection + adapters before the orchestration node

### Parallel Opportunities

- T002, T003 (Setup) in parallel
- T007 (Foundational) in parallel with T004/T005 (different files)
- T010, T011 (fixtures) in parallel; T012, T013, T014 (tests) in parallel with each other after the fixtures
- T016, T017 (Bradesco/Inter adapters) in parallel with each other
- T020, T021 (US2 tests) in parallel
- T023, T024 (US3 tests) in parallel

---

## Parallel Example: User Story 1

```bash
# Fixtures in parallel:
Task: "Create Bradesco CSV fixtures in backend/tests/fixtures/bradesco/"
Task: "Create Inter CSV fixtures in backend/tests/fixtures/inter/"

# Adapters in parallel (once T015 is ready):
Task: "Implement the Bradesco adapter in backend/src/financial_planner/parsers/bradesco.py"
Task: "Implement the Inter adapter in backend/src/financial_planner/parsers/inter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phase 3 (US1)
3. Manually validate Scenario 1 of `quickstart.md`
4. At this point it's already possible to import a statement from either bank — the feature's MVP

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 → functional import (MVP)
3. US2 → safe reimport, no duplicates
4. US3 → visibility into errors/inconsistencies
5. Polish → end-to-end validation with real data (outside the repo) + constitution-compliance review

---

## Notes

- All test tasks use only small synthetic fixtures — no real financial data enters the repository (constitution,
  "Sensitive Data Protection")
- Category, subcategory, confidence, and installments stay `NULL`/untouched by this feature — they're later
  specs' responsibility
- Commit after each task or logical group of tasks
- **T028 completed** with the user's 2 real statements (Bradesco + Inter, Aug/2026) in `extracts/` (gitignored,
  confirmed via `git check-ignore`). All 3 `quickstart.md` scenarios reconciled correctly. Validating against real
  data found 2 bugs not anticipated by the original spec/fixtures, fixed and covered by new regression tests
  (11/11 passing):
  1. A Bradesco administrative line with both Credit and Debit blank (e.g. "COD. LANC. 0") crashed the parser —
     fixed to treat it as a zero-amount transaction.
  2. The balance-reconciliation check always normalized the balance to an absolute value, losing the sign on
     accounts with a negative balance (overdraft), and assumed ascending chronological order in the file — but
     the Inter export comes in descending order (most recent first). Both fixed in `parsers/reconcile.py`.
