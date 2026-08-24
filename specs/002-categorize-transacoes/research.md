# Research: Transaction Categorization

No `NEEDS CLARIFICATION` was left in the Technical Context — the business rules are already fixed in the BRD
(sections 4, 5.1, 5.2, Appendix A). This document records the technical decisions needed to implement them.

## Evaluation order: transfer vs. memory vs. LLM

- **Decision**: for each transaction, evaluate in this order: (1) transfer pattern (PIX/TED/DOC) with a mirrored
  amount in another account within ±2 days → suggest "Transferência interna"; (2) merchant already confirmed in
  memory → mapped category with `confidence = high`; (3) otherwise, call the LLM.
- **Rationale**: a transfer is a characteristic of the transaction itself (pattern + mirrored pair), not of the
  merchant — evaluating it first prevents a generic memory entry (e.g. a "PIX ENVIADO" mistakenly mapped in the
  past) from masking a real transfer. This is consistent with the BRD (5.2): the transfer suggestion is always
  `categorize`'s job, never an automatic application of memory.
- **Alternatives considered**: checking memory first — rejected because, since Bradesco's `Histórico` never names
  the counterparty (BRD 6.3), a generic merchant like "PIX ENVIADO" could end up in memory with a wrong category
  and mask real transfers in future runs.

## Merchant identification

- **Decision**: the merchant is the normalized (trim + lowercase) text of `description_raw`. No additional
  normalization (removing document numbers, fuzzy matching) in this first version.
- **Rationale**: pragmatic simplicity (Principle I) — refining normalization is a low-risk incremental change
  that can come later, guided by real merchants observed during monthly review.
- **Alternatives considered**: more aggressive normalization (removing numbers, stemming) — rejected as
  over-engineering at this stage; documented as a possible future improvement in data-model.md.

## Transfer detection (pattern + window)

- **Decision**: transfer pattern = the description contains one of the terms `PIX`, `TED`, `DOC`
  (case-insensitive). Mirrored amount = another transaction, in a different account of the same user, with the
  same absolute amount and the opposite `type` (one `income`, one `expense`), with `date` within ±2 days.
- **Rationale**: literally reflects the BRD 5.2 rule, and is implementable without any additional text analysis —
  important because Bradesco's `Histórico` doesn't allow name-based matching (BRD 6.3).
- **Alternatives considered**: also requiring a textual match between the two transactions — rejected because the
  BRD already identified that this correspondence is weak/nonexistent on the Bradesco side.

## LLM abstraction

- **Decision**: use `init_chat_model` (LangChain) as the single point of LLM client creation, configured via
  environment variables (`OLLAMA_MODEL`, `OLLAMA_BASE_URL`) already planned in the BRD (section 7). `llm/client.py`
  exposes a `categorize_transaction(description, taxonomy) -> (category, subcategory, confidence)` function — the
  node doesn't know the concrete provider.
- **Rationale**: constitution Principle III — future swap to Claude/OpenAI without changing
  `nodes/categorize.py`.
- **Alternatives considered**: calling the Ollama client directly — rejected, it would break the swappability
  required by the constitution.

## Fallback for a category outside the taxonomy

- **Decision**: any LLM response that doesn't exactly match (after simple normalization) a category/subcategory
  in the configured taxonomy is replaced with `category = "Outros"`, `confidence = low`.
- **Rationale**: FR-005/SC-002 — no transaction can end up without a valid category; "Outros" is already the
  fallback category defined in the BRD's Appendix A.
- **Alternatives considered**: re-prompting the LLM with a stricter prompt until getting a valid category —
  rejected as unnecessary complexity at this stage (Principle I); can be revisited if the fallback rate proves
  high in practice.

## Testing strategy

- **Decision**: the LLM is always mocked (the `categorize_transaction` function replaced by a deterministic
  double in tests); fixtures covering an already-confirmed merchant, a new merchant, an LLM response outside the
  taxonomy, and a pair of mirrored transactions inside/outside the 2-day window.
- **Rationale**: aligned with the constitution ("Testing Standards") and with the spec's User Stories.
- **Alternatives considered**: integration tests against a real Ollama — rejected as a test dependency; left as
  manual validation (quickstart.md), not part of the automated suite.
