# Implementation Plan: Merchant Memory Update

**Branch**: `004-update-memory` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-update-memory/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `update_memory` node: after a month's transactions are all `confidence = high`, persist a
merchant → category/subcategory mapping into `merchant_memory` for every transaction whose category isn't
"Internal Transfer". Idempotent upsert — the newest confirmation always wins, re-running is a no-op. Extends the
existing graph (`detect_and_parse` → `categorize` → `human_review` → `update_memory`) as its final node so far.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — `sqlite3` (stdlib, via `db/repository.py`), same as prior features

**Storage**: SQLite — writes to the `merchant_memory` table already created by feature 002 (previously read-only
for this project); uses a standard `INSERT ... ON CONFLICT(merchant_key) DO UPDATE` upsert, supported the same way
by SQLite and Postgres

**Testing**: pytest. No LLM involved, so no mocking concerns — tests seed transactions directly and assert on
`merchant_memory` contents

**Target Platform**: CLI local (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A

**Constraints**: MUST be idempotent (FR-005); MUST NOT ever write `category = "Internal Transfer"` to memory
(FR-003); MUST NOT mutate any transaction (FR-004)

**Scale/Scope**: same order of magnitude as prior features — dozens of transactions per month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | One upsert function, no new abstraction; idempotency comes from `ON CONFLICT`, not custom dedup logic | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/memory.py` only accesses the database via `db/repository.py` | PASS |
| III. Swappable LLM via Abstraction | N/A — no LLM involved | N/A |
| IV. Portable Persistence | `INSERT ... ON CONFLICT ... DO UPDATE` is standard SQL, supported identically by SQLite and Postgres | PASS |
| V. Mandatory Human Review | N/A — this feature makes no sensitive decision, it only persists decisions already made by feature 003 | N/A |
| VI. Categorical Confidence | N/A — doesn't set or read confidence as a decision, only filters on it | N/A |
| VII. Deterministic Deduplication | N/A — unrelated to transaction dedup | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/004-update-memory/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/financial_planner/
│   ├── nodes/
│   │   └── memory.py                 # NEW — update_memory node
│   ├── db/
│   │   └── repository.py             # + upsert_merchant_category(merchant_key, category, subcategory)
│   └── graph.py                      # extended: adds the update_memory node + edges
└── tests/
    └── test_memory.py                # NEW

frontend/                             # not used at this stage
```

**Structure Decision**: A single new node file (`nodes/memory.py`) plus one new repository function — no new
top-level module needed, unlike feature 002/003 which introduced `categorization/`, `llm/`, `interface/`. This
feature's logic is small enough to live directly in the node, consistent with Principle I.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
