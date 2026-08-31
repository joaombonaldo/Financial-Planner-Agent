# BRD — Financial Planner with AI Agents (LangGraph)

**Status:** Draft v1
**Last updated:** 2026-08-25
**Author:** João Miguel

---

## 1. Project overview

Personal study project aimed at learning AI agent architecture hands-on, by building a financial planner that:

- Imports bank statements (CSV/Excel) from 2 banks
- Automatically categorizes transactions using an LLM, with human review (human-in-the-loop)
- Tracks credit card installments, transfers between the user's own accounts, income and expenses
- Compares spending against budget goals defined by the user
- Generates monthly insights about the financial situation
- Keeps history across monthly runs

The project is used by a single user (the author), run on a monthly cadence (possibly weekly).

---

## 2. Learning goals

- Practice LangGraph: `StateGraph`, `checkpointer`, `interrupt()`/human-in-the-loop, conditionals
- Practice decoupled architecture (domain / infrastructure / interface separation)
- Practice React in Phase 2 (dashboard + review via UI)
- Learn Supabase (hosted Postgres) in Phase 2

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Agent orchestration | LangGraph | Single graph with specialized nodes (not a multi-agent supervisor — unnecessary for this flow) |
| LLM | Local Ollama, **Qwen2.5** model | Future swap to Claude/OpenAI via `init_chat_model()`, without changing nodes |
| Data parsing | pandas + openpyxl | Market standard for CSV/Excel |
| Persistence (phase 1) | SQLite | LangGraph checkpointer + merchant memory + history, all in the same database |
| Persistence (phase 2) | Supabase (Postgres) | Free tier ($0/month); migration via `langgraph-checkpoint-postgres`, same interface as SQLite |
| Observability | LangSmith | Automatic tracing via environment variables, no code changes |
| Dependency manager | `uv` | |
| Interface (phase 1) | CLI | Focus on validating the agent flow before investing in UI |
| Interface (phase 2) | React + FastAPI | FastAPI exposes `core/` via an async API (needed because of `interrupt()`) |
| Repository | Monorepo (`backend/` + `frontend/`) | Personal project, single dev — separate repos bring no benefit here |

---

## 4. Graph architecture (LangGraph)

Sequential flow of 7 nodes, with one human interruption point:

```
detect_and_parse → categorize → human_review (interrupt) → update_memory
    → budget_check → generate_insights → generate_report
```

| Node | Responsibility | Uses LLM? |
|---|---|---|
| `detect_and_parse` | Identifies the source bank and normalizes the data via an adapter pattern (1 parser per bank) | No |
| `categorize` | Categorizes transactions; uses memory of already-confirmed merchants, only calls the LLM for new/ambiguous cases | Yes |
| `human_review` | Interrupts the graph (`interrupt()`) for review/correction of medium/low confidence items | No |
| `update_memory` | Persists corrections into the merchant → category mapping | No |
| `budget_check` | Compares spending per category against defined goals | No |
| `generate_insights` | Generates observations about trends and comparisons with previous months | Yes (optional) |
| `generate_report` | Assembles the month's final report | No |

**Thread strategy:** each processed month gets its own `thread_id` in the checkpointer (e.g. `2026-08`), allowing a month to be reprocessed/audited in isolation. History across months lives in the data layer (SQLite/Supabase), not in the graph state.

---

## 5. Business rules

### 5.1 Categorization
- Taxonomy with categories and subcategories (see Appendix A), extensible as real usage grows
- Confidence represented categorically (`high` / `medium` / `low`), not numerically — aligned with what LLMs can reliably estimate
- `high`: already-known merchant → passes straight through
- `medium`/`low`: goes to `human_review`
- Subcategory selection is required whenever the chosen category has subcategories in the taxonomy — the LLM is instructed to always pick one in that case, not just the top-level category (categories with no subcategories, e.g. `Outros`, keep an empty subcategory). Since every LLM-sourced categorization is already `medium`/`low` confidence and therefore always goes through `human_review`, a wrong subcategory guess is never a new risk — it's still caught by the existing review step (see specs/008-required-subcategory). During `human_review`, the valid subcategories for the suggested category are shown to the user to make correcting/confirming easier.

### 5.2 Transfers between the user's own accounts
- Transactions with a transfer pattern (`TED`, `PIX`, `DOC`) and a mirrored amount in another account (±2-day window) are **suggested** as "Transferência interna" (internal transfer) by `categorize`, but confirmed via `human_review` — never excluded automatically without supervision
- Confirmed transfers are excluded from the total of expenses/income

### 5.3 Installments (credit card)
- Each installment shows up in the normal monthly spend of its corresponding category
- There's a dedicated table (`installments`) with total amount, number of installments, paid/remaining installments — queryable as a separate view
- **Deferred to Phase 3** (decided 2026-08-30, see [docs/decisions/installments-deferred-to-phase-3.md](decisions/installments-deferred-to-phase-3.md)). Individual installment charges already flow through the pipeline in their category's spend (first bullet); only the aggregate `installments` table/view is deferred, alongside the Phase 3 investment-tracking work. The `installment_id` column stays as a nullable forward-compat stub.

