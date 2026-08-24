# financial-planner (backend)

## Variáveis de ambiente

Usadas pela feature de categorização (`nodes/categorize.py` → `llm/client.py`) para configurar o LLM local:

| Variável | Default | Descrição |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5` | Modelo servido pelo Ollama local |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint do servidor Ollama |

Nenhuma delas é necessária para rodar a suíte de testes — o LLM é sempre mockado nos testes automatizados
(`tests/fixtures/categorization/llm_double.py`), nunca depende de Ollama rodando.

## Rodando uma revisão mensal via CLI

```sh
uv run python -m financial_planner.interface.cli 2026-08 /caminho/para/financial-planner.db extrato-bradesco.csv extrato-inter.csv
```

Importa os extratos, categoriza, e entra num loop de revisão no terminal para toda transação com
`confidence != high` (inclui candidatos a transferência). Interromper o processo (Ctrl+C) não perde as decisões já
tomadas — rodar o mesmo comando de novo retoma exatamente do próximo item pendente, graças ao checkpointer do
LangGraph (`thread_id = month_ref`).

## Como os testes dirigem o grafo sem terminal real

`nodes/review.py` usa `interrupt()` do LangGraph — não dá pra chamá-lo fora de uma execução de grafo. Os testes
(`tests/test_review.py`) compilam um grafo mínimo (`tests/fixtures/review/graph_harness.py`, só com o node
`human_review`, sem `detect_and_parse`/`categorize`) e dirigem o loop de interrupção programaticamente: invocam o
grafo, capturam o payload de cada `interrupt()`, respondem com `Command(resume=...)`, repetindo até o grafo
terminar. Nenhum teste depende de `input()` real nem de Ollama rodando.

## Rodando os testes

```sh
uv run pytest
```

### Se o import de `financial_planner` falhar com `ModuleNotFoundError`

Em alguns ambientes (observado em sandbox macOS), o `.pth` que o `uv` gera para instalar
o pacote local em modo editável (`.venv/lib/python3.12/site-packages/financial_planner.pth`)
é criado com a flag `UF_HIDDEN` do macOS, e o Python 3.12 ignora silenciosamente `.pth`
ocultos — o pacote fica invisível para o interpretador mesmo estando instalado. Sintoma:
`uv run python -c "import financial_planner"` funciona logo após `uv sync`, mas volta a
falhar na próxima chamada de `uv run` (ele resincroniza e recria o `.pth` já oculto).

Workaround:

```sh
chflags nohidden .venv/lib/python3.12/site-packages/financial_planner.pth
uv run --no-sync pytest
```

`--no-sync` evita que o `uv` regenere o `.pth` (e a flag oculta) antes de cada execução.
