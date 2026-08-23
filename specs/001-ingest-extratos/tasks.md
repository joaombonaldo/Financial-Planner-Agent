---

description: "Task list template for feature implementation"
---

# Tasks: Ingestão de Extratos Bancários

**Input**: Design documents from `/specs/001-ingest-extratos/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/parser-adapter.md, quickstart.md

**Tests**: Incluídas — a constituição do projeto exige testes unitários determinísticos por banco com fixtures
pequenas ("Padrões de Teste"), então não são opcionais nesta feature.

**Organization**: Tasks agrupadas por user story (US1/US2/US3, conforme spec.md) para permitir implementação e
teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tasks incompletas)
- **[Story]**: a qual user story a task pertence (US1, US2, US3)

## Path Conventions

Projeto único em `backend/`, conforme `plan.md`. Todos os caminhos abaixo são relativos à raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: preparar o projeto `backend/` para receber o código desta feature (ainda não existe nada além do
esqueleto criado pelo `uv init`).

- [X] T001 Adicionar `pytest` como dependência de desenvolvimento (`uv add --dev pytest` em `backend/`)
- [X] T002 [P] Criar diretórios `backend/src/financial_planner/nodes/`, `backend/src/financial_planner/parsers/` e
      `backend/src/financial_planner/db/`, cada um com `__init__.py`
- [X] T003 [P] Criar `backend/tests/__init__.py`, `backend/tests/fixtures/bradesco/` e
      `backend/tests/fixtures/inter/`

**Checkpoint**: estrutura de pastas pronta para receber código de domínio e testes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: peças compartilhadas pelas três user stories — schema de transação, acesso a banco e contrato de
parser. Nenhuma user story pode ser implementada antes desta fase.

**⚠️ CRITICAL**: bloqueia todas as user stories abaixo.

- [X] T004 Definir o schema tipado da Transação normalizada e do `ImportResult` (campos desta feature, ver
      `data-model.md`) em `backend/src/financial_planner/state.py`
- [X] T005 Criar `backend/src/financial_planner/db/schema.sql` com a tabela `transactions` (subset usado por esta
      feature: `dedup_hash`, `date`, `description_raw`, `account`, `type`, `amount`, `month_ref`, mais colunas
      nullable `category`/`subcategory`/`confidence`/`installment_id` reservadas para features futuras), usando SQL
      padrão (Princípio IV — persistência portável)
- [X] T006 Implementar `backend/src/financial_planner/db/repository.py` com `transaction_exists(dedup_hash)` e
      `insert_transaction(transaction)`, únicos pontos de acesso ao SQLite (depende de T005)
- [X] T007 [P] Definir o contrato comum de adapter (assinaturas de detecção e parsing, ver
      `contracts/parser-adapter.md`) em `backend/src/financial_planner/parsers/base.py`
- [X] T008 Implementar normalização de valor (formato brasileiro → decimal) e data (`DD/MM/AAAA` → ISO) em
      `backend/src/financial_planner/parsers/normalize.py` (depende de T004)
- [X] T009 Implementar cálculo do hash de deduplicação (SHA-256 sobre `date+description_raw+amount+account`
      normalizados, ver `research.md`) em `backend/src/financial_planner/parsers/dedup.py` (depende de T008)

**Checkpoint**: fundação pronta — as três user stories podem começar.

---

## Phase 3: User Story 1 - Importar extrato de um banco suportado (Priority: P1) 🎯 MVP

**Goal**: dado um CSV do Bradesco ou do Inter, detectar o banco automaticamente e obter as transações do mês em
formato normalizado único.

**Independent Test**: rodar a ingestão contra uma fixture de cada banco e verificar que a saída é uma lista de
transações no schema normalizado (Cenário 1 de `quickstart.md`).

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem falhar antes da implementação.

- [X] T010 [P] [US1] Criar fixtures CSV do Bradesco (caso feliz + BOM + header duplicado "Últimos Lancamentos" +
      rodapé "Total") em `backend/tests/fixtures/bradesco/`
- [X] T011 [P] [US1] Criar fixtures CSV do Inter (caso feliz + `Descrição` vazia + linhas de metadado) em
      `backend/tests/fixtures/inter/`
- [X] T012 [P] [US1] Teste unitário de parsing do Bradesco em
      `backend/tests/test_parsers.py::test_parse_bradesco` (depende de T010)
- [X] T013 [P] [US1] Teste unitário de parsing do Inter, incluindo fallback `Descrição` → `Histórico`, em
      `backend/tests/test_parsers.py::test_parse_inter` (depende de T011)
- [X] T014 [P] [US1] Teste unitário de detecção automática de banco (Bradesco, Inter) em
      `backend/tests/test_parsers.py::test_detect_bank` (depende de T010, T011)

### Implementation for User Story 1

- [X] T015 [US1] Implementar filtro de linha de transação por regex de data (`^\d{2}/\d{2}/\d{4};`) reutilizável
      pelos dois adapters em `backend/src/financial_planner/parsers/base.py` (depende de T007)
- [X] T016 [P] [US1] Implementar adapter do Bradesco (duas colunas Crédito/Débito, `Docto.`) em
      `backend/src/financial_planner/parsers/bradesco.py` (depende de T015, T008, T009)
- [X] T017 [P] [US1] Implementar adapter do Inter (coluna `Valor` com sinal, fallback de descrição) em
      `backend/src/financial_planner/parsers/inter.py` (depende de T015, T008, T009)
- [X] T018 [US1] Implementar detecção automática de banco por estrutura de colunas em
      `backend/src/financial_planner/parsers/detect.py` (depende de T016, T017)
- [X] T019 [US1] Implementar node `detect_and_parse` orquestrando detecção + adapter + persistência via
      `db/repository.py` em `backend/src/financial_planner/nodes/ingest.py` (depende de T006, T018)

**Checkpoint**: User Story 1 completa e testável de forma independente.

---

## Phase 4: User Story 2 - Reimportar um extrato sem duplicar transações (Priority: P2)

**Goal**: reimportar o mesmo arquivo (ou um com período sobreposto) não deve criar transações duplicadas.

**Independent Test**: importar a mesma fixture duas vezes e verificar que a segunda execução não insere nada novo
(Cenário 2 de `quickstart.md`).

### Tests for User Story 2 ⚠️

- [X] T020 [P] [US2] Teste unitário: reimportar a mesma fixture do Bradesco resulta em zero transações novas, em
      `backend/tests/test_parsers.py::test_reimport_skips_duplicates` (depende de T010)
- [X] T021 [P] [US2] Teste unitário: duas transações equivalentes vindas de seções diferentes do mesmo arquivo
      Bradesco (extrato principal + "Últimos Lancamentos") geram apenas uma transação, em
      `backend/tests/test_parsers.py::test_dedup_within_same_file`

### Implementation for User Story 2

- [X] T022 [US2] Estender o node `detect_and_parse` para checar `transaction_exists(dedup_hash)` antes de inserir e
      contabilizar `transactions_imported` / `transactions_skipped_duplicate` no `ImportResult` em
      `backend/src/financial_planner/nodes/ingest.py` (depende de T019, T006, T004)

**Checkpoint**: User Story 1 e 2 funcionam juntas — reimportação é segura.

---

## Phase 5: User Story 3 - Ser avisado quando um arquivo não pôde ser processado corretamente (Priority: P3)

**Goal**: banco não reconhecido ou saldo que não reconcilia gera aviso/erro explícito, nunca falha silenciosa.

**Independent Test**: rodar a ingestão contra um arquivo de banco não suportado e contra uma fixture com saldo
propositalmente incorreto (Cenário 3 de `quickstart.md`).

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Teste unitário: arquivo com layout não reconhecido retorna erro explícito e nenhuma transação,
      em `backend/tests/test_parsers.py::test_detect_unknown_bank`
- [X] T024 [P] [US3] Teste unitário: fixture com saldo alterado propositalmente produz
      `balance_reconciliation = mismatch` e mensagem em `warnings`, mantendo as transações corretas importadas, em
      `backend/tests/test_parsers.py::test_balance_reconciliation_mismatch`

### Implementation for User Story 3

- [X] T025 [US3] Implementar retorno de erro explícito para banco não reconhecido em
      `backend/src/financial_planner/parsers/detect.py` (depende de T018)
- [X] T026 [US3] Implementar checagem de saldo (saldo anterior ± valor da transação == saldo declarado, com
      tolerância de arredondamento) em `backend/src/financial_planner/parsers/reconcile.py` (depende de T015)
- [X] T027 [US3] Integrar erro de banco não reconhecido e avisos de reconciliação ao `ImportResult` retornado pelo
      node `detect_and_parse` em `backend/src/financial_planner/nodes/ingest.py` (depende de T022, T025, T026)

**Checkpoint**: as três user stories funcionam de forma independente e integrada.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Rodar os cenários de `quickstart.md` manualmente contra um extrato real (fora do repositório, via
      `extracts/`) para validar end-to-end antes de considerar a feature pronta
- [X] T029 Revisar `nodes/ingest.py` contra o Princípio II da constituição (node não deve importar `pandas` nem
      `sqlite3` diretamente — apenas via `parsers/` e `db/repository.py`)
- [X] T030 [P] Documentar em `backend/README.md` como rodar os testes desta feature (`uv run pytest`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as user stories
- **User Stories (Phase 3-5)**: todas dependem do Foundational
  - US1 é a base funcional; US2 e US3 estendem o node criado em US1 (T019), então na prática são sequenciais
    (US1 → US2 → US3) apesar de testáveis de forma independente
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas

### Within Each User Story

- Testes são escritos antes da implementação e devem falhar primeiro
- Fixtures antes dos testes que as usam
- `parsers/base.py` (linha de transação) antes dos adapters específicos
- Adapters antes da detecção automática
- Detecção + adapters antes do node de orquestração

### Parallel Opportunities

- T002, T003 (Setup) em paralelo
- T007 (Foundational) em paralelo com T004/T005 (arquivos diferentes)
- T010, T011 (fixtures) em paralelo; T012, T013, T014 (testes) em paralelo entre si após as fixtures
- T016, T017 (adapters Bradesco/Inter) em paralelo entre si
- T020, T021 (testes US2) em paralelo
- T023, T024 (testes US3) em paralelo

---

## Parallel Example: User Story 1

```bash
# Fixtures em paralelo:
Task: "Criar fixtures CSV do Bradesco em backend/tests/fixtures/bradesco/"
Task: "Criar fixtures CSV do Inter em backend/tests/fixtures/inter/"

