# Data Model: Revisão Humana de Transações

## Transação (campos alterados por esta feature)

Nenhuma coluna nova em `transactions`. Esta feature só atualiza `category`, `subcategory` e `confidence` — os
mesmos campos que a feature 002 já preenche — via decisão humana em vez de memória/LLM.

| Campo | Regra nesta feature |
|---|---|
| `category`/`subcategory` | Mantidos (aceitar) ou substituídos pela entrada validada do usuário (corrigir) |
| `confidence` | Sempre vira `"high"` ao final da decisão — nunca fica `medium`/`low` depois de revisado |

## Item pendente de revisão (conceito, não é tabela)

Query, não entidade: `SELECT ... FROM transactions WHERE month_ref = ? AND confidence != 'high' ORDER BY date`.
Ver research.md — por que essa única condição já cobre candidatos a transferência.

## GraphState

Estado mínimo que flui entre os nodes do `StateGraph`. Deliberadamente pequeno: os nodes já buscam e persistem
transações direto no banco (padrão estabelecido nas features 001/002), então o estado do grafo não carrega a lista
de transações — só o necessário para os nodes saberem o que processar.

| Campo | Tipo | Descrição |
|---|---|---|
| `source_files` | list[str] | caminhos dos extratos a importar (entrada do `detect_and_parse`) |
| `month_ref` | str | mês sendo processado (ex.: `"2026-08"`) — também usado como `thread_id` do checkpointer |
| `db_path` | str | caminho do banco SQLite compartilhado por todos os nodes |

## Payload de interrupção (formato do `interrupt()`)

Não é uma entidade persistida — é a estrutura de dados trocada entre `nodes/review.py` e quem estiver dirigindo o
grafo (a CLI, ou um teste).

| Campo | Descrição |
|---|---|
| `transaction` | data, descrição, valor, conta, categoria/subcategoria/confiança sugeridas |
| `is_transfer_candidate` | `bool` — muda as respostas válidas esperadas (`confirmar`/categoria vs. `aceitar`/categoria) |
| `error` | opcional — presente quando o node está re-perguntando pelo mesmo item após uma resposta inválida |

## Resposta do usuário (`Command(resume=...)`)

Texto livre, no mesmo formato usado pelo `llm_categorizer` da feature 002:

| Entrada | Efeito |
|---|---|
| `"aceitar"` | mantém a categoria/subcategoria sugeridas (só para itens que não são candidatos a transferência) |
| `"confirmar"` | mantém `"Transferência interna"` (só para candidatos a transferência) |
| `"categoria\|subcategoria"` | substitui a sugestão pela categoria/subcategoria informadas (subcategoria opcional) |
| qualquer outra coisa, ou categoria fora da taxonomia | inválido — o node re-interrompe pelo mesmo item com `error` preenchido |
