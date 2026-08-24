# Feature Specification: Revisão Humana de Transações

**Feature Branch**: `003-human-review`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Revisão humana (node `human_review` do grafo): interrompe o processamento sempre que
houver transações de confiança média/baixa ou candidatas a transferência entre contas próprias, apresenta cada uma
para o usuário confirmar ou corrigir, e persiste a decisão imediatamente — sem perder progresso se a sessão for
interrompida no meio. Consome a saída da feature de categorização (002); não usa LLM. Inclui a montagem do grafo
(LangGraph `StateGraph` com `interrupt()`) que liga `detect_and_parse` → `categorize` → `human_review`, já que este
é o primeiro node cuja razão de existir depende de rodar dentro de um grafo compilado."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Revisar e corrigir transações de confiança média/baixa (Priority: P1)

Como usuário, quero ver cada transação que o sistema categorizou com confiança média ou baixa, com a sugestão já
preenchida, e poder aceitar essa sugestão ou corrigi-la, para garantir que meus dados financeiros fiquem corretos
antes de qualquer relatório ser gerado.

**Why this priority**: É a razão de existir do node — sem isso, transações de baixa confiança ficariam
permanentemente incorretas, e a promessa central do projeto (revisão humana obrigatória para decisões sensíveis)
não se cumpre.

**Independent Test**: Pode ser testado fornecendo um mês com transações de confiança média/baixa e simulando
respostas do usuário (aceitar / corrigir), verificando que cada transação termina com a categoria certa e
`confidence = high`.

**Acceptance Scenarios**:

1. **Given** uma transação com `confidence = medium` e uma categoria sugerida, **When** o usuário aceita a
   sugestão, **Then** a transação mantém a categoria/subcategoria sugeridas e passa a ter `confidence = high`.
2. **Given** uma transação com `confidence = low`, **When** o usuário informa uma categoria diferente da sugerida,
   **Then** a transação recebe a categoria/subcategoria informadas pelo usuário, com `confidence = high`.
3. **Given** um mês em que todas as transações já têm `confidence = high` (nenhuma pendência), **When** o
   processamento chega neste node, **Then** o grafo segue adiante automaticamente, sem interromper para revisão.

---

### User Story 2 - Confirmar ou rejeitar candidatos a transferência (Priority: P1)

Como usuário, quero confirmar ou rejeitar cada transação sinalizada como candidata a transferência entre minhas
próprias contas, para controlar exatamente quais movimentações são tratadas como transferência interna e quais
são gasto/receita real.

**Why this priority**: A sugestão de transferência nunca pode virar decisão automática (BRD 5.2) — sem esta user
story, candidatos a transferência ficariam presos permanentemente no estado de "sugestão", nunca confirmados.

**Independent Test**: Pode ser testado fornecendo uma transação com `category = "Transferência interna"` (sugerida
pela categorização) e simulando confirmação e rejeição, verificando o resultado em cada caso.

**Acceptance Scenarios**:

1. **Given** uma transação sugerida como "Transferência interna", **When** o usuário confirma, **Then** ela
   permanece com essa categoria e passa a ter `confidence = high`.
2. **Given** uma transação sugerida como "Transferência interna", **When** o usuário rejeita e informa a categoria
   real, **Then** ela recebe a categoria informada (nunca permanece como "Transferência interna" sem confirmação
   nem fica sem categoria), com `confidence = high`.

---

### User Story 3 - Retomar uma revisão interrompida sem perder progresso (Priority: P2)

Como usuário, quero poder interromper uma sessão de revisão no meio (fechar o terminal, por exemplo) e retomar
depois, sem perder as decisões que já tomei nem repetir revisões já feitas.

**Why this priority**: Revisão de um mês inteiro pode ter dezenas de itens — sem essa garantia, uma interrupção
acidental obrigaria a refazer tudo, o que na prática desencorajaria o uso da revisão.

**Independent Test**: Pode ser testado revisando parte dos itens pendentes, simulando uma interrupção, e
retomando o processamento — verificando que os itens já decididos não são apresentados de novo e permanecem com a
decisão tomada.

**Acceptance Scenarios**:

1. **Given** uma sessão de revisão com 3 itens pendentes, **When** o usuário decide o primeiro item e a sessão é
   interrompida antes do segundo, **Then** o primeiro item permanece com a decisão tomada (persistida
   imediatamente) ao retomar.
2. **Given** uma sessão retomada após interrupção, **When** o processamento continua, **Then** apenas os itens
   ainda não decididos são apresentados ao usuário — nenhum item já decidido é perguntado de novo.

### Edge Cases

- Nenhuma transação pendente de revisão no mês: o node não deve interromper o grafo (User Story 1, cenário 3).
- Usuário informa uma categoria ou subcategoria fora da taxonomia configurada durante uma correção: o sistema
  MUST rejeitar a entrada e pedir novamente, nunca aceitar uma categoria inválida silenciosamente.
