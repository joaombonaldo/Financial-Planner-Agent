# Implementation Plan: Budget Check

**Branch**: `005-budget-check` | **Date**: 2026-08-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-budget-check/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `budget_check` node: for a fully processed month, compute actual expense per category (excluding
internal transfers and income), compare it against configured monthly goals read through a swappable `get_budget()`
function, and produce a per-category comparison (within/over budget, exact difference). Extends the graph as its
next step after `update_memory`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — `pyyaml` (already a dependency, used the same way as `categories.yaml`)

**Storage**: read-only over the existing `transactions` table via `db/repository.py`; goals come from a local YAML
file (`config/budget.local.yaml`, gitignored — mirrors `budget.example.yaml` with fictitious values, per BRD
section 8), not from the database

**Testing**: pytest. No LLM, no human interaction — tests seed transactions directly and provide a temporary
budget config file, asserting on the computed comparison

**Target Platform**: CLI local (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A — same small monthly volume as prior features; plain Python aggregation over the
month's transaction list is enough, no need for a SQL `GROUP BY`

**Constraints**: MUST fail explicitly when no local budget configuration exists (FR-008); MUST NOT modify any
transaction (FR-009)

**Scale/Scope**: dozens of transactions per month, a handful of configured categories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | Plain Python sum over the month's transactions, no SQL aggregate query or ORM needed for this volume | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/budget.py` reads transactions only via `db/repository.py` and goals only via `budget/config.py` — never opens the YAML file or `sqlite3` itself | PASS |
| III. Swappable LLM via Abstraction | N/A — no LLM involved | N/A |
| IV. Portable Persistence | `get_budget()` is a swappable function (FR-007), backed by a local file today; a future Supabase-backed implementation can replace it without touching `nodes/budget.py`, mirroring the BRD's own stated plan (section 5.5) | PASS |
| V. Mandatory Human Review | N/A — no sensitive decision is made here; this feature only compares already-finalized data | N/A |
| VI. Categorical Confidence | N/A — `confidence` is only used as a read filter (FR-010), never set | N/A |
| VII. Deterministic Deduplication | N/A — unrelated to transaction dedup | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/005-budget-check/
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
│   ├── budget/
│   │   └── config.py                 # NEW — get_budget(), swappable goal source (local YAML today)
│   ├── nodes/
│   │   └── budget.py                 # NEW — budget_check node
│   ├── state.py                      # + CategoryComparison, BudgetNotConfiguredError
│   ├── graph_state.py                # + budget_report field
│   └── config/
│       └── budget.example.yaml       # NEW — fictitious example goals, versioned (real one is gitignored)
└── tests/
    └── test_budget.py                # NEW

frontend/                             # not used at this stage
```

**Structure Decision**: New `budget/` module (mirrors `llm/`'s pattern — a small, dedicated abstraction module for
one swappable concern) holding just the goal-reading function. The comparison logic itself is small enough to
live directly in `nodes/budget.py`, consistent with how feature 004 kept its logic directly in the node rather
than introducing a module for a single function's worth of work.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
