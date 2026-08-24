---

description: "Task list template for feature implementation"
---

# Tasks: Categorização de Transações

**Input**: Design documents from `/specs/002-categorize-transacoes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llm-categorizer.md,
contracts/transfer-detection.md, quickstart.md

**Tests**: Incluídas — a constituição do projeto exige que o grafo seja testável com LLM mockado, sem depender do
Ollama rodando ("Padrões de Teste"), então não são opcionais nesta feature.

**Organization**: Tasks agrupadas por user story (US1/US2/US3, conforme spec.md) para permitir implementação e
teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tasks incompletas)
- **[Story]**: a qual user story a task pertence (US1, US2, US3)

## Path Conventions

Projeto único em `backend/`, conforme `plan.md`. Todos os caminhos abaixo são relativos à raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Criar diretórios `backend/src/financial_planner/categorization/` e
      `backend/src/financial_planner/llm/`, cada um com `__init__.py`
- [X] T002 [P] Criar `backend/tests/fixtures/categorization/`
- [X] T003 [P] Criar `backend/src/financial_planner/config/categories.yaml` com a taxonomia inicial do Anexo A do
      BRD (categorias + subcategorias, incluindo "Outros" e "Transferência interna")

**Checkpoint**: estrutura de pastas e taxonomia base prontas.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: peças compartilhadas pelas três user stories — schema estendido, acesso a merchant memory, taxonomia
validada e abstração de LLM. Nenhuma user story pode ser implementada antes desta fase.

**⚠️ CRITICAL**: bloqueia todas as user stories abaixo.

- [X] T004 Adicionar a tabela `merchant_memory` (`merchant_key` PK, `category`, `subcategory`) a
      `backend/src/financial_planner/db/schema.sql`, usando SQL padrão (Princípio IV)
- [X] T005 Implementar em `backend/src/financial_planner/db/repository.py`: `get_merchant_category(merchant_key)`,
      `update_transaction_category(dedup_hash, category, subcategory, confidence)` e
      `list_transactions_by_month(month_ref)` (depende de T004)
- [X] T006 [P] Implementar carregamento e validação da taxonomia (`config/categories.yaml` → lista de
      categorias/subcategorias válidas, incluindo fallback "Outros") em
      `backend/src/financial_planner/categorization/taxonomy.py` (depende de T003)
- [X] T007 [P] Implementar `backend/src/financial_planner/llm/client.py`: único ponto de criação do chat model via
      `init_chat_model`, configurado por `OLLAMA_MODEL`/`OLLAMA_BASE_URL` (Princípio III)
- [X] T008 Implementar normalização de merchant key (trim + lowercase de `description_raw`) e busca em memória em
      `backend/src/financial_planner/categorization/merchant_memory.py` (depende de T005)

**Checkpoint**: fundação pronta — as três user stories podem começar.

---

## Phase 3: User Story 1 - Categorizar automaticamente merchants já conhecidos (Priority: P1) 🎯 MVP

**Goal**: transações de merchants já confirmados em memória recebem categoria/subcategoria com `confidence = high`,
sem chamar o LLM.

**Independent Test**: popular `merchant_memory` com um mapeamento e verificar que uma transação correspondente é
categorizada corretamente sem nenhuma chamada ao LLM (Cenário 1 de `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T009 [P] [US1] Criar fixtures de transações + estado de `merchant_memory` (merchant conhecido) em
      `backend/tests/fixtures/categorization/`
- [X] T010 [P] [US1] Teste unitário: merchant já confirmado retorna categoria mapeada com `confidence = high`, em
      `backend/tests/test_categorize.py::test_categorize_known_merchant` (depende de T009)
- [X] T011 [P] [US1] Teste unitário: memória vazia (primeira execução) não produz `confidence = high` para nenhuma
      transação, em `backend/tests/test_categorize.py::test_empty_merchant_memory_never_high`

### Implementation for User Story 1

- [X] T012 [US1] Implementar o node `categorize` em `backend/src/financial_planner/nodes/categorize.py`,
      orquestrando: para cada transação, checar `merchant_memory.py` primeiro e atualizar a transação via
      `db/repository.py` quando houver match (depende de T008, T005)

