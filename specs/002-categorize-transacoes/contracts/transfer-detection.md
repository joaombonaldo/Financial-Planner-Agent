# Contract: Detecção de Transferência

## `categorization/transfer_detection.py`

**Entrada**: uma transação candidata + a lista de todas as outras transações já importadas no mesmo lote mensal
(de todas as contas conhecidas do usuário).

**Saída**: `bool` (é candidata a transferência) — ou, na integração com o node, diretamente a atribuição
`category = "Transferência interna"`, `confidence = "medium"` quando `True`.

**Garantias que o contrato exige**:
- Só considera transações de **contas diferentes** da transação avaliada (nunca compara uma transação com outra
  da mesma conta).
- Exige padrão de transferência na descrição (`PIX`, `TED` ou `DOC`, case-insensitive) **e** valor espelhado
  (mesmo valor absoluto, `type` oposto) em outra conta, com `date` dentro de uma janela de ±2 dias — as duas
  condições são obrigatórias, não bastam isoladamente.
- Nunca exclui a transação do total nem marca como confirmada — apenas sinaliza a sugestão (FR-008).

## Uso pelo node `categorize`

Avaliada antes de `merchant_memory.py` e antes de `llm_categorizer.py` (ver research.md — ordem de avaliação).
