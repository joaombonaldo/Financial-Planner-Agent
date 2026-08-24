# Feature Specification: Categorização de Transações

**Feature Branch**: `002-categorize-transacoes`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Categorização automática de transações (node `categorize` do grafo): usa memória de
merchants já confirmados para categorizar com alta confiança sem LLM; chama o LLM apenas para casos novos ou
ambíguos, retornando confiança categórica (high/medium/low); sinaliza candidatos a transferência entre contas
próprias sem excluí-los automaticamente do total. Consome a saída da feature de ingestão (001) e prepara o
resultado para a revisão humana (feature futura)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Categorizar automaticamente merchants já conhecidos (Priority: P1)

Como usuário, quero que transações de estabelecimentos que já categorizei em meses anteriores sejam categorizadas
automaticamente com alta confiança, sem chamar o LLM nem exigir minha revisão, para não repetir o mesmo trabalho
manual todo mês.

**Why this priority**: É o que torna o processo mensal sustentável — sem isso, toda transação exigiria revisão
humana ou chamada de LLM, todo mês, para sempre.

**Independent Test**: Pode ser testado fornecendo uma transação cujo merchant já tem mapeamento confirmado em
memória e verificando que ela recebe a categoria correta com `confidence = high`, sem nenhuma chamada ao LLM.

**Acceptance Scenarios**:

1. **Given** uma transação cuja descrição corresponde a um merchant já confirmado em memória (ex.: "Uber" →
   Transporte/Uber-99), **When** a transação é categorizada, **Then** ela recebe a categoria e subcategoria
   mapeadas, com `confidence = high`, sem chamada ao LLM.
2. **Given** um mês sem nenhum merchant confirmado em memória (primeira execução do sistema), **When** as
   transações são categorizadas, **Then** nenhuma transação recebe `confidence = high` só por estar na memória —
   todas passam pelo fluxo de categorização via LLM (User Story 2).

---

### User Story 2 - Categorizar transações novas ou ambíguas via LLM (Priority: P1)

Como usuário, quero que transações de merchants que eu nunca vi antes sejam categorizadas automaticamente por um
LLM, usando a taxonomia de categorias definida, com um nível de confiança explícito, para que eu saiba quais
merecem minha atenção na revisão.

**Why this priority**: Junto com a User Story 1, é o que entrega o valor central da feature — sem isso, toda
transação nova ficaria sem categoria alguma.

**Independent Test**: Pode ser testado fornecendo uma transação cujo merchant não está na memória e verificando que
o LLM é chamado e retorna uma categoria válida da taxonomia com um nível de confiança categórico.

**Acceptance Scenarios**:

1. **Given** uma transação cujo merchant não está na memória, **When** ela é categorizada, **Then** o LLM é chamado
   e retorna uma categoria/subcategoria pertencente à taxonomia configurada, com `confidence` igual a `medium` ou
   `low` (nunca `high` — alta confiança só vem de merchant já conhecido, ver User Story 1).
2. **Given** uma resposta do LLM que não corresponde a nenhuma categoria da taxonomia configurada, **When** o
   resultado é processado, **Then** a transação recebe a categoria de fallback "Outros" com `confidence = low`, em
   vez de ficar sem categoria ou quebrar o processamento.
3. **Given** uma transação com descrição genérica insuficiente para categorização confiável (ex.: histórico do
   Bradesco que nunca cita o nome do estabelecimento), **When** ela é categorizada, **Then** ela recebe
   `confidence = medium` ou `low`, nunca `high`.

---

### User Story 3 - Sinalizar candidatos a transferência entre contas próprias (Priority: P2)

Como usuário, quero que transações que parecem ser transferências entre minhas próprias contas (Bradesco ↔ Inter)
sejam sinalizadas como candidatas, sem serem excluídas automaticamente do total de gastos/receitas, para eu
confirmar antes de qualquer exclusão acontecer.

**Why this priority**: Evita tanto o erro de contar uma transferência interna como gasto real quanto o erro maior
de excluir do total algo que não era transferência — por isso a decisão final fica para a revisão humana, não para
esta feature.

**Independent Test**: Pode ser testado fornecendo duas transações espelhadas (mesmo valor, contas diferentes, datas
dentro de uma janela de ±2 dias, padrão de transferência na descrição) e verificando que ambas são sinalizadas como
candidatas a "Transferência interna", permanecendo no total até confirmação posterior.

**Acceptance Scenarios**:

1. **Given** duas transações com valor espelhado (uma de saída em uma conta, uma de entrada em outra conta do
   mesmo usuário) dentro de uma janela de até 2 dias, e com padrão de transferência na descrição (PIX/TED/DOC),
   **When** a categorização roda, **Then** ambas são sugeridas com categoria "Transferência interna", mas
   permanecem contabilizadas no total até serem confirmadas por uma revisão humana (fora do escopo desta feature).
2. **Given** uma transação com padrão de transferência na descrição mas sem um valor espelhado correspondente em
   outra conta dentro da janela de ±2 dias, **When** a categorização roda, **Then** ela não é sinalizada como
   candidata a transferência — segue o fluxo normal de categorização (User Story 1 ou 2).

### Edge Cases

- Merchant memory vazia (primeiro uso do sistema): todas as transações passam pelo fluxo de LLM (User Story 2),
  nenhuma recebe `high` por falta de histórico.
- Descrição de transação sem nome de estabelecimento (ex.: Bradesco "PIX ENVIADO"/"PIX RECEBIDO" genérico): não
  impede a categorização, mas limita a chance de match em memória e tende a resultar em confiança mais baixa.
