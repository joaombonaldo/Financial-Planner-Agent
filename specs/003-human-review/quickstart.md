# Quickstart: Validando a Revisão Humana

Guia de validação end-to-end desta feature. Sem código de implementação — apenas os passos para provar que o
comportamento da spec funciona.

## Pré-requisitos

- Ambiente `backend/` com dependências resolvidas (`uv sync`), incluindo `langgraph-checkpoint-sqlite`
- Fixtures sintéticas em `backend/tests/fixtures/review/` (transações com `confidence` variada, incluindo pelo
  menos um candidato a transferência)
- Nos testes automatizados, o grafo é dirigido programaticamente (sem terminal real) — ver research.md

## Cenário 1 — Revisar e corrigir confiança média/baixa (User Story 1)

1. Popular o banco com transações `confidence = medium` e `confidence = low` para um mês.
2. Invocar o grafo para esse mês; capturar o payload do primeiro `interrupt()`.
3. Responder `"aceitar"` para o item de confiança média; verificar que a transação mantém a categoria sugerida
   com `confidence = high`.
4. Responder com uma categoria diferente (`"Alimentação|Mercado"`) para o item de confiança baixa; verificar que
   a transação recebe essa categoria com `confidence = high`.
5. Rodar o grafo para um mês onde todas as transações já são `confidence = high`; verificar que ele termina sem
   nenhum `interrupt()`.

**Resultado esperado**: toda transação pendente termina revisada e com `confidence = high`; um mês sem pendências
não interrompe.

## Cenário 2 — Confirmar ou rejeitar transferência (User Story 2)

1. Popular o banco com uma transação `category = "Transferência interna"`, `confidence = medium`.
2. Invocar o grafo; responder `"confirmar"` — verificar que a categoria permanece "Transferência interna" com
   `confidence = high`.
3. Repetir com outra transação equivalente, respondendo com uma categoria diferente (ex.:
   `"Alimentação|Restaurante/Delivery"`) — verificar que ela substitui "Transferência interna" pela categoria
   informada, com `confidence = high`.

**Resultado esperado**: nenhum candidato a transferência fica sem decisão explícita.

## Cenário 3 — Retomar sessão interrompida (User Story 3)

1. Popular o banco com 3 transações pendentes.
2. Invocar o grafo, responder ao primeiro `interrupt()`, e então parar de avançar o grafo (simulando uma
   interrupção de processo — não chamar `.stream()`/`.invoke()` de novo ainda).
3. Verificar diretamente no banco que a primeira decisão já está persistida (`confidence = high`), mesmo sem o
   grafo ter terminado.
4. Invocar o grafo de novo com o mesmo `thread_id` (retomando via checkpointer); verificar que o primeiro item
   não é apresentado de novo — o próximo `interrupt()` já é o segundo item pendente.

**Resultado esperado**: nenhuma decisão já tomada é perdida ou repetida ao retomar.

## Checklist de saída

- [ ] Cenário 1 confirma aceitar/corrigir e o caso "nada pendente, sem interrupção"
- [ ] Cenário 2 confirma confirmar/rejeitar transferência
- [ ] Cenário 3 confirma que retomar não perde nem repete decisões
- [ ] Nenhum teste depende de terminal real nem de dado financeiro real
