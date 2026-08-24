# Implementation Plan: Generate Insights

**Branch**: `006-generate-insights` | **Date**: 2026-08-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-generate-insights/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `generate_insights` node: build an LLM prompt grounded in the current month's real category spend,
the budget comparison already computed by `budget_check`, and (when available) the previous month's category
spend for comparison; call the LLM through the existing swappable abstraction; return the generated Portuguese
summary, or a recorded failure reason if generation didn't succeed — never raising, per the BRD's "optional"
marking for this node. Extends the graph as its next step after `budget_check`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — `llm/client.py` (already built for feature 002)

**Storage**: read-only over the existing `transactions` table, for both the current and previous `month_ref`; no
schema change

**Testing**: pytest. LLM always mocked (constitution) — reuses the `FakeChatModel` double from feature 002
(`tests/fixtures/categorization/llm_double.py`), extended with a failure-simulating variant for FR-006's tests

**Target Platform**: CLI local (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A

**Constraints**: MUST NOT raise on LLM failure (FR-006) — this node's one deliberately broad exception handler,
justified by the BRD explicitly marking it optional

**Scale/Scope**: same order of magnitude as prior features — dozens of transactions across at most two months per
run

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | Reuses the category-spend calculation already built for `budget_check` (extracted into a shared helper) instead of a second implementation | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/insights.py` reads transactions only via `db/repository.py` and the LLM only via `llm/client.py` | PASS |
| III. Swappable LLM via Abstraction | Central to this feature — uses `llm/client.py`, same as `categorize` | PASS |
| IV. Portable Persistence | N/A — no schema change, read-only access already using standard SQL | N/A |
| V. Mandatory Human Review | N/A — this feature makes no sensitive financial decision; it only narrates data already finalized by features 001-005 | N/A |
| VI. Categorical Confidence | N/A — `confidence` is only used as a read filter (inherited from the shared spend calculation), never set | N/A |
| VII. Deterministic Deduplication | N/A — unrelated to transaction dedup | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/006-generate-insights/
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
│   │   ├── config.py                 # existing
│   │   └── spending.py               # NEW — compute_category_spend(), extracted from nodes/budget.py
│   ├── nodes/
│   │   ├── budget.py                 # refactored to use budget/spending.py
│   │   └── insights.py               # NEW — generate_insights node
│   ├── state.py                      # + InsightsResult
│   └── graph_state.py                # + insights_summary, insights_error fields
└── tests/
    ├── fixtures/
    │   └── categorization/
    │       └── llm_double.py          # + a failure-simulating chat model double
    └── test_insights.py               # NEW

frontend/                             # not used at this stage
```

**Structure Decision**: `budget/spending.py` is the one refactor this feature requires — pulling the spend
calculation out of `nodes/budget.py` so both `budget_check` and `generate_insights` share one implementation,
consistent with spec.md's Assumptions. Everything else is additive: one new node, one new state field on
`GraphState`, one new result type.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
