# Implementation Plan: Transaction Categorization

**Branch**: `002-categorize-transacoes` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-categorize-transacoes/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implement the `categorize` node: for each transaction normalized by the ingestion feature (001), check whether the
merchant already has a confirmed category in memory (`confidence = high`, no LLM); if the transfer pattern
(PIX/TED/DOC) has a mirrored amount in another of the user's accounts within ±2 days, suggest "Transferência
interna" without excluding it from the total; otherwise, call the LLM (via a swappable abstraction) to suggest a
category/subcategory from the configured taxonomy, with `confidence` `medium`/`low` and a fallback to "Outros"
when the response doesn't match the taxonomy. Persist category/subcategory/confidence on the transaction, ready
for human review (a future feature).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `langchain-ollama` (via `init_chat_model` — swappable LLM abstraction), `pyyaml`
(taxonomy in `config/categories.yaml`), `sqlite3` (stdlib, via `db/repository.py`)

**Storage**: SQLite — extends the `transactions` table already created by feature 001 (fills in `category`,
`subcategory`, `confidence`, still null) and adds a `merchant_memory` table (merchant → confirmed category
mapping). This feature only reads `merchant_memory`; writing to it is a future feature's responsibility
(`update_memory`).

**Testing**: pytest, with the LLM always mocked (constitution — "The graph is testable with a mocked LLM, without
depending on Ollama running"); deterministic fixtures for a known merchant, a new merchant, a response outside
the taxonomy, and a mirrored transfer pair.

**Target Platform**: local CLI (macOS/Linux), single-user monthly run

**Project Type**: single project inside the monorepo (`backend/`)

**Performance Goals**: N/A — same order of magnitude of volume as feature 001 (dozens of transactions/month)

**Constraints**: Must not depend on a real Ollama server running for tests (LLM always mocked in tests); the
category returned by the LLM can never result in `confidence = high` (Principle VI/FR-006)

**Scale/Scope**: ~1 month of transactions per run, 2 known accounts (Bradesco, Inter)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Application in this feature | Status |
|---|---|---|
| I. Pragmatic Simplicity | Taxonomy as YAML config, no generic rules engine; transfer detection is a direct check (pattern + day window), not a generic matching system | PASS |
| II. Nodes Isolated from Infrastructure | `nodes/categorize.py` orchestrates; LLM access lives in `llm/client.py`, database access in `db/repository.py` — the node never calls `init_chat_model` or `sqlite3` directly | PASS |
| III. Swappable LLM via Abstraction | Core of this feature — `llm/client.py` uses `init_chat_model`, today Ollama/Qwen2.5, swappable without changing `nodes/categorize.py` | PASS |
| IV. Portable Persistence | `merchant_memory` and the `transactions` update use standard SQL | PASS |
| V. Mandatory Human Review | Respected by design: medium/low `confidence` and transfer candidates are never applied as final by this feature — they're left for `human_review` (a future feature) | PASS |
| VI. Categorical Confidence | Central — FR-006/FR-009: `high` only via memory, the LLM never returns `high` directly | PASS |
| VII. Deterministic Deduplication | N/A — this feature doesn't recompute dedup (already resolved by ingestion) | N/A |

No violations — Complexity Tracking doesn't apply.

## Project Structure

### Documentation (this feature)

```text
specs/002-categorize-transacoes/
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
│   ├── nodes/
│   │   └── categorize.py            # categorize node — orchestrates memory + transfer + LLM
│   ├── llm/
│   │   └── client.py                # swappable LLM abstraction (init_chat_model)
│   ├── categorization/
│   │   ├── taxonomy.py              # loads/validates config/categories.yaml, "Outros" fallback
│   │   ├── merchant_memory.py       # reads merchant_memory via db/repository.py
│   │   ├── transfer_detection.py    # PIX/TED/DOC pattern + mirrored amount within ±2 days
│   │   └── llm_categorizer.py       # calls llm/client.py, maps the response to the taxonomy
│   ├── config/
│   │   └── categories.yaml          # initial taxonomy (BRD Appendix A)
│   └── db/
│       ├── schema.sql                # + merchant_memory table
│       └── repository.py             # + functions to read merchant_memory and update a transaction
└── tests/
    ├── fixtures/
    │   └── categorization/           # synthetic transactions: known merchant, new, outside the taxonomy, transfer pair
    └── test_categorize.py

frontend/                             # not used at this stage
```

**Structure Decision**: Reuses the `backend/` structure created by feature 001. The new `categorization/` module
holds the domain logic (taxonomy, memory, transfer detection, LLM call); `llm/client.py` isolates the LLM
abstraction (Principle III); `nodes/categorize.py` only orchestrates, never touching `init_chat_model` or
`sqlite3` directly (Principle II).

## Complexity Tracking

*Not applicable — no constitution violations identified.*
