# financial-planner (backend)

## Variáveis de ambiente

Usadas pela feature de categorização (`nodes/categorize.py` → `llm/client.py`) para configurar o LLM local:

| Variável | Default | Descrição |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5` | Modelo servido pelo Ollama local |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint do servidor Ollama |

Nenhuma delas é necessária para rodar a suíte de testes — o LLM é sempre mockado nos testes automatizados
(`tests/fixtures/categorization/llm_double.py`), nunca depende de Ollama rodando.

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
