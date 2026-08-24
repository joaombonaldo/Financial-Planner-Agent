# Contract: Node `human_review`

## `nodes/review.py`

**Entrada**: `GraphState` (ver data-model.md) — usa `month_ref` e `db_path`.

**Comportamento**:
1. Consulta itens pendentes (`confidence != 'high'`) do mês, direto no banco via `db/repository.py`.
2. Se não houver nenhum, retorna sem chamar `interrupt()` (FR-008 — nunca interrompe à toa).
3. Para cada item pendente, na ordem da consulta:
   a. Chama `interrupt(payload)` com os dados do item.
   b. Valida a resposta recebida (`Command(resume=...)`) contra a taxonomia e contra o tipo de item
      (transferência ou não).
   c. Se inválida, chama `interrupt()` de novo pelo **mesmo** item, com `error` preenchido no payload —
      não avança para o próximo item até obter uma resposta válida.
   d. Se válida, persiste a decisão imediatamente via `db/repository.py` (`confidence = "high"`) e segue para o
      próximo item pendente.

**Garantias que o contrato exige**:
- Nunca persiste uma categoria fora da taxonomia (FR-009/SC-005).
- Nunca deixa um candidato a transferência sem decisão explícita (FR-004/SC-004).
- Uma retomada após interrupção de processo nunca reapresenta um item já decidido (FR-007) — garantido pela
  combinação de consulta sempre fresca ao banco + replay do checkpointer (ver research.md).
- Não escreve em `merchant_memory` — fora de escopo (FR-010).

## `graph.py`

**Responsabilidade**: montar e compilar o `StateGraph` (`detect_and_parse` → `categorize` → `human_review`) com
`SqliteSaver` como checkpointer, usando o mesmo arquivo de banco de `db/repository.py`. Expõe uma função
`build_graph(db_path) -> CompiledGraph` — quem chama (CLI ou teste) é responsável por invocar/retomar via
`thread_id = month_ref`.

## `interface/cli.py`

**Responsabilidade**: dirigir o loop de interrupção — invoca o grafo, quando recebe um `interrupt()` formata o
payload pro terminal, lê uma linha de `stdin`, e resume o grafo com essa resposta, repetindo até o grafo terminar.
Não conhece taxonomia nem regras de negócio — apenas exibe o que o node manda e devolve texto (ver research.md).
