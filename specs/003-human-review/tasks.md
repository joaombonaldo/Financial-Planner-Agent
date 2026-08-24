---

description: "Task list template for feature implementation"
---

# Tasks: Revisão Humana de Transações

**Input**: Design documents from `/specs/003-human-review/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/review-node.md, quickstart.md

**Tests**: Incluídas — a constituição exige que o grafo seja testável de forma determinística; aqui isso significa
dirigir o loop de `interrupt()`/`Command(resume=...)` programaticamente, sem terminal real.

**Organization**: Tasks agrupadas por user story (US1/US2/US3, conforme spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tasks incompletas)
- **[Story]**: a qual user story a task pertence (US1, US2, US3)

## Path Conventions

Projeto único em `backend/`, conforme `plan.md`. Todos os caminhos abaixo são relativos à raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 [P] Adicionar `langgraph-checkpoint-sqlite` como dependência (`uv add langgraph-checkpoint-sqlite` em
      `backend/`)
- [X] T002 [P] Criar `backend/src/financial_planner/interface/__init__.py`
- [X] T003 [P] Criar `backend/tests/fixtures/review/`

**Checkpoint**: dependência do checkpointer resolvida, estrutura de pastas pronta.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: bloqueia todas as user stories abaixo.

- [X] T004 Definir `GraphState` (TypedDict: `source_files`, `month_ref`, `db_path`) em
      `backend/src/financial_planner/graph_state.py`
- [X] T005 Implementar `list_pending_review(conn, month_ref)` (`WHERE month_ref = ? AND confidence != 'high'`) em
      `backend/src/financial_planner/db/repository.py` (ver research.md — por que essa única condição já cobre
      candidatos a transferência)

**Checkpoint**: fundação pronta — as três user stories podem começar.

---

## Phase 3: User Story 1 - Revisar e corrigir confiança média/baixa (Priority: P1) 🎯 MVP

**Goal**: transações `confidence != high` são apresentadas ao usuário via `interrupt()`, uma por vez, e a decisão
(aceitar ou corrigir) é persistida com `confidence = high`.

**Independent Test**: popular o banco com itens de confiança média/baixa, dirigir o grafo respondendo a cada
`interrupt()`, verificar o resultado persistido (Cenário 1 de `quickstart.md`).

### Tests for User Story 1 ⚠️

- [X] T006 [P] [US1] Criar helpers de fixture (transações com `confidence` variada) em
      `backend/tests/fixtures/review/builders.py`
- [X] T007 [P] [US1] Teste: aceitar a sugestão mantém categoria/subcategoria e vira `confidence = high`, em
      `backend/tests/test_review.py::test_review_accept_suggestion` (depende de T006)
- [X] T008 [P] [US1] Teste: corrigir com uma categoria diferente persiste a nova categoria com `confidence = high`,
      em `backend/tests/test_review.py::test_review_correct_with_new_category` (depende de T006)
- [X] T009 [P] [US1] Teste: mês sem nenhuma pendência não interrompe o grafo, em
      `backend/tests/test_review.py::test_review_no_pending_items_never_interrupts`
- [X] T010 [P] [US1] Teste: categoria fora da taxonomia é rejeitada e o mesmo item é perguntado de novo, em
      `backend/tests/test_review.py::test_review_rejects_invalid_category_and_reasks` (depende de T006)

### Implementation for User Story 1

- [X] T011 [US1] Implementar `nodes/review.py`: consulta itens pendentes, laço de `interrupt()` por item, valida
      contra a taxonomia, persiste imediatamente, avança (depende de T004, T005)
- [X] T012 [US1] Implementar `graph.py`: `build_graph(db_path)` — monta o `StateGraph`
      (`detect_and_parse` → `categorize` → `human_review`) com `SqliteSaver` como checkpointer, `thread_id` =
      `month_ref` (depende de T011, T001)

**Checkpoint**: User Story 1 completa e testável de forma independente.

---

## Phase 4: User Story 2 - Confirmar ou rejeitar candidatos a transferência (Priority: P1)

**Goal**: candidatos a transferência (`category = "Transferência interna"`) são confirmados ou substituídos por
uma categoria real — nunca ficam sem decisão.

**Independent Test**: popular o banco com um candidato a transferência, confirmar e rejeitar em execuções
separadas, verificar o resultado (Cenário 2 de `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Criar fixture de candidato a transferência (`category = "Transferência interna"`,
      `confidence = medium`) em `backend/tests/fixtures/review/builders.py`
- [X] T014 [P] [US2] Teste: responder `"confirmar"` mantém "Transferência interna" com `confidence = high`, em
      `backend/tests/test_review.py::test_review_confirm_transfer` (depende de T013)
- [X] T015 [P] [US2] Teste: responder com uma categoria substitui "Transferência interna" pela categoria
      informada, com `confidence = high`, em
      `backend/tests/test_review.py::test_review_reject_transfer_with_new_category` (depende de T013)

### Implementation for User Story 2

- [X] T016 [US2] Estender `nodes/review.py` para reconhecer `"confirmar"` como resposta válida apenas quando o
      item é candidato a transferência, e para tratar qualquer resposta de categoria como rejeição da sugestão
      (depende de T011)

**Checkpoint**: User Story 1 e 2 funcionam juntas — todo item pendente (transferência ou não) sempre termina
decidido.

---

## Phase 5: User Story 3 - Retomar sessão interrompida sem perder progresso (Priority: P2)

**Goal**: interromper o processo no meio de uma revisão e retomar depois não perde nem repete decisões.