### 5.4 Income and expenses
- The system tracks full movement (inflows and outflows), not just spending
- Transaction `type` field: `income` / `expense` / `transfer` (extensible to support investments in Phase 3)

### 5.5 Budget goals
- Phase 1: `config/budget.local.yaml` file (gitignored), read via a `get_budget()` function
- Phase 2: the same function starts reading from Supabase, without changing the rest of the system

---

## 6. Data model

### 6.1 Transaction (normalized schema)

```
id                  # PK auto-increment
dedup_hash          # hash(date + description_raw + amount + account) — prevents duplication on reimport
date
description_raw     # as it came from the bank
account             # source bank/account
type                # income | expense | transfer
amount              # always positive; type indicates direction
category
subcategory
confidence          # high | medium | low
installment_id      # FK, nullable
month_ref           # e.g. "2026-08"
```

### 6.2 Installments

```
installments
├── id
├── description
├── total_amount
├── num_installments
├── installment_amount
├── first_charge_date
└── account
```

### 6.3 Source format per bank

**Status: confirmed from real exports** (period 24/07 to 22/08/2026, 1 month, both banks).

| Aspect | Bradesco | Inter |
|---|---|---|
| Encoding | UTF-8 **with BOM** (`EF BB BF`) — requires `utf-8-sig` when reading | UTF-8 without BOM |
| Separator | `;` | `;` |
| Number format | Brazilian (`1.645,20` = one thousand six hundred forty-five point twenty) | Brazilian, same |
| Date format | `DD/MM/YYYY` | `DD/MM/YYYY` |
| Amount column | **Two separate columns**: `Crédito (R$)` and `Débito (R$)` (one populated, the other blank) | **Single column** `Valor`, signed (negative = debit) |
| Transaction description | `Histórico` (e.g. "PIX ENVIADO", "PIX RECEBIDO") — **never includes the counterparty's name** | `Histórico` (generic type, e.g. "Compra no débito") + `Descrição` (merchant/person name) — **`Descrição` comes blank on some rows**, needs a fallback to `Histórico` |
| Native identifier | `Docto.` column (document number) | Doesn't exist — only running balance |
| Running balance | Yes, `Saldo (R$)` column | Yes, `Saldo` column |
| Metadata lines in the file | Line 1 (branch/account), then header | 4 lines (title, account, period, balance) + blank line, then header |
| Section structure | **Two sections in the same file**: main statement + "Últimos Lancamentos" block (header repeated mid-file) + "Total" footer line | Single section |

**Parsing strategy adopted (validated against the real files):** instead of a fixed `skiprows`, every line is tested against a date regex (`^\d{2}/\d{2}/\d{4};`) — only matching lines become a transaction. This robustly handles the Bradesco case (metadata, header duplicated mid-file, footer total line, blank lines) without needing to map the exact line-by-line structure. Tested on the real file: 54 total lines → 42 valid transaction lines.

**Findings that impact decisions already made:**
- **Internal transfer detection (section 5.2) is weaker on the Bradesco side**: since Bradesco's `Histórico` never names the counterparty (just generic "PIX ENVIADO"/"PIX RECEBIDO"), matching a transfer between the two own accounts will depend almost entirely on **mirrored amount + date window**, not text — which was already the designed rule, but we've now confirmed there's no extra textual signal on the Bradesco side to reinforce the match. This reinforces the decision to always keep this in `human_review`, never automatic.
- **`dedup_hash` (section 6.1) remains necessary even though no exact duplicate was found in this sample** — Bradesco has two sections (`main statement` + `Últimos Lancamentos`) with potential overlap in future re-exports (e.g. re-exporting to include already-processed days).
- **The `Saldo` (balance) column on both banks** can serve as a parser sanity check in automated testing: the previous row's balance ± the current row's amount should match the following row's balance.

---

## 7. Repository structure

```
financial-planner-agent/
├── backend/
│   ├── pyproject.toml
│   ├── src/financial_planner/
│   │   ├── graph.py              # builds and compiles the StateGraph
│   │   ├── state.py              # typed schema (domain)
│   │   ├── nodes/                # use cases — orchestrate, don't implement direct I/O
│   │   │   ├── ingest.py
│   │   │   ├── categorize.py
│   │   │   ├── review.py
│   │   │   ├── memory.py
│   │   │   ├── budget.py
│   │   │   ├── insights.py
│   │   │   └── report.py
│   │   ├── parsers/               # adapters — 1 file per bank
│   │   ├── db/                    # persistence adapter
│   │   │   ├── schema.sql
│   │   │   └── repository.py
│   │   ├── config/
│   │   │   ├── categories.yaml
│   │   │   └── budget.example.yaml
│   │   └── interface/
│   │       ├── cli.py             # phase 1
│   │       └── api.py             # phase 2 — FastAPI
│   └── tests/
│       ├── fixtures/              # fake CSVs per bank
│       ├── golden_set.csv         # transactions with known-correct category
│       ├── test_parsers.py
│       └── test_graph.py
├── frontend/                       # phase 2 — React
├── extracts/                       # gitignored — real exports
└── README.md
```

