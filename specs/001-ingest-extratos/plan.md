# Implementation Plan: Ingestão de Extratos Bancários

**Branch**: `001-ingest-extratos` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ingest-extratos/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implementar o node `detect_and_parse`: dado um arquivo CSV exportado manualmente do Bradesco ou do Inter, detectar
automaticamente o banco de origem, extrair apenas as linhas de transação real (ignorando metadado, headers
repetidos e rodapé), normalizar valor/data para um formato canônico, calcular hash de deduplicação e persistir
transações prontas para a etapa de categorização — sem duplicar em reimportações e sem falhar silenciosamente
quando o arquivo não reconciliar ou não for reconhecido.

## Technical Context

**Language/Version**: Python 3.12 (`backend/.python-version`)

**Primary Dependencies**: pandas + openpyxl (leitura/parsing de CSV), `sqlite3` (stdlib, via `db/repository.py`)

**Storage**: SQLite (`backend/src/financial_planner/db/schema.sql`) — esta feature só precisa da tabela
`transactions` (colunas do schema normalizado descrito no BRD 6.1) para checar `dedup_hash` já existentes

**Testing**: pytest, com fixtures CSV pequenas e determinísticas por banco (2-3 linhas + casos de borda), conforme
`Padrões de Teste` da constituição

**Target Platform**: CLI local (macOS/Linux), execução mensal single-user

**Project Type**: Projeto único dentro do monorepo (`backend/`) — sem componente de frontend nesta fase

**Performance Goals**: N/A — volume mensal da ordem de dezenas de transações por banco; não há requisito de
throughput

**Constraints**: Não deve depender de LLM nem de rede (`detect_and_parse` não usa LLM, por design do BRD seção 4);
deve ser resiliente às particularidades de arquivo já documentadas na spec (BOM, seções duplicadas, coluna de
descrição vazia)

**Scale/Scope**: 2 bancos suportados (Bradesco, Inter), ~1 mês de extrato por execução (dezenas de linhas)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Aplicação nesta feature | Status |
|---|---|---|
| I. Simplicidade Pragmática | Um parser por banco (adapter pattern), sem abstração além do necessário para 2 bancos conhecidos | PASS |
| II. Nodes Isolados de Infraestrutura | `nodes/ingest.py` orquestra; leitura de arquivo fica em `parsers/`, acesso a banco (checagem de dedup) fica em `db/repository.py` — node não toca pandas nem sqlite3 diretamente | PASS |
| III. LLM Trocável por Abstração | N/A — este node não usa LLM | N/A |
| IV. Persistência Portável | Query de `dedup_hash` usa SQL padrão (sem sintaxe específica de SQLite), compatível com troca futura para Postgres | PASS |
| V. Revisão Humana Obrigatória | N/A — nenhuma decisão sensível (categorização, transferência) é tomada nesta feature | N/A |
| VI. Confiança Categórica | N/A — `confidence` não é preenchido por esta feature | N/A |
| VII. Deduplicação Determinística | Requisito central (FR-006): hash de `date+description_raw+amount+account` | PASS |

Nenhuma violação — Complexity Tracking não se aplica.

## Project Structure

### Documentation (this feature)

```text
specs/001-ingest-extratos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/financial_planner/
│   ├── state.py                     # schema tipado da Transação normalizada (domínio)
│   ├── nodes/
│   │   └── ingest.py                # node detect_and_parse — orquestra parser + repository
│   ├── parsers/
│   │   ├── base.py                  # contrato comum do adapter de parsing (ver contracts/)
│   │   ├── bradesco.py              # adapter Bradesco
│   │   ├── inter.py                 # adapter Inter
│   │   └── detect.py                # detecção automática de banco a partir do arquivo
│   └── db/
│       ├── schema.sql               # tabela transactions (subset usado por esta feature)
│       └── repository.py            # checagem/persistência de dedup_hash
└── tests/
    ├── fixtures/
    │   ├── bradesco/                # CSVs pequenos: caso feliz + casos de borda
    │   └── inter/                   # idem para Inter
    └── test_parsers.py

frontend/                             # não usado nesta fase
```

**Structure Decision**: Projeto único em `backend/`, reaproveitando a estrutura já definida no BRD (seção 7).
`parsers/` concentra o adapter pattern por banco (Princípio II — isola pandas/leitura de arquivo dos nodes);
`db/repository.py` concentra o acesso a SQLite para checagem de `dedup_hash`. `frontend/` permanece vazio, fora do
escopo desta feature e da Fase 1 como um todo.

## Complexity Tracking

*Não aplicável — nenhuma violação de constituição identificada.*
