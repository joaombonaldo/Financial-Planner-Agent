# Decision: rework the category taxonomy to match real debit/PIX + credit-card usage

**Branch**: `main` (spec `011-taxonomy-reorg`; no feature branch — worked directly on `main`)
**Date**: 2026-08-30
**Status**: Implemented
**Related**: [docs/brd-financial-planner-agent.md](../brd-financial-planner-agent.md) Appendix A, [specs/011-taxonomy-reorg/spec.md](../../specs/011-taxonomy-reorg/spec.md), [golden-set-deferred.md](golden-set-deferred.md) (the same `2026-07` month is the data affected here), [installments-deferred-to-phase-3.md](installments-deferred-to-phase-3.md) (`Cartão de crédito` stays a single aggregate line until Phase 3)

## Problem

The taxonomy in `config/categories.yaml` was the pre-usage guess from BRD Appendix A.
After the user described how they actually use their two instruments (debit/PIX from
the checking account, plus a credit card whose fatura is paid from that same
account), several categories no longer matched:

- `Vestuário` (Roupas, Calçados) was too narrow — real shopping spans perfumes and
  cosmetics, electronics/tech, and generic house/other purchases, on **both**
  instruments.
- `Cartão de crédito/Parcelamentos` conflated two ideas. Installment-level tracking
  is deferred to Phase 3 (see `installments-deferred-to-phase-3.md`); what Phase 1
  actually needs is a home for the one monthly debit-side fatura payment line.
- No home for psychologist/therapy spend, for dinners/bars/outings as leisure
  (distinct from travel/shows/hobbies), or for investment **yield** (as opposed to
  investment contributions, which `Investimento` already covers).
- `Transporte público`, `Estacionamento`, `Livros` never appeared in the real
  exports.

A cross-cutting clarification from the user: **category and payment instrument are
independent**. Any category can occur on debit or on credit — `Lazer` and `Compras`
are not credit-only. The debit-vs-credit total rules are the report node's job, not
the taxonomy's.

## Decision

Replace the `categories:` tree in `config/categories.yaml` with the tree in
`specs/011-taxonomy-reorg/spec.md` / BRD Appendix A. Update the LLM categorizer
prompt guidance, the committed budget example, the BRD appendix, and this record.
`TRANSFER_CATEGORY` (`"Transferência interna"`) and `FALLBACK_CATEGORY` (`"Outros"`)
are unchanged.

Out of scope (features B and C, other agents): the report-node debit-vs-credit
total rules, and the credit-card transaction stream.

## Old → new mapping

### Category renames

| Old | New | Notes |
|---|---|---|
| `Vestuário` | `Compras` | subcategories broadened (see below) |
| `Cartão de crédito/Parcelamentos` | `Cartão de crédito` | single debit-side fatura payment line; still confirmed in `human_review` |

### Subcategory renames

| Category (new) | Old subcategory | New subcategory |
|---|---|---|
| `Alimentação` | `Padaria/Café` | `Café/Lanches` |
| `Compras` (was `Vestuário`) | `Roupas`, `Calçados` | folded into `Roupas/Calçados` |

### Added

- `Saúde/Psicólogo/Terapia`
- `Lazer/Restaurante/Bar`, `Lazer/Passeios/Atividades`
- `Compras/Perfumes/Cosméticos`, `Compras/Eletrônicos/Tecnologia`, `Compras/Casa/Outros`
- `Receita/Rendimentos` (investment yield/interest — `RENTAB`, `Rendimento`)
- `Assinaturas/Seguros` was already present in config; it is now also reflected in the BRD appendix

### Removed

- `Transporte/Transporte público`, `Transporte/Estacionamento`
- `Educação/Livros`

### Unchanged

`Moradia`, `Transporte` (minus the two dropped subcats), `Investimento` (added last
session), `Transferência interna`, `Outros`, and all of `Receita`'s other
subcategories.

## Data migration for `data/financial-planner.db`

`data/financial-planner.db` is gitignored real data: **109 transactions, all in
`month_ref = '2026-07'`**, categorized during the `007-generate-report` validation
run (see `golden-set-deferred.md`). Inspection of the live DB on 2026-08-30:

- `category` values present: `Outros` (45), `Transferência interna` (25),
  `Alimentação` (10), `Transporte` (9), **`Cartão de crédito/Parcelamentos` (9)**,
  `Receita` (4), `Lazer` (3), `Saúde` (2), `Moradia` (1), `Educação` (1).
- **No `subcategory` values are populated at all** (every row's subcategory is
  empty — the validation run auto-accepted category-only suggestions).
- **No `Vestuário` rows.**
- `merchant_memory` is **empty** (0 rows — it was cleared on 2026-08-30, see
  `golden-set-deferred.md`), so there is nothing to remap there.

So on the current DB only the `Cartão de crédito/Parcelamentos` → `Cartão de
crédito` rename actually touches rows (9). The other statements are included for
completeness / safety and are harmless no-ops against this DB; they matter only if
an older backup or a re-import from before this change is loaded.

**The user runs these — this doc does not execute DB writes.** Back up first
(`cp data/financial-planner.db data/financial-planner.db.bak-$(date +%Y%m%d-%H%M%S)`).

```sql
UPDATE transactions SET category='Cartão de crédito' WHERE category='Cartão de crédito/Parcelamentos';
UPDATE transactions SET category='Compras' WHERE category='Vestuário';
UPDATE transactions SET subcategory='Café/Lanches' WHERE subcategory='Padaria/Café';
UPDATE transactions SET subcategory='Roupas/Calçados' WHERE category='Compras' AND subcategory IN ('Roupas', 'Calçados');

-- merchant_memory is empty today; run these only if a non-empty memory table is ever restored:
UPDATE merchant_memory SET category='Cartão de crédito' WHERE category='Cartão de crédito/Parcelamentos';
UPDATE merchant_memory SET category='Compras' WHERE category='Vestuário';
UPDATE merchant_memory SET subcategory='Café/Lanches' WHERE subcategory='Padaria/Café';
UPDATE merchant_memory SET subcategory='Roupas/Calçados' WHERE category='Compras' AND subcategory IN ('Roupas', 'Calçados');
```

Dropped subcategories (`Transporte público`, `Estacionamento`, `Livros`) are not
present in the DB; if a future restore contains them, they would need manual
recategorization (there is no automatic target) — none exist today.

## Consequences / things to watch

- The `2026-07` month keeps its category-level data; the 9 renamed rows still
  reach the same reports/insights under the new name. Nothing is recategorized in
  meaning, only in label.
- `2026-07`'s categories were never human-reviewed (see `golden-set-deferred.md`),
  so the 45 `Outros` rows remain a draft, unaffected by this reorg.
- Any future re-import of a pre-2026-08-30 export will produce old-name categories
  again only if it also restores the old `config/categories.yaml`; with the new
  config the LLM path emits new names directly.
- New subcategories under `Compras`/`Lazer`/`Saúde` are only suggested where the
  prompt guidance fires; everything else still flows through `human_review`.
