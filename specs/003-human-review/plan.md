# Implementation Plan: Revisão Humana de Transações

**Branch**: `003-human-review` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-human-review/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implementar o node `human_review` e, pela primeira vez, montar de fato um `StateGraph` do LangGraph (ligando
`detect_and_parse` → `categorize` → `human_review`, com checkpointer SQLite). O node consulta as transações do mês
ainda com `confidence != high`, e para cada uma chama `interrupt()` pedindo confirmação ou correção; a decisão é
persistida imediatamente e a confiança vira `high`. Uma CLI mínima (`interface/cli.py`) dirige o loop de
interrupção/retomada — genérica o suficiente para não conhecer regras de negócio, só exibir o que o node manda e
devolver a resposta do usuário.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `langgraph` (já presente — `StateGraph`, `interrupt`, `Command`),
`langgraph-checkpoint-sqlite` (novo — `SqliteSaver`, checkpointer que permite retomar exatamente de onde parou)

**Storage**: SQLite — o checkpointer usa o mesmo arquivo de banco já usado por `transactions`/`merchant_memory`
(BRD seção 3: "tudo no mesmo banco"), em tabelas próprias criadas automaticamente pelo `SqliteSaver`

**Testing**: pytest. Testes do node chamam a função de revisão diretamente, injetando respostas via um driver de
teste que simula o loop de `interrupt()`/`Command(resume=...)`, sem terminal real — consistente com o padrão já
usado para o LLM mockado.

**Target Platform**: CLI local (macOS/Linux), execução mensal single-user

**Project Type**: Projeto único dentro do monorepo (`backend/`)

**Performance Goals**: N/A

**Constraints**: A revisão de um item MUST sobreviver a uma interrupção de processo (fechar o terminal) — depende
inteiramente do checkpointer persistir o estado do grafo em disco antes de cada pausa, não em memória

**Scale/Scope**: dezenas de itens pendentes por mês, no pior caso (nenhum merchant conhecido ainda)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Aplicação nesta feature | Status |
|---|---|---|
| I. Simplicidade Pragmática | Usa o padrão recomendado do próprio LangGraph para múltiplas interrupções em loop dentro de um node — nenhuma máquina de estados própria; CLI só exibe/coleta texto, sem framework de TUI | PASS |
| II. Nodes Isolados de Infraestrutura | `nodes/review.py` só acessa banco via `db/repository.py`; a CLI (`interface/cli.py`) é a camada de interface, não um node — já prevista como componente separado na arquitetura do BRD (seção 7) | PASS |
| III. LLM Trocável por Abstração | N/A — este node não usa LLM | N/A |
| IV. Persistência Portável | Tabelas próprias (`transactions`) seguem SQL padrão; o checkpointer usa `langgraph-checkpoint-sqlite` hoje, com troca planejada para `langgraph-checkpoint-postgres` na Fase 2 (BRD seção 3) — mesma interface, migração já prevista | PASS |
| V. Revisão Humana Obrigatória | Esta feature é a implementação direta do princípio | PASS |
| VI. Confiança Categórica | Toda decisão humana resulta em `confidence = high` — nunca um valor numérico | PASS |
| VII. Deduplicação Determinística | N/A — não recalcula dedup | N/A |

Nenhuma violação — Complexity Tracking não se aplica.

## Project Structure

### Documentation (this feature)

```text
specs/003-human-review/
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
│   ├── graph.py                      # NOVO — monta e compila o StateGraph (checkpointer SqliteSaver)
│   ├── graph_state.py                # NOVO — GraphState (TypedDict mínimo: source_files, month_ref, db_path)
│   ├── nodes/
│   │   ├── ingest.py                 # existente — adaptado para a assinatura de node do LangGraph
│   │   ├── categorize.py             # existente — idem
│   │   └── review.py                 # NOVO — node human_review
│   ├── db/
│   │   └── repository.py             # + list_pending_review(month_ref)
│   └── interface/
│       └── cli.py                    # NOVO — driver mínimo do loop interrupt()/resume
└── tests/
    ├── fixtures/
    │   └── review/                   # transações sintéticas com confidence variada
    └── test_review.py

frontend/                             # não usado nesta fase
```

**Structure Decision**: Introduz `graph.py`/`graph_state.py` na raiz do pacote (montagem do grafo é transversal,
não pertence a nenhum node específico) e `interface/cli.py` como a primeira peça da camada de interface prevista
na estrutura do BRD (seção 7). `nodes/review.py` seguindo o mesmo padrão dos nodes anteriores — só orquestra,
acessa banco via `db/repository.py`.

## Complexity Tracking

*Não aplicável — nenhuma violação de constituição identificada.*