# Adapters em paralelo (depois de T015 pronto):
Task: "Implementar adapter do Bradesco em backend/src/financial_planner/parsers/bradesco.py"
Task: "Implementar adapter do Inter em backend/src/financial_planner/parsers/inter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Phase 1 (Setup) e Phase 2 (Foundational)
2. Completar Phase 3 (US1)
3. Validar Cenário 1 de `quickstart.md` manualmente
4. Nesse ponto já é possível importar um extrato de qualquer um dos dois bancos — MVP da feature

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → importação funcional (MVP)
3. US2 → reimportação segura, sem duplicar
4. US3 → visibilidade de erros/inconsistências
5. Polish → validação end-to-end com dado real (fora do repo) + revisão de aderência à constituição

---

## Notes

- Todas as tasks de teste usam apenas fixtures sintéticas pequenas — nenhum dado financeiro real entra no
  repositório (constituição, "Proteção de Dados Sensíveis")
- Categoria, subcategoria, confiança e parcelamento permanecem `NULL`/não tocados por esta feature — são
  responsabilidade de specs futuras
- Commitar após cada task ou grupo lógico de tasks
- **T028 concluída** com os 2 extratos reais do usuário (Bradesco + Inter, ago/2026) em `extracts/` (gitignored,
  confirmado via `git check-ignore`). Os 3 cenários do `quickstart.md` reconciliaram corretamente. A validação com dado real
  encontrou 2 bugs não previstos pela spec/fixtures originais, corrigidos e cobertos por novos testes de
  regressão (11/11 passando):
  1. Linha administrativa do Bradesco com Crédito e Débito ambos em branco (ex.: "COD. LANC. 0") crashava o
     parser — corrigido para tratar como transação de valor zero.
  2. A checagem de reconciliação de saldo normalizava o saldo sempre para valor absoluto, perdendo o sinal em
     contas com saldo negativo (cheque especial), e assumia ordem cronológica ascendente no arquivo — mas o
     export do Inter vem em ordem descendente (mais recente primeiro). Ambos corrigidos em
     `parsers/reconcile.py`.
