# financial-planner (backend)

## Environment variables

Used by the categorization feature (`nodes/categorize.py` → `llm/client.py`) to configure the local LLM:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5` | Model served by local Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server endpoint |

None of them are required to run the test suite — the LLM is always mocked in automated tests
(`tests/fixtures/categorization/llm_double.py`), never depends on Ollama running.

## Running a monthly review via CLI

```sh
uv run python -m financial_planner.interface.cli 2026-08 /path/to/financial-planner.db bradesco-statement.csv inter-statement.csv
```

Imports the statements, categorizes them, and enters a terminal review loop for every transaction with
`confidence != high` (including transfer candidates). Interrupting the process (Ctrl+C) doesn't lose decisions
already made — running the same command again resumes exactly from the next pending item, thanks to the LangGraph
checkpointer (`thread_id = month_ref`). Once the month has nothing left pending, the graph automatically persists
every confirmed category into `merchant_memory` (`nodes/memory.py`) — that same merchant auto-categorizes with
`confidence = high` the next time it shows up, in any future month.

## How the tests drive the graph without a real terminal

`nodes/review.py` uses LangGraph's `interrupt()` — it can't be called outside a graph run. The tests
(`tests/test_review.py`) compile a minimal graph (`tests/fixtures/review/graph_harness.py`, with only the
`human_review` node, no `detect_and_parse`/`categorize`) and drive the interruption loop programmatically: invoke
the graph, capture each `interrupt()` payload, respond with `Command(resume=...)`, repeating until the graph
finishes. No test depends on real `input()` or on Ollama running.

## Running the tests

```sh
uv run pytest
```

### If importing `financial_planner` fails with `ModuleNotFoundError`

In some environments (observed in a macOS sandbox), the `.pth` file `uv` generates to install the local
package in editable mode (`.venv/lib/python3.12/site-packages/financial_planner.pth`) gets created with
macOS's `UF_HIDDEN` flag, and Python 3.12 silently ignores hidden `.pth` files — the package becomes invisible
to the interpreter even though it's installed. Symptom: `uv run python -c "import financial_planner"` works
right after `uv sync`, but fails again on the next `uv run` call (it re-syncs and recreates the already-hidden
`.pth`).

Workaround:

```sh
chflags nohidden .venv/lib/python3.12/site-packages/financial_planner.pth
uv run --no-sync pytest
```

`--no-sync` prevents `uv` from regenerating the `.pth` (and the hidden flag) before each run.
