# Contract: Transfer Detection

## `categorization/transfer_detection.py`

**Input**: a candidate transaction + the list of all other transactions already imported in the same monthly
batch (across all of the user's known accounts).

**Output**: `bool` (is a transfer candidate) — or, when wired into the node, directly the assignment
`category = "Transferência interna"`, `confidence = "medium"` when `True`.

**Guarantees the contract requires**:
- Only considers transactions from **accounts different** from the one being evaluated (never compares a
  transaction with another from the same account).
- Requires a transfer pattern in the description (`PIX`, `TED`, or `DOC`, case-insensitive) **and** a mirrored
  amount (same absolute value, opposite `type`) in another account, with `date` within a ±2-day window — both
  conditions are mandatory, neither is sufficient alone.
- Never excludes the transaction from the total nor marks it as confirmed — only flags the suggestion (FR-008).

## Usage by the `categorize` node

Evaluated before `merchant_memory.py` and before `llm_categorizer.py` (see research.md — evaluation order).
