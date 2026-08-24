# Implementation Plan: Generate Report

**Branch**: `007-generate-report` | **Date**: 2026-08-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-generate-report/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `generate_report` node: read the month's finalized transactions, compute total income, total
expense, net balance, the internal-transfer total (kept separate), and a category-by-category breakdown covering
every category with any activity — then assemble all of that alongside the budget comparison and insights result
already computed by earlier nodes into a single `MonthlyReport`. This is the graph's last node; no LLM, no
mutation, purely aggregation.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new

**Storage**: read-only over the existing `transactions` table via `db/repository.py`; no schema change

**Testing**: pytest. No LLM, no human interaction — tests seed transactions directly and assert on the assembled
`MonthlyReport`'s fields

**Target Platform**: CLI local (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A — same small monthly volume as every prior feature

**Constraints**: MUST NOT modify any transaction, budget goal, or merchant memory entry (FR-008); MUST NOT use an
LLM (FR-009)

**Scale/Scope**: dozens of transactions per month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | Aggregation logic lives directly in `nodes/report.py`, no new module — the same choice already made for `update_memory` (feature 004) when a single function's worth of logic didn't warrant one | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/report.py` only reads transactions via `db/repository.py` | PASS |
| III. Swappable LLM via Abstraction | N/A — no LLM involved | N/A |
| IV. Portable Persistence | N/A — no schema change, read-only access already using standard SQL | N/A |
| V. Mandatory Human Review | N/A — no sensitive decision is made here; this feature only aggregates data already finalized by features 001-006 | N/A |
| VI. Categorical Confidence | N/A — `confidence` is only used as a read filter, never set | N/A |
| VII. Deterministic Deduplication | N/A — unrelated to transaction dedup | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/007-generate-report/
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
│   │   └── report.py                 # NEW — generate_report node
│   ├── state.py                      # + CategoryBreakdownEntry, MonthlyReport
│   ├── graph_state.py                # + report field
│   └── graph.py                      # extended: generate_insights -> generate_report -> END
└── tests/
    └── test_report.py                # NEW

frontend/                             # not used at this stage
```

**Structure Decision**: No new top-level module — `nodes/report.py` holds both the node function and the small
category-breakdown helper it needs, consistent with how feature 004 kept `update_memory`'s logic directly in its
node rather than introducing a module for a single function's worth of work.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
