# Quickstart: Validando a Ingestão de Extratos

Guia de validação end-to-end desta feature. Não contém código de implementação — apenas os passos para provar que
o comportamento descrito na spec funciona.

## Pré-requisitos

- Ambiente `backend/` com dependências resolvidas (`uv sync`)
- Fixtures de teste em `backend/tests/fixtures/bradesco/` e `backend/tests/fixtures/inter/` (CSVs pequenos e
  sintéticos, cobrindo caso feliz + casos de borda da spec — nunca dados reais)
- Banco SQLite de teste vazio (arquivo temporário, não o banco real do usuário)

## Cenário 1 — Importar um extrato de cada banco (User Story 1)

1. Rodar o processo de ingestão apontando para a fixture do Bradesco.
2. Verificar que o banco detectado é `bradesco`, sem input manual.
3. Verificar que a quantidade de transações retornadas bate com a quantidade de linhas de transação real da
   fixture (contadas manualmente na fixture).
4. Repetir os passos 1-3 para a fixture do Inter, incluindo uma linha com `Descrição` vazia — verificar que a
   transação correspondente usa `Histórico` como descrição.

**Resultado esperado**: transações normalizadas em formato único (mesma estrutura de campos) para os dois bancos,
com valor/data no formato canônico, independente do banco de origem.

## Cenário 2 — Reimportar sem duplicar (User Story 2)

1. Importar a fixture do Bradesco (como no Cenário 1).
2. Importar a mesma fixture novamente.
3. Verificar que `transactions_imported` da segunda execução é `0` e `transactions_skipped_duplicate` bate com o
   total de transações da fixture.

**Resultado esperado**: nenhuma transação duplicada na base após a segunda importação.

## Cenário 3 — Aviso em arquivo não reconhecido ou saldo inconsistente (User Story 3)

1. Rodar o processo de ingestão apontando para um arquivo CSV com estrutura de colunas que não corresponde a
   nenhum dos dois bancos suportados.
2. Verificar que o processo retorna um erro explícito de "banco não reconhecido", sem gerar nenhuma transação.
3. Rodar o processo com uma fixture válida onde a coluna de saldo foi deliberadamente alterada para não reconciliar
   com a soma das transações.
4. Verificar que o `ImportResult` tem `balance_reconciliation = mismatch` e contém uma mensagem em `warnings`
   explicando a divergência — e que as transações reconhecidas corretamente ainda assim são importadas.

**Resultado esperado**: falhas e inconsistências são sempre visíveis ao usuário, nunca silenciosas; um arquivo de
banco não suportado nunca gera transações parciais.

## Checklist de saída

- [ ] Cenário 1 passa para Bradesco e Inter
- [ ] Cenário 2 confirma zero duplicatas em reimportação
- [ ] Cenário 3 confirma erro explícito (banco não reconhecido) e aviso explícito (saldo não reconcilia)
- [ ] Nenhum teste depende de rede, LLM ou dado financeiro real