- Resposta do LLM fora da taxonomia conhecida: cai em "Outros" com `confidence = low`, nunca falha o processamento.
- Duas transações de valor espelhado que coincidem por acaso (não são transferência de fato): ficam sinalizadas
  como candidatas mesmo assim — a decisão final de aceitar ou rejeitar a sugestão é da revisão humana, não desta
  feature.
- Transação de parcela de cartão de crédito: recebe categoria normal da compra (ex.: "Vestuário"); a lógica de
  parcelamento em si (tabela `installments`) é responsabilidade de uma feature futura, não desta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST, para cada transação, verificar se o merchant (derivado da descrição) já possui um
  mapeamento confirmado em memória antes de considerar qualquer outra fonte de categorização.
- **FR-002**: Quando o merchant já está confirmado em memória, o sistema MUST atribuir a categoria e subcategoria
  mapeadas com `confidence = high`, sem chamar o LLM.
- **FR-003**: Quando o merchant não está confirmado em memória, o sistema MUST chamar o LLM para sugerir uma
  categoria e subcategoria a partir da taxonomia configurada.
- **FR-004**: O sistema MUST manter a taxonomia de categorias/subcategorias como configuração extensível (não
  fixa no código), incluindo as categorias "Outros" e "Transferência interna" descritas no Anexo A do BRD.
- **FR-005**: Quando a resposta do LLM não corresponder a nenhuma categoria da taxonomia configurada, o sistema
  MUST atribuir a categoria de fallback "Outros" com `confidence = low`, em vez de falhar ou deixar a transação
  sem categoria.
- **FR-006**: `confidence = high` MUST ocorrer apenas via merchant já confirmado em memória (FR-002); toda
  categorização vinda do LLM MUST resultar em `confidence` igual a `medium` ou `low`.
- **FR-007**: O sistema MUST identificar transações candidatas a transferência entre contas próprias: padrão de
  transferência na descrição (PIX/TED/DOC) combinado com um valor espelhado em outra conta do usuário dentro de
  uma janela de até 2 dias.
- **FR-008**: Transações candidatas a transferência MUST ser sugeridas com categoria "Transferência interna", mas
  MUST NOT ser excluídas do total de gastos/receitas nem confirmadas automaticamente por esta feature — a
  confirmação final é responsabilidade da revisão humana (fora do escopo desta feature).
- **FR-009**: A confiança de categorização MUST sempre ser representada de forma categórica (`high`/`medium`/
  `low`), nunca como um valor numérico.
- **FR-010**: O sistema MUST persistir a categoria, subcategoria e confiança atribuídas a cada transação, prontas
  para consumo pela etapa de revisão humana.
- **FR-011**: Esta feature MUST NOT gravar novas confirmações na memória de merchants — isso é responsabilidade de
  uma feature futura (`update_memory`), acionada após a revisão humana.

### Key Entities *(include if feature involves data)*

- **Mapeamento de merchant**: associação entre um merchant (derivado da descrição da transação) e uma categoria/
  subcategoria já confirmada em execuções anteriores. Esta feature apenas lê esse mapeamento; gravar novas
  confirmações é responsabilidade de uma feature futura.
- **Taxonomia de categorias**: lista configurável de categorias e subcategorias (Anexo A do BRD), incluindo os
  fallbacks "Outros" (baixa confiança) e "Transferência interna" (candidatos a transferência).
- **Transação (estendida)**: a transação normalizada produzida pela feature de ingestão (001), agora com
  `category`, `subcategory` e `confidence` preenchidos por esta feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Transações de merchants já confirmados em meses anteriores são categorizadas automaticamente com
  alta confiança, sem exigir nenhuma ação do usuário nem chamada ao LLM.
- **SC-002**: 100% das transações processadas terminam com uma categoria válida da taxonomia — nenhuma transação
  fica sem categoria, mesmo nos casos de resposta inesperada do LLM.
- **SC-003**: 100% das transações candidatas a transferência são sinalizadas para confirmação, e nenhuma é
  excluída do total de gastos/receitas por esta feature.
- **SC-004**: 100% das transações categorizadas têm um valor de confiança dentre `high`/`medium`/`low` — nenhum
  valor numérico ou ausente.
- **SC-005**: Nenhuma transação recebe `confidence = high` sem ter vindo de um merchant já confirmado em memória.

## Assumptions

- O merchant de uma transação é derivado do texto normalizado de `description_raw`; resolução mais sofisticada de
  entidade (fuzzy matching entre variações de nome do mesmo estabelecimento) não é necessária nesta primeira
  versão — pode ser refinada depois, conforme uso real.
- Transações do Bradesco com descrição genérica (ex.: "PIX ENVIADO"/"PIX RECEBIDO", sem nome do favorecido/
  pagador) raramente terão match direto em memória de merchant — tendem a passar pelo fluxo de LLM com confiança
  mais baixa, como já identificado no BRD (seção 6.3).
- A detecção de transferência (FR-007) considera apenas transações já importadas no sistema para as contas
  conhecidas do usuário (Bradesco e Inter) dentro do mesmo lote de processamento mensal — não busca em janelas de
  tempo além de ±2 dias nem em contas fora das já cadastradas.
- O LLM usado é local (Ollama + Qwen2.5, conforme stack do BRD), mas esta spec é agnóstica ao provedor — a escolha
  concreta e a forma de troca ficam para o plano técnico.
- Parcelamentos de cartão de crédito recebem a categoria normal da compra por esta feature; a lógica específica de
  parcelamento (tabela `installments`, rastreio de parcelas pagas/restantes) é responsabilidade de uma feature
  futura.