- Duas transações formam um par de transferência espelhada (uma sugestão em cada conta): cada uma é revisada
  independentemente — confirmar ou rejeitar uma não decide automaticamente a outra.
- Sessão interrompida sem nenhuma decisão tomada ainda: ao retomar, todos os itens originalmente pendentes
  continuam pendentes, sem duplicação nem perda.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST interromper o processamento do mês sempre que existir pelo menos uma transação com
  `confidence` diferente de `high` ou com `category = "Transferência interna"` ainda não confirmada.
- **FR-002**: Para cada item pendente, o sistema MUST apresentar ao usuário data, descrição, valor, conta e a
  categoria/subcategoria/confiança sugeridas antes de pedir uma decisão.
- **FR-003**: Para itens que não são candidatos a transferência, o usuário MUST poder aceitar a sugestão ou
  informar uma categoria/subcategoria diferente, dentro da taxonomia configurada.
- **FR-004**: Para candidatos a transferência, o usuário MUST poder confirmar (mantém "Transferência interna") ou
  rejeitar e informar a categoria real — nunca ficar sem decisão.
- **FR-005**: Toda transação decidida pelo usuário (aceita ou corrigida) MUST passar a ter `confidence = high`,
  refletindo que uma decisão humana é a fonte de confiança mais alta possível no sistema.
- **FR-006**: Cada decisão MUST ser persistida imediatamente após ser tomada, não só ao final da sessão inteira —
  uma interrupção não pode custar decisões já tomadas.
- **FR-007**: Ao retomar uma sessão interrompida, o sistema MUST apresentar apenas os itens ainda pendentes —
  itens já decididos MUST NOT ser apresentados novamente.
- **FR-008**: Quando não houver nenhum item pendente de revisão para o mês, o sistema MUST seguir o processamento
  automaticamente, sem interromper.
- **FR-009**: O sistema MUST validar qualquer categoria/subcategoria informada manualmente contra a taxonomia
  configurada, rejeitando e pedindo novamente entradas inválidas.
- **FR-010**: Esta feature MUST NOT gravar novas confirmações na memória de merchants — isso continua sendo
  responsabilidade de uma feature futura (`update_memory`), que consome as decisões desta feature.

### Key Entities *(include if feature involves data)*

- **Item pendente de revisão**: não é uma entidade própria — é qualquer transação (da feature 002) com
  `confidence` diferente de `high`, ou com `category = "Transferência interna"` ainda não confirmada pelo usuário.
- **Decisão humana**: a atualização de `category`/`subcategory`/`confidence` de uma transação, aplicada
  diretamente sobre o registro existente — não existe uma tabela separada de "decisões"; a transação em si é a
  fonte de verdade de que foi revisada, pois `confidence = high` só ocorre por memória confirmada (feature 002)
  ou por decisão humana (esta feature).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das transações com confiança média/baixa ou candidatas a transferência de um mês processado
  terminam a revisão com `confidence = high`.
- **SC-002**: Interromper uma sessão de revisão no meio e retomá-la depois não perde nenhuma decisão já tomada.
- **SC-003**: Um mês em que todas as transações já são `confidence = high` é processado sem nenhuma interrupção
  para revisão.
- **SC-004**: Nenhum candidato a transferência permanece com `category = "Transferência interna"` sem confirmação
  explícita do usuário ao final da revisão do mês.
- **SC-005**: Nenhuma categoria ou subcategoria fora da taxonomia configurada é aceita durante uma correção manual.

## Assumptions

- Uma decisão humana (aceitar ou corrigir) sempre resulta em `confidence = high` — não existe um quarto nível de
  confiança "revisado por humano" separado; o valor `high` já comunica "não precisa de mais revisão", seja a
  origem memória de merchant (feature 002) ou decisão humana (esta feature).
- Cada transação é revisada individualmente, mesmo quando faz parte de um par de transferência espelhada — não há
  nesta versão uma interação de "revisar o par de uma vez" (poderia ser um refinamento futuro).
- A interface de interação com o usuário nesta fase é a CLI (conforme stack do BRD, Fase 1); esta feature inclui o
  mínimo de interação necessário para revisar um mês, não um CLI completo com todos os comandos do produto.
- A montagem do grafo (`StateGraph`, `interrupt()`, checkpointer com `thread_id` por mês) é tratada como detalhe
  técnico desta feature (fica no plano de implementação), não como uma feature separada — é a primeira vez que um
  grafo precisa existir de fato, já que os nodes anteriores rodavam como funções independentes.
- Persistir a decisão "imediatamente" (FR-006) significa gravar no banco a cada item decidido, não esperar o fim
  da sessão de revisão inteira — alinhado ao uso do checkpointer do LangGraph para retomar exatamente de onde
  parou.
