# Quickstart: Validating Generate Insights

End-to-end validation guide for this feature. No implementation code — just the steps to prove the spec's
behavior works.

## Prerequisites

- `backend/` environment with dependencies resolved (`uv sync`)
- LLM always mocked in automated tests — no scenario below needs Ollama running

## Scenario 1 — Grounded summary for a single month (User Story 1)

1. Seed categorized transactions and a budget comparison for one month.
2. Run insight generation with a fake chat model that records the prompt it received.
3. Verify the returned summary matches the fake model's canned response, and that the prompt included the real
   category spend and the budget comparison.

**Expected result**: the LLM is given real data, and the returned summary is exactly what it produced.

## Scenario 2 — Comparison with the previous month (User Story 2)

1. Seed categorized transactions for two consecutive months, with a noticeable difference in one category.
2. Run insight generation for the second month; verify the prompt included both months' category totals.
3. Repeat with no data at all for the first month; verify generation still succeeds, with no comparison claimed
   in the prompt.

**Expected result**: the comparison appears only when real prior-month data exists.

## Scenario 3 — LLM failure never blocks processing (User Story 3)

1. Configure a chat model double that raises on `invoke()`; run insight generation.
2. Verify the call returns an `InsightsResult` with `error` set and `summary = None` — no exception propagates.
3. Repeat with a double that returns a blank response; verify the same failure handling applies.

**Expected result**: nothing ever crashes because of an LLM problem in this node.

## Exit checklist

- [ ] Scenario 1 confirms the summary is grounded in real data
- [ ] Scenario 2 confirms the previous-month comparison is included only when real data exists
- [ ] Scenario 3 confirms LLM failures and blank responses never raise
- [ ] No test depends on a real terminal, Ollama running, or real financial data