**Checkpoint**: User Story 1 completa e testável de forma independente.

---

## Phase 4: User Story 2 - Categorizar transações novas ou ambíguas via LLM (Priority: P1)

**Goal**: merchants sem match em memória são categorizados via LLM, com fallback para "Outros"/`low` quando a
resposta não pertence à taxonomia.

**Independent Test**: rodar a categorização com o LLM mockado retornando categoria válida e depois inválida,
verificando `confidence` e o fallback (Cenário 2 de `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Criar dublê determinístico do LLM (substitui `llm/client.py` nos testes) em
      `backend/tests/fixtures/categorization/`
- [X] T014 [P] [US2] Teste unitário: merchant novo recebe categoria da taxonomia com `confidence` `medium`/`low`,
      nunca `high`, em `backend/tests/test_categorize.py::test_categorize_new_merchant_via_llm` (depende de T013)
- [X] T015 [P] [US2] Teste unitário: resposta do LLM fora da taxonomia cai em `category = "Outros"`,
      `confidence = low`, em
      `backend/tests/test_categorize.py::test_llm_response_outside_taxonomy_falls_back` (depende de T013)

### Implementation for User Story 2

- [X] T016 [US2] Implementar `backend/src/financial_planner/categorization/llm_categorizer.py`: chama
      `llm/client.py`, valida a resposta contra `taxonomy.py`, aplica fallback "Outros"/`low` quando necessário
      (depende de T006, T007)
- [X] T017 [US2] Estender o node `categorize` para chamar `llm_categorizer.py` quando não há match em memória, em
      `backend/src/financial_planner/nodes/categorize.py` (depende de T012, T016)

**Checkpoint**: User Story 1 e 2 funcionam juntas — toda transação sem match em memória é categorizada via LLM.

---

## Phase 5: User Story 3 - Sinalizar candidatos a transferência entre contas próprias (Priority: P2)

**Goal**: transações com padrão de transferência (PIX/TED/DOC) e valor espelhado em outra conta dentro de ±2 dias
são sugeridas como "Transferência interna", sem serem excluídas do total.

**Independent Test**: fornecer duas transações espelhadas em contas diferentes e verificar que ambas são
sinalizadas, permanecendo na lista de transações (Cenário 3 de `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T018 [P] [US3] Criar fixtures de par de transações espelhadas (dentro e fora da janela de 2 dias) em
      `backend/tests/fixtures/categorization/`
- [X] T019 [P] [US3] Teste unitário: par espelhado dentro da janela é sinalizado como "Transferência interna" com
      `confidence = medium`, em
      `backend/tests/test_categorize.py::test_transfer_pair_detected` (depende de T018)
- [X] T020 [P] [US3] Teste unitário: padrão de transferência sem par espelhado segue o fluxo normal (memória/LLM),
      em `backend/tests/test_categorize.py::test_transfer_pattern_without_mirror_falls_through` (depende de T018)

### Implementation for User Story 3

- [X] T021 [US3] Implementar `backend/src/financial_planner/categorization/transfer_detection.py`: padrão
      PIX/TED/DOC + valor espelhado em conta diferente dentro de ±2 dias (depende de T005)
- [X] T022 [US3] Reordenar o node `categorize` para checar `transfer_detection.py` **antes** de
      `merchant_memory.py`/`llm_categorizer.py` (ver research.md — ordem de avaliação), em
      `backend/src/financial_planner/nodes/categorize.py` (depende de T017, T021)

**Checkpoint**: as três user stories funcionam de forma independente e integrada, na ordem correta
(transferência → memória → LLM).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 [P] Rodar os cenários de `quickstart.md` manualmente contra transações reais já importadas (via feature
      001, dado fora do repositório) para validar end-to-end antes de considerar a feature pronta
- [X] T024 Revisar `nodes/categorize.py` contra o Princípio II da constituição (node não deve importar
      `init_chat_model`/`sqlite3` diretamente — apenas via `llm/client.py` e `db/repository.py`)
- [X] T025 [P] Documentar em `backend/README.md` as variáveis de ambiente necessárias (`OLLAMA_MODEL`,
      `OLLAMA_BASE_URL`) e como rodar os testes desta feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as user stories
- **User Stories (Phase 3-5)**: todas dependem do Foundational
  - US1, US2 e US3 estendem o mesmo node `categorize` (T012 → T017 → T022), então na prática são sequenciais
    (US1 → US2 → US3) apesar de testáveis de forma independente — os módulos de domínio (`merchant_memory.py`,
    `llm_categorizer.py`, `transfer_detection.py`) em si são independentes entre si e podem ser implementados em
    paralelo antes da integração final no node
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas

### Within Each User Story

- Testes são escritos antes da implementação e devem falhar primeiro
- Fixtures antes dos testes que as usam
- Módulos de domínio (`categorization/*.py`) antes da integração no node
- A ordem final de avaliação no node (transferência → memória → LLM) só fica correta após T022 (US3) — durante
  US1/US2 o node ainda não conhece `transfer_detection.py`

### Parallel Opportunities

- T001, T002, T003 (Setup) em paralelo
- T006, T007 (Foundational) em paralelo entre si
- T009 (fixtures) antes de T010/T011 (testes) em paralelo entre si
- T013 (dublê do LLM) antes de T014/T015 em paralelo entre si
- T018 (fixtures) antes de T019/T020 em paralelo entre si

---

## Parallel Example: Foundational

```bash
# Módulos independentes em paralelo:
Task: "Implementar taxonomy.py em backend/src/financial_planner/categorization/taxonomy.py"
Task: "Implementar llm/client.py em backend/src/financial_planner/llm/client.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Phase 1 (Setup) e Phase 2 (Foundational)
2. Completar Phase 3 (US1)
3. Validar Cenário 1 de `quickstart.md` manualmente
4. Nesse ponto, merchants já conhecidos são categorizados automaticamente — MVP da feature

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → categorização automática de merchants conhecidos (MVP)
3. US2 → categorização via LLM para merchants novos, com fallback seguro
4. US3 → sinalização de transferências, sem exclusão automática do total
5. Polish → validação end-to-end com dado real (fora do repo) + revisão de aderência à constituição

---

## Notes

- Todas as tasks de teste usam fixtures sintéticas e o LLM sempre mockado — nenhum dado financeiro real nem
  dependência de Ollama rodando entra na suíte automatizada
- `merchant_memory` só é lida por esta feature; gravar novas confirmações é responsabilidade de uma feature futura
  (`update_memory`)
- A confirmação/rejeição de candidatos a transferência e a persistência de correções de baixa/média confiança
  ficam para a feature futura de revisão humana (`human_review`) — esta feature só sugere, nunca decide
- Commitar após cada task ou grupo lógico de tasks

- **T023 concluída** com Ollama real (Qwen2.5) contra as 89 transações reais importadas pela feature 001
  (Bradesco + Inter, ago/2026; extratos removidos de `extracts/` após a validação):
  - `confidence = high`: 0 (correto — memória de merchant vazia na primeira execução, SC-005 confirmado)
  - `confidence = low` por fallback de taxonomia inválida: 0 — todas as respostas do LLM já vieram em categoria
    válida no formato esperado
  - 100% das transações terminaram com categoria válida (SC-002); nenhuma foi excluída do total (89 antes e
    depois da categorização, SC-003)
  - Qualidade real do LLM é imperfeita (esperado): algumas categorizações ficaram erradas (ex.: farmácia "Raia"
    categorizada como Transporte; rendimento de investimento "RENTAB.INVEST" categorizado como Cartão de
    Crédito em vez de Outros) — mas sempre com `confidence = medium`, nunca `high`, então ficam corretamente
    marcadas para revisão humana (feature futura), validando o design da constituição (Princípio V)
  - Observação para uma iteração futura (não bloqueia esta feature): o padrão de transferência (`PIX`/`TED`/
    `DOC`) é amplo o suficiente para sinalizar como "Transferência interna" uma compra via PIX QR Code cujo
    valor coincide por acaso com outra transação em outra conta dentro da janela de 2 dias — comportamento já
    previsto como edge case aceito na spec (a decisão final é da revisão humana), mas vale reduzir o escopo do
    padrão textual se a taxa de falso positivo se mostrar alta no uso real