**Independent Test**: decidir parte dos itens pendentes, "interromper" (não continuar avançando o grafo), verificar
persistência parcial no banco, retomar com o mesmo `thread_id` e verificar que só os itens restantes aparecem
(Cenário 3 de `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T017 [P] [US3] Teste: decidir 1 de 3 itens, "parar", verificar no banco que a decisão já está persistida
      antes do grafo terminar, em
      `backend/tests/test_review.py::test_review_partial_session_persists_immediately`
- [X] T018 [P] [US3] Teste: retomar com o mesmo `thread_id` após decidir 1 de 3 itens apresenta o **segundo** item
      em seguida, nunca o primeiro de novo, em
      `backend/tests/test_review.py::test_review_resume_does_not_reask_decided_items`

### Implementation for User Story 3

- [X] T019 [US3] Validar (sem alteração de código esperada — ver research.md) que `list_pending_review` sempre
      consulta o banco diretamente a cada execução do node, nunca cacheia a lista em memória entre chamadas — é
      essa característica que garante a retomada correta junto com o checkpointer. Ajustar `nodes/review.py`
      apenas se os testes de T017/T018 revelarem alguma dependência de estado em memória.

**Checkpoint**: as três user stories funcionam de forma independente e integrada.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 [P] Implementar `interface/cli.py`: loop mínimo que invoca o grafo, formata o payload de cada
      `interrupt()` no terminal, lê uma linha de `stdin`, e resume o grafo com essa resposta — sem conhecer
      taxonomia nem regras de negócio (ver contracts/review-node.md)
- [X] T021 [P] Rodar os cenários de `quickstart.md` manualmente contra transações reais já importadas/categorizadas
      (via features 001/002, dado fora do repositório) usando a CLI de verdade, para validar end-to-end
- [X] T022 Revisar `nodes/review.py` contra o Princípio II da constituição (acesso a banco só via
      `db/repository.py`; `graph.py` e `interface/cli.py` são as únicas peças que legitimamente importam
      `langgraph`/lidam com stdin diretamente)
- [X] T023 [P] Documentar em `backend/README.md` como rodar uma sessão de revisão via CLI e como os testes desta
      feature dirigem o grafo sem terminal real

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as user stories
- **User Stories (Phase 3-5)**: todas dependem do Foundational
  - US2 estende o mesmo `nodes/review.py` criado em US1 (T011 → T016), então na prática é sequencial
    (US1 → US2); US3 não deve exigir mudança de código se o design de "consulta sempre fresca ao banco" segurar —
    é majoritariamente uma fase de verificação
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas

### Within Each User Story

- Testes são escritos antes da implementação e devem falhar primeiro
- Fixtures antes dos testes que as usam
- `graph.py` (T012) depende do node `human_review` já existir, porque é o terceiro node da cadeia

### Parallel Opportunities

- T001, T002, T003 (Setup) em paralelo
- T007, T008, T009, T010 (testes US1) em paralelo entre si, após T006
- T014, T015 (testes US2) em paralelo entre si, após T013
- T017, T018 (testes US3) em paralelo entre si

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Phase 1 (Setup) e Phase 2 (Foundational)
2. Completar Phase 3 (US1) — inclui `graph.py`, a primeira montagem real do `StateGraph`
3. Validar Cenário 1 de `quickstart.md` manualmente
4. Nesse ponto já é possível revisar e corrigir qualquer transação de confiança média/baixa — MVP da feature

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → revisão funcional + grafo montado (MVP)
3. US2 → transferências sempre decididas, nunca esquecidas
4. US3 → retomada segura após interrupção
5. Polish → CLI mínima de verdade + validação end-to-end com dado real

---

## Notes

- Todas as tasks de teste dirigem o grafo programaticamente (sem terminal real) — nenhuma depende de dado
  financeiro real nem de LLM (este node não usa LLM)
- Gravar confirmações em `merchant_memory` continua fora de escopo (feature futura `update_memory`)
- Excluir transferências confirmadas dos totais continua fora de escopo (feature futura `budget_check`)

- **T021 concluída** com o grafo completo (Ollama real) contra os dados reais de Bradesco + Inter, dirigindo o
  loop de `interrupt()`/`Command(resume=...)` programaticamente:
  - 89/89 transações terminaram com `confidence = high` e `category` nunca `NULL`, em ambos os meses cobertos
    pelo extrato (89 transações se distribuem entre `month_ref = "2026-07"` e `"2026-08"`, já que o período do
    export vai de 24/07 a 22/08/2026)
  - **Achado, não é bug de código**: o extrato cobre dois meses civis — rodar o grafo só para `"2026-08"` deixa
    as transações de julho intocadas (sem categoria, sem confiança), já que `categorize`/`human_review` operam
    por `month_ref`. Isso é o comportamento correto e esperado (alinhado ao BRD — cada mês é processado com seu
    próprio `thread_id`), mas é fácil esquecer ao validar manualmente um extrato que cruza a virada do mês; uma
    feature futura de CLI mais completa pode valer a pena detectar e processar automaticamente todos os
    `month_ref` presentes num lote de arquivos, em vez de exigir um mês por chamada
  - Confirmado com Python puro (não só a query SQL) que 0 transações têm `confidence != 'high'` — a query
    `list_pending_review` (`WHERE confidence != 'high'`) depende do invariante "todo `confidence` é preenchido
    antes de `human_review` rodar" (garantido pela sequência do grafo); `confidence IS NULL` nunca deveria
    aparecer em uso normal, e de fato não apareceu
- Commitar após cada task ou grupo lógico de tasks
