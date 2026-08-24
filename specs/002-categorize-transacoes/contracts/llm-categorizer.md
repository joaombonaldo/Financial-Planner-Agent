# Contract: LLM Categorizer

Internal interface between `nodes/categorize.py` and the LLM layer. Consumed only by the node — no other module
calls `llm/client.py` directly (Principle II).

## `llm/client.py`

**Responsibility**: the single point of chat model client creation (`init_chat_model`), configured via
`OLLAMA_MODEL`/`OLLAMA_BASE_URL`. Knows nothing about taxonomy or business rules — it only knows how to talk to an
LLM.

## `categorization/llm_categorizer.py`

**Input**: the transaction description (`description_raw`) + the loaded taxonomy (`categorization/taxonomy.py`).

**Output**: `(category: str, subcategory: str | None, confidence: Literal["medium", "low"])`.

**Guarantees the contract requires**:
- Never returns `confidence = "high"` — reserved exclusively for merchant-memory matches (FR-006).
- Always returns a category belonging to the configured taxonomy — if the LLM's raw response doesn't match any
  valid entry, the module already applies the fallback (`"Outros"`, `confidence = "low"`) before returning; the
  caller never has to validate the taxonomy again.
- It's the only function in this feature that actually invokes `llm/client.py` — testable in isolation with a
  double standing in for the real client (constitution — "graph testable with a mocked LLM").

## Usage by the `categorize` node

`nodes/categorize.py` only calls this function when the transaction wasn't resolved by `merchant_memory.py` nor
by `transfer_detection.py` (see research.md — evaluation order). The node never imports `llm/client.py` directly.
