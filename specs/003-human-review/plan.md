# Implementation Plan: Human Review of Transactions

**Branch**: `003-human-review` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-human-review/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `human_review` node and, for the first time, actually assemble a LangGraph `StateGraph` (wiring
`detect_and_parse` → `categorize` → `human_review`, with a SQLite checkpointer). The node queries the month's
transactions still with `confidence != high`, and for each one calls `interrupt()` asking for confirmation or
correction; the decision is persisted immediately and confidence becomes `high`. A minimal CLI
(`interface/cli.py`) drives the interrupt/resume loop — generic enough to know nothing about business rules, just
displaying what the node sends and returning the user's response.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `langgraph` (already present — `StateGraph`, `interrupt`, `Command`),
`langgraph-checkpoint-sqlite` (new — `SqliteSaver`, a checkpointer that allows resuming exactly where it left off)

**Storage**: SQLite — the checkpointer uses the same database file already used by
`transactions`/`merchant_memory` (BRD section 3: "all in the same database"), in its own tables automatically
created by `SqliteSaver`

**Testing**: pytest. The node's tests call the review function directly, injecting responses via a test driver
that simulates the `interrupt()`/`Command(resume=...)` loop, with no real terminal — consistent with the pattern
already used for the mocked LLM.

**Target Platform**: local CLI (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A

**Constraints**: Reviewing an item MUST survive a process interruption (closing the terminal) — this depends
entirely on the checkpointer persisting the graph state to disk before each pause, not in memory

**Scale/Scope**: dozens of pending items per month, in the worst case (no merchant known yet)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | Uses LangGraph's own recommended pattern for multiple interruptions looped within a node — no custom state machine; the CLI only displays/collects text, no TUI framework | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/review.py` only accesses the database via `db/repository.py`; the CLI (`interface/cli.py`) is the interface layer, not a node — already planned as a separate component in the BRD's architecture (section 7) | PASS |
| III. Swappable LLM via Abstraction | N/A — this node doesn't use an LLM | N/A |
| IV. Portable Persistence | The feature's own tables (`transactions`) use standard SQL; the checkpointer uses `langgraph-checkpoint-sqlite` today, with a planned swap to `langgraph-checkpoint-postgres` in Phase 2 (BRD section 3) — same interface, migration already planned | PASS |
| V. Mandatory Human Review | This feature is the direct implementation of the principle | PASS |
| VI. Categorical Confidence | Every human decision results in `confidence = high` — never a numeric value | PASS |
| VII. Deterministic Deduplication | N/A — doesn't recompute dedup | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/003-human-review/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/financial_planner/
│   ├── graph.py                      # NEW — builds and compiles the StateGraph (SqliteSaver checkpointer)
│   ├── graph_state.py                # NEW — GraphState (minimal TypedDict: source_files, month_ref, db_path)
│   ├── nodes/
│   │   ├── ingest.py                 # existing — adapted to LangGraph's node signature
│   │   ├── categorize.py             # existing — same
│   │   └── review.py                 # NEW — human_review node
│   ├── db/
│   │   └── repository.py             # + list_pending_review(month_ref)
│   └── interface/
│       └── cli.py                    # NEW — minimal driver for the interrupt()/resume loop
└── tests/
    ├── fixtures/
    │   └── review/                   # synthetic transactions with varying confidence
    └── test_review.py

frontend/                             # not used at this stage
```

**Structure Decision**: Introduces `graph.py`/`graph_state.py` at the package root (graph assembly is
cross-cutting, doesn't belong to any specific node) and `interface/cli.py` as the first piece of the interface
layer planned in the BRD's structure (section 7). `nodes/review.py` follows the same pattern as the previous
nodes — only orchestrates, accesses the database via `db/repository.py`.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
