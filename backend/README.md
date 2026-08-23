# financial-planner (backend)

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
