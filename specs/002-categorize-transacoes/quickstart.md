# Quickstart: Validando a Categorização de Transações

Guia de validação end-to-end desta feature. Sem código de implementação — apenas os passos para provar que o
comportamento da spec funciona.

## Pré-requisitos

- Ambiente `backend/` com dependências resolvidas (`uv sync`)
- `config/categories.yaml` com a taxonomia inicial (Anexo A do BRD)
- Fixtures sintéticas em `backend/tests/fixtures/categorization/` (transações + estado de `merchant_memory`)
- LLM sempre mockado nos testes automatizados — nenhum cenário abaixo depende de Ollama rodando

## Cenário 1 — Merchant já confirmado (User Story 1)

1. Popular `merchant_memory` com um mapeamento conhecido (ex.: "uber" → Transporte/Uber-99).
2. Rodar a categorização sobre uma transação cuja descrição normalizada bate com esse merchant.
3. Verificar que a transação recebe a categoria/subcategoria mapeadas com `confidence = high`, e que o dublê do
   LLM não foi chamado nenhuma vez.

**Resultado esperado**: categorização automática sem LLM para merchants já conhecidos.

## Cenário 2 — Merchant novo, via LLM (User Story 2)

1. Rodar a categorização sobre uma transação cujo merchant não está em `merchant_memory`.
2. Configurar o dublê do LLM para retornar uma categoria válida da taxonomia.
3. Verificar que a transação recebe essa categoria com `confidence` `medium` ou `low` (nunca `high`).
4. Repetir configurando o dublê para retornar uma categoria **fora** da taxonomia.
5. Verificar que a transação recebe `category = "Outros"`, `confidence = low`.

**Resultado esperado**: toda transação termina com uma categoria válida, mesmo com resposta inesperada do LLM.

## Cenário 3 — Candidato a transferência (User Story 3)

1. Criar duas transações sintéticas: uma de saída em uma conta ("PIX ENVIADO", valor X), uma de entrada em outra
   conta ("PIX RECEBIDO", mesmo valor X), com datas a até 2 dias de distância.
2. Rodar a categorização sobre o lote contendo as duas.
3. Verificar que ambas recebem `category = "Transferência interna"`, `confidence = medium`, e que **nenhuma** foi
   removida do total (a lista de transações retornada continua com as duas).
4. Repetir com uma transação de padrão de transferência sem par espelhado dentro da janela.
5. Verificar que essa transação segue o fluxo normal (Cenário 1 ou 2), sem virar "Transferência interna".

**Resultado esperado**: transferências são sinalizadas, nunca aplicadas ou excluídas automaticamente.

## Checklist de saída

- [ ] Cenário 1 confirma `confidence = high` sem chamada ao LLM
- [ ] Cenário 2 confirma fallback "Outros"/`low` para resposta fora da taxonomia
- [ ] Cenário 3 confirma sinalização de transferência sem exclusão do total
- [ ] Nenhum teste depende de rede, Ollama real ou dado financeiro real
