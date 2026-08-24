# Contract: LLM Categorizer

Interface interna entre `nodes/categorize.py` e a camada de LLM. Consumida apenas pelo node — nenhum outro módulo
chama `llm/client.py` diretamente (Princípio II).

## `llm/client.py`

**Responsabilidade**: único ponto de criação do client de chat model (`init_chat_model`), configurado via
`OLLAMA_MODEL`/`OLLAMA_BASE_URL`. Não conhece taxonomia nem regras de negócio — só sabe conversar com um LLM.

## `categorization/llm_categorizer.py`

**Entrada**: descrição da transação (`description_raw`) + taxonomia carregada (`categorization/taxonomy.py`).

**Saída**: `(category: str, subcategory: str | None, confidence: Literal["medium", "low"])`.

**Garantias que o contrato exige**:
- Nunca retorna `confidence = "high"` — reservado exclusivamente para matches de merchant memory (FR-006).
- Sempre retorna uma categoria pertencente à taxonomia configurada — se a resposta bruta do LLM não corresponder
  a nenhuma entrada válida, o módulo já aplica o fallback (`"Outros"`, `confidence = "low"`) antes de retornar;
  quem chama nunca precisa validar a taxonomia de novo.
- É a única função desta feature que efetivamente invoca `llm/client.py` — testável isoladamente com um dublê no
  lugar do client real (constituição — "grafo testável com LLM mockado").

## Uso pelo node `categorize`

`nodes/categorize.py` só chama esta função quando a transação não foi resolvida por `merchant_memory.py` nem por
`transfer_detection.py` (ver research.md — ordem de avaliação). O node nunca importa `llm/client.py` diretamente.
