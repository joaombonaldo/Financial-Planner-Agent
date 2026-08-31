# Feature Specification: Categorization Taxonomy Rework

**Feature Branch**: `011-taxonomy-reorg`

**Created**: 2026-08-30

**Status**: Implemented

**Input**: User description: "Reorganizar a taxonomia de categorias para refletir como eu realmente uso
o cartão de débito/PIX e o cartão de crédito. Renomear `Vestuário` para `Compras` com subcategorias mais
amplas (perfumes/cosméticos, eletrônicos, casa), transformar `Cartão de crédito/Parcelamentos` em apenas
`Cartão de crédito` (a linha de pagamento da fatura no débito, que continua contando no total), adicionar
`Saúde/Psicólogo/Terapia`, `Lazer/Restaurante/Bar`, `Lazer/Passeios/Atividades` e `Receita/Rendimentos`,
e remover subcategorias que nunca apareceram nos extratos reais (`Transporte público`, `Estacionamento`,
`Livros`). Categoria e instrumento de pagamento (débito vs crédito) são independentes."

## Problem

The taxonomy in `config/categories.yaml` was written before any real usage. After the user described how
they actually spend — debit/PIX out of the checking account plus a credit card whose fatura is paid from
that same account — several buckets no longer fit:

- `Vestuário` (Roupas, Calçados) is too narrow; real shopping also covers perfumes/cosmetics,
  electronics/tech, and generic house/other items, on **either** instrument.
- `Cartão de crédito/Parcelamentos` conflates installment tracking (deferred to Phase 3) with what Phase 1
  actually needs: a home for the single monthly debit-side fatura payment line.
- There is no home for psychologist/therapy spend, for dinners/bars/outings as leisure (distinct from
  travel/shows/hobbies), or for investment **yield** (distinct from investment contributions).
- `Transporte público`, `Estacionamento`, and `Livros` never appeared in the real exports.

A cross-cutting point from the user: **category and payment instrument are independent**. Any category can
occur on debit or on credit — `Lazer` and `Compras` are not credit-only. The debit-vs-credit total rules
are the report node's responsibility, not the taxonomy's.

## The new taxonomy

| Category | Subcategories |
|---|---|
| Moradia | Aluguel/Financiamento, Condomínio, Energia, Água, Internet, Gás |
| Alimentação | Mercado, Café/Lanches, Restaurante/Delivery |
| Transporte | Combustível, Uber/99, Manutenção veículo |
| Saúde | Psicólogo/Terapia, Farmácia, Plano de saúde, Consultas |
| Assinaturas | Streaming, Academia, Seguros, Software/SaaS |
| Lazer | Restaurante/Bar, Passeios/Atividades, Viagem, Eventos/Shows, Hobbies |
| Compras | Roupas/Calçados, Perfumes/Cosméticos, Eletrônicos/Tecnologia, Casa/Outros |
| Educação | Cursos, Mensalidade |
| Investimento | *(none — Phase 3 owns investment detail)* |
| Cartão de crédito | *(none — debit-side fatura payment line; NOT excluded from totals)* |
| Transferência interna | *(none — excluded from spend totals)* |
| Receita | Salário, Reembolso, Rendimentos, Freelance/Extra, Outras entradas |
| Outros | *(none — low-confidence fallback)* |

## What changed and why

| Change | Rationale |
|---|---|
| `Vestuário` → **`Compras`**; subcats → Roupas/Calçados, Perfumes/Cosméticos, Eletrônicos/Tecnologia, Casa/Outros | User shops for more than clothing on both instruments |
| `Cartão de crédito/Parcelamentos` → **`Cartão de crédito`** | Phase 1 only needs the one debit-side fatura payment line; installment detail is Phase 3 |
| `Alimentação/Padaria/Café` → **`Café/Lanches`** | Covers daily coffee/bakery/snack spend more naturally |
| Add `Saúde/Psicólogo/Terapia` | Recurring therapy spend had no home |
| Add `Lazer/Restaurante/Bar`, `Lazer/Passeios/Atividades` | Dinners/bars/outings are leisure but distinct from travel/shows/hobbies |
| Add `Receita/Rendimentos` | Investment yield/interest (`RENTAB`, `Rendimento`) was landing in generic `Receita` or `Outros` |
| Drop `Transporte/Transporte público`, `Transporte/Estacionamento`, `Educação/Livros` | Never observed in real exports |
| Keep `Investimento` (added last session), `Assinaturas/Seguros` (now also in BRD Appendix A) | CDB/Aplicação contributions and card insurance already needed these |

