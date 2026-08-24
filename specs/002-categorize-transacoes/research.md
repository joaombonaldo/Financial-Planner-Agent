# Research: Categorização de Transações

Nenhum `NEEDS CLARIFICATION` restou no Technical Context — as regras de negócio já estão fixadas no BRD (seções 4,
5.1, 5.2, Anexo A). Este documento registra as decisões técnicas necessárias para implementá-las.

## Ordem de avaliação: transferência vs. memória vs. LLM

- **Decision**: para cada transação, avaliar nesta ordem: (1) padrão de transferência (PIX/TED/DOC) com valor
  espelhado em outra conta dentro de ±2 dias → sugerir "Transferência interna"; (2) merchant já confirmado em
  memória → categoria mapeada com `confidence = high`; (3) caso contrário, chamar o LLM.
- **Rationale**: transferência é uma característica da transação em si (padrão + par espelhado), não do merchant —
  avaliar antes evita que uma eventual entrada genérica de memória (ex.: um "PIX ENVIADO" mapeado por engano no
  passado) mascare uma transferência real. Isso é consistente com o BRD (5.2): a sugestão de transferência é
  sempre do `categorize`, nunca uma aplicação automática de memória.
- **Alternatives considered**: checar memória primeiro — rejeitado porque, como o histórico do Bradesco nunca cita
  o favorecido/pagador (BRD 6.3), um merchant genérico tipo "PIX ENVIADO" poderia acabar em memória com uma
  categoria errada e mascarar transferências reais em execuções futuras.

## Identificação de merchant

- **Decision**: o merchant é o texto normalizado (trim + lowercase) de `description_raw`. Sem normalização
  adicional (remoção de números de documento, fuzzy matching) nesta primeira versão.
- **Rationale**: simplicidade pragmática (Princípio I) — refinar a normalização é um ajuste incremental de baixo
  risco que pode vir depois, guiado por merchants reais observados na revisão mensal.
- **Alternatives considered**: normalização mais agressiva (remover números, stemming) — rejeitada por
  over-engineering nesta fase; documentado como possível melhoria futura no data-model.md.

## Detecção de transferência (padrão + janela)

- **Decision**: padrão de transferência = descrição contém um dos termos `PIX`, `TED`, `DOC` (case-insensitive).
  Valor espelhado = outra transação, em conta diferente do mesmo usuário, com o mesmo valor absoluto e
  `type` oposto (uma `income`, uma `expense`), com `date` dentro de ±2 dias.
- **Rationale**: reflete literalmente a regra do BRD 5.2, e é implementável sem qualquer análise textual adicional
  — importante porque o histórico do Bradesco não permite matching por nome (BRD 6.3).
- **Alternatives considered**: exigir também correspondência textual entre as duas transações — rejeitado porque o
  BRD já identificou que essa correspondência é fraca/inexistente do lado Bradesco.

## Abstração do LLM

- **Decision**: usar `init_chat_model` (LangChain) como ponto único de criação do client de LLM, configurado via
  variáveis de ambiente (`OLLAMA_MODEL`, `OLLAMA_BASE_URL`) já previstas no BRD (seção 7). `llm/client.py` expõe
  uma função `categorize_transaction(description, taxonomy) -> (category, subcategory, confidence)` — o node não
  conhece o provedor concreto.
- **Rationale**: Princípio III da constituição — troca futura para Claude/OpenAI sem alterar `nodes/categorize.py`.
- **Alternatives considered**: chamar o cliente Ollama diretamente — rejeitado, quebraria a trocabilidade exigida
  pela constituição.

## Fallback de categoria fora da taxonomia

- **Decision**: qualquer resposta do LLM que não corresponda exatamente (após normalização simples) a uma
  categoria/subcategoria da taxonomia configurada é substituída por `category = "Outros"`, `confidence = low`.
- **Rationale**: FR-005/SC-002 — nenhuma transação pode ficar sem categoria válida; "Outros" já é a categoria de
  fallback definida no Anexo A do BRD.
- **Alternatives considered**: re-perguntar ao LLM com um prompt mais restrito até obter uma categoria válida —
  rejeitado por complexidade desnecessária nesta fase (Princípio I); pode ser revisitado se a taxa de fallback se
  mostrar alta na prática.

## Estratégia de testes

- **Decision**: LLM sempre mockado (função `categorize_transaction` substituída por um dublê determinístico nos
  testes); fixtures cobrindo merchant já confirmado, merchant novo, resposta do LLM fora da taxonomia, e par de
  transações espelhadas dentro/fora da janela de 2 dias.
- **Rationale**: alinhado à constituição ("Padrões de Teste") e às User Stories da spec.
- **Alternatives considered**: testes de integração contra um Ollama real — rejeitado como dependência de teste;
  fica como validação manual (quickstart.md), não como parte da suíte automatizada.