**Architectural principle:** nodes never access the database/LLM directly — always via `db/repository.py` or an abstracted LLM client. This keeps the dependency direction correct (business logic doesn't depend on infrastructure) without needing formal interfaces (`Protocol`/ABC), which would be over-engineering for a project of this size.

### Environment variables (`.env`)
`OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `SQLITE_DB_PATH`

---

## 8. Sensitive data strategy

- No real data (statements, personal categories, goals, the `.db` database) enters the repository
- `.gitignore` covers: `extracts/`, `*.db`, `config/budget.local.yaml`, `.env`
- The repository only versions reusable code + `config/budget.example.yaml` with fictitious values

---

## 9. Testing strategy

- **Parser unit tests** — small fixtures (2-3 lines) per bank, deterministic
- **Categorization golden set** — ~30-40 real/anonymized transactions with known-correct category, used to measure accuracy (critical when switching from a local LLM to Claude/OpenAI). **Not built yet — deferred until a genuinely human-reviewed month exists** (decided 2026-08-30, see [docs/decisions/golden-set-deferred.md](decisions/golden-set-deferred.md)); should be a prerequisite of the Phase 2 "swap to Claude" work.
- **Graph with mocked LLM** — validates node/edge wiring without depending on Ollama running

---

## 10. Scope and roadmap

### MVP (Phase 1)
- CLI, 1 user, 2 banks
- Categorization + human review + simple report
- **Acceptance criteria:**
  1. Process a real month from 2 banks without error
  2. Review/correction works via CLI
  3. Final report matches the sum manually checked against the statement
  4. Generated insights correctly reflect the month's financial situation, in a way that helps understand where the money is going

### Phase 2
- React + dashboards + visual history
- Persistence migration to Supabase
- FastAPI backend exposing `core/` via an async API (start-run → poll-status → resume-review pattern)

### Phase 3
- Investment tracking (beyond financial planning)

---

## 11. Out of scope (explicit)

- Automatic bank integration (open banking/API) — manual export is an assumption of the whole project
- Multi-user/authentication in the MVP (even after migrating to Supabase in Phase 2, usage stays personal)
- Mobile app
- Real-time alerts (`budget_check` only runs when the month is processed, doesn't monitor continuously)

---

## Appendix A — Initial category taxonomy

Category and subcategory names are kept in Portuguese here and throughout the codebase (`config/categories.yaml`), since this is the taxonomy the user actually applies to their own (Brazilian) finances.

| Category | Subcategories |
|---|---|
| Moradia | Aluguel/Financiamento, Condomínio, Energia, Água, Internet, Gás |
| Alimentação | Mercado, Restaurante/Delivery, Padaria/Café |
| Transporte | Combustível, Uber/99, Transporte público, Manutenção veículo, Estacionamento |
| Saúde | Plano de saúde, Farmácia, Consultas |
| Assinaturas | Streaming, Software/SaaS, Academia |
| Lazer | Viagem, Eventos/Shows, Hobbies |
| Educação | Cursos, Livros, Mensalidade |
| Vestuário | Roupas, Calçados |
| Cartão de crédito/Parcelamentos | (own view — see section 5.3) |
| Transferência interna | (excluded from spend total — see section 5.2) |
| Receita | Salário, Freelance/Extra, Reembolso, Outras entradas |
| Investimento | Added ahead of Phase 3 to reduce CDB/Aplicação miscategorization; full investment tracking remains Phase 3 |
| Outros | Fallback for low confidence |

*Initial list — subject to expansion as real merchants show up during monthly review.*

**Findings from the real exports that suggest a taxonomy adjustment:**
- `Aplicação` (e.g. "Cdb Pos Di Liq. Banco Inter") — an investment contribution. A dedicated `Investimento` category now exists (added ahead of Phase 3 to reduce this specific CDB/Aplicação miscategorization, which was landing as `Receita`); full investment tracking still arrives in Phase 3.
- `Deb Cartao + Protegido` (card insurance) — suggested as a new `Seguros` subcategory under `Assinaturas`.
- `Pagamento efetuado` / "Pagamento Fatura" (credit card bill payment, leaving the checking account) — maps to `Cartão de crédito/Parcelamentos` as the month's aggregate payment; it's made up of the individual installments already categorized separately (see section 5.3). This is now encoded as categorizer prompt guidance (descriptions like "Pagamento efetuado" / "Pagamento Fatura" / "PAGAMENTO DE FATURA" are suggested as `Cartão de crédito/Parcelamentos`), still confirmed during `human_review` like every other suggestion.