## Requirements

- **FR-001**: `config/categories.yaml` MUST contain exactly the tree above; `load_taxonomy` MUST accept every
  category/subcategory in it and reject anything else (unchanged validation behavior).
- **FR-002**: `TRANSFER_CATEGORY` (`"Transferência interna"`) and `FALLBACK_CATEGORY` (`"Outros"`) MUST be
  unchanged.
- **FR-003**: The LLM categorizer prompt's "Orientações específicas" block MUST route: investment buys
  (CDB/Aplicação/RDB/Tesouro) → `Investimento`; investment yield (`RENTAB`, `Rendimento`) →
  `Receita/Rendimentos`; credit-card bill payment lines (`Pagamento efetuado`, `Pagamento Fatura`,
  `PAGAMENTO DE FATURA`) → `Cartão de crédito`; dinners/bars/dates → `Lazer/Restaurante/Bar` or
  `Lazer/Passeios/Atividades`; perfumes/cosmetics/clothes/shoes/electronics → `Compras/...`;
  psychologist/therapy → `Saúde/Psicólogo/Terapia`; small daily coffee/bakery/snacks →
  `Alimentação/Café/Lanches`. Prompt stays in Portuguese.
- **FR-004**: The committed `config/budget.example.yaml` MUST validate against the new taxonomy.
- **FR-005**: BRD Appendix A MUST reflect the new tree and drop findings notes that are now implemented.
- **FR-006**: A migration record (`docs/decisions/taxonomy-reorg.md`) MUST document the old→new mapping and
  provide ready-to-run SQL for the existing `data/financial-planner.db`. The DB writes are executed by the
  user, not by this feature.
- **FR-007**: No old literal (`"Cartão de crédito/Parcelamentos"`, `"Vestuário"`, `"Padaria/Café"`) may
  remain anywhere under `backend/src`.

## Success Criteria

- **SC-001**: `uv run --project backend pytest -q` passes with the new taxonomy and added coverage.
- **SC-002**: `Compras` and each of its subcategories validate as a taxonomy entry.
- **SC-003**: A psychologist-style description resolves to `Saúde/Psicólogo/Terapia` and a perfume-style
  description resolves to `Compras/Perfumes/Cosméticos` through the deterministic `FakeChatModel` harness.
- **SC-004**: The new prompt guidance lines are present in the rendered prompt.

## Out of Scope

- The report-node **debit-vs-credit total rules** (feature B). The taxonomy only says the two instruments
  are independent; where each category counts toward which total is decided in `nodes/report.py`.
- The **credit-card transaction stream** (feature C) — importing/attributing individual credit-card line
  items. Phase 1 keeps a single aggregate `Cartão de crédito` debit-side payment line.
- Installment-level tracking — remains Phase 3 (`docs/decisions/installments-deferred-to-phase-3.md`).
- Recategorizing the unreviewed `2026-07` month beyond the mechanical label renames in the migration doc.

## Assumptions

- `data/financial-planner.db` currently holds 109 rows (all `month_ref='2026-07'`), no populated
  subcategories, no `Vestuário` rows, and an empty `merchant_memory` table — so only the
  `Cartão de crédito/Parcelamentos` → `Cartão de crédito` rename touches live rows (9). Other migration
  statements are safe no-ops today, relevant only to older backups/re-imports.
- The LLM cannot be forced to emit an exact category; prompt guidance strengthens the instruction, and
  `human_review` remains the safety net (same as feature 008).
