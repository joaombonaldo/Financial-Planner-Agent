# Implementation Plan: Bank Statement Ingestion

**Branch**: `001-ingest-extratos` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ingest-extratos/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `detect_and_parse` node: given a CSV file manually exported from Bradesco or Inter, automatically
detect the source bank, extract only the real transaction lines (ignoring metadata, repeated headers, and
footers), normalize amount/date into a canonical format, compute a deduplication hash, and persist transactions
ready for the categorization step — without duplicating on reimport and without failing silently when the file
doesn't reconcile or isn't recognized.

## Technical Context

**Language/Version**: Python 3.12 (`backend/.python-version`)

**Primary Dependencies**: pandas + openpyxl (CSV reading/parsing), `sqlite3` (stdlib, via `db/repository.py`)

**Storage**: SQLite (`backend/src/financial_planner/db/schema.sql`) — this feature only needs the `transactions`
table (columns from the normalized schema described in BRD 6.1) to check existing `dedup_hash` values

**Testing**: pytest, with small, deterministic CSV fixtures per bank (2-3 lines + edge cases), per the
constitution's "Testing Standards"

**Target Platform**: local CLI (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`) — no frontend component at this stage

**Performance Goals**: N/A — monthly volume on the order of dozens of transactions per bank; no throughput
requirement

**Constraints**: Must not depend on the LLM nor on the network (`detect_and_parse` doesn't use an LLM, by BRD
section 4's design); must be resilient to the file quirks already documented in the spec (BOM, duplicated
sections, blank description column)

**Scale/Scope**: 2 supported banks (Bradesco, Inter), ~1 month of statement per run (dozens of lines)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | One parser per bank (adapter pattern), no abstraction beyond what's needed for 2 known banks | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/ingest.py` orchestrates; file reading lives in `parsers/`, database access (dedup check) lives in `db/repository.py` — the node never touches pandas or sqlite3 directly | PASS |
| III. Swappable LLM via Abstraction | N/A — this node doesn't use an LLM | N/A |
| IV. Portable Persistence | The `dedup_hash` query uses standard SQL (no SQLite-specific syntax), compatible with a future Postgres switch | PASS |
| V. Mandatory Human Review | N/A — no sensitive decision (categorization, transfer) is made in this feature | N/A |
| VI. Categorical Confidence | N/A — `confidence` isn't filled in by this feature | N/A |
| VII. Deterministic Deduplication | Central requirement (FR-006): hash of `date+description_raw+amount+account` | PASS |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/001-ingest-extratos/
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
│   ├── state.py                     # typed schema for the normalized Transaction (domain)
│   ├── nodes/
│   │   └── ingest.py                # detect_and_parse node — orchestrates parser + repository
│   ├── parsers/
│   │   ├── base.py                  # shared parsing-adapter contract (see contracts/)
│   │   ├── bradesco.py              # Bradesco adapter
│   │   ├── inter.py                 # Inter adapter
│   │   └── detect.py                # automatic bank detection from the file
│   └── db/
│       ├── schema.sql               # transactions table (subset used by this feature)
│       └── repository.py            # dedup_hash check/persistence
└── tests/
    ├── fixtures/
    │   ├── bradesco/                # small CSVs: happy path + edge cases
    │   └── inter/                   # same, for Inter
    └── test_parsers.py

frontend/                             # not used at this stage
```

**Structure Decision**: Single project in `backend/`, reusing the structure already defined in the BRD (section
7). `parsers/` holds the per-bank adapter pattern (Principle II — isolates pandas/file reading from the nodes);
`db/repository.py` holds SQLite access for the `dedup_hash` check. `frontend/` stays empty, out of scope for this
feature and for Phase 1 as a whole.

## Complexity Tracking

*Not applicable — no constitution violations identified.*
