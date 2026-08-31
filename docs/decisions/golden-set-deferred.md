# Decision: defer the categorization golden set until a genuinely reviewed month exists

**Branch**: `main` (scope decision, not an implementation)
**Date**: 2026-08-30
**Status**: Accepted
**Related**: [docs/brd-financial-planner-agent.md](../brd-financial-planner-agent.md) §9 (Testing strategy — "Categorization golden set")

## Problem

BRD §9 calls for a golden set: ~30–40 real/anonymized transactions with
known-correct categories, used to measure categorization accuracy — "critical when
switching from a local LLM to Claude/OpenAI" in Phase 2.

The obvious source for the ~40 rows is the only substantial processed month in
`data/financial-planner.db`: `2026-07`, 109 transactions, all stored at
`confidence = 'high'`.

## Why those labels can't be used as ground truth

`confidence = 'high'` is set by only two code paths: a `merchant_memory` hit, or a
`human_review` confirmation. The DB's `merchant_memory` table is populated (40
rows), and it is only ever written by `update_memory`, which runs after
`human_review` — so the review node did execute over this month.

But the review was **not** a real human categorizing their own finances. The month
was processed during `007-generate-report` task T012 ("full graph, real Ollama,
both real months") as an implementation-validation run, with the `interrupt()`
prompts auto-answered (accept the LLM's suggestion). Evidence:

- **45 of 109 rows (41%) are `Outros`**, the explicit low-confidence fallback
  bucket. A human who knew these transactions would have moved the obvious ones
  (e.g. `Viasul` — a bus company — to `Transporte`; `Usina Do Corpo` — a gym — to
  `Saúde`; `Imobiliaria Vila Rica` to `Moradia`).
- `Cdb Pos Di Liq. Banco Inter` → `Receita` and `Pagamento Fatura - <name>` →
  `Outros` are both stored — the exact two miscategorizations fixed on 2026-08-30
  (see `config/categories.yaml` `Investimento`, and the "Pagamento Fatura" prompt
  guidance in `llm_categorizer.py`). Human review would very likely have caught
  "my investment purchase isn't income".

A golden set built from these labels would only measure whether the categorizer
reproduces its own earlier guesses — worthless as an accuracy benchmark. The
value of a golden set is entirely in a one-time human labelling pass, which has
not happened yet.

## Decision

Defer the golden set. Build it after the user processes at least one month through
a real, attentive `human_review` (or sets aside ~30 minutes to label a curated,
anonymized sample by hand). At that point:

- Curate ~35–40 diverse rows covering every taxonomy category.
- Anonymize: keep merchant/business names (they are the signal), replace
  natural-person names with `PESSOA FISICA NN` placeholders, strip phone/document
  numbers, drop balance/`Docto.`/hash columns. No placeholder→real-name mapping in
  any committed file (BRD §8).
- Exclude `Transferência interna` rows (transfer detection needs cross-account
  context an isolated CSV lacks — it has its own test coverage).
- Land it as `backend/tests/golden_set.csv` + an opt-in harness
  (`backend/tests/test_golden_set.py`, `-m golden`, real LLM, empty merchant
  memory so every row exercises the LLM) that reports overall + per-category
  accuracy without gating the default suite.

## Related finding — `merchant_memory` was seeded with unreviewed guesses (resolved 2026-08-30)

`data/financial-planner.db`'s `merchant_memory` table held 40 auto-accepted
mappings from the T012 run, including wrong ones (`cdb pos di ... → Receita`,
`pagamento fatura ... → Outros`) and real personal names. Memory hits are applied
as `high` confidence and **bypass `human_review`**, so every future run would have
silently re-applied these.

Cleared on 2026-08-30 (backup: `data/financial-planner.db.bak-20260830-213809`):
`DELETE FROM merchant_memory` (all 40 rows) and `DELETE FROM transactions WHERE
month_ref IN ('2026-06','2026-08')` (6 stray uncategorized ingest rows with no
graph checkpoint). The 109 `2026-07` transactions and the `2026-07` checkpoint
were kept. `merchant_memory` rebuilds itself from real `human_review`
confirmations on the first genuine monthly run.

## Consequences

- No accuracy safety net for the Phase 2 LLM swap until the golden set is built.
  Mitigation: make building it a prerequisite task of the Phase 2 "swap to Claude"
  work, not an afterthought.
- `2026-07`'s stored categories remain usable as a *starting draft* for the
  labelling pass (pre-filled cells to correct), just not as-is.
