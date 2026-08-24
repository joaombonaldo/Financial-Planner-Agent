# Implementation Plan: Categorização de Transações

**Branch**: `002-categorize-transacoes` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-categorize-transacoes/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Implementar o node `categorize`: para cada transação normalizada pela feature de ingestão (001), verificar se o
merchant já tem categoria confirmada em memória (`confidence = high`, sem LLM); se o padrão de transferência
(PIX/TED/DOC) tiver um valor espelhado em outra conta do usuário dentro de ±2 dias, sugerir "Transferência interna"
sem excluir do total; caso contrário, chamar o LLM (via abstração trocável) para sugerir categoria/subcategoria da
taxonomia configurada, com `confidence` `medium`/`low` e fallback para "Outros" quando a resposta não corresponder
à taxonomia. Persistir categoria/subcategoria/confiança na transação, pronta para a revisão humana (feature
futura).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `langchain-ollama` (via `init_chat_model` — abstração trocável de LLM), `pyyaml`
(taxonomia em `config/categories.yaml`), `sqlite3` (stdlib, via `db/repository.py`)

**Storage**: SQLite — estende a tabela `transactions` já criada pela feature 001 (preenche `category`,
`subcategory`, `confidence`, ainda nulos) e adiciona a tabela `merchant_memory` (mapeamento merchant → categoria
confirmada). Esta feature só lê `merchant_memory`; gravar nela é responsabilidade de uma feature futura
(`update_memory`).

**Testing**: pytest, com o LLM sempre mockado (constituição — "O grafo é testável com LLM mockado, sem depender do
Ollama rodando"); fixtures determinísticas para merchant conhecido, merchant novo, resposta fora da taxonomia e
par de transferência espelhada.

**Target Platform**: CLI local (macOS/Linux), execução mensal single-user

**Project Type**: Projeto único dentro do monorepo (`backend/`)

**Performance Goals**: N/A — mesma ordem de grandeza de volume da feature 001 (dezenas de transações/mês)

**Constraints**: Não pode depender de um servidor Ollama real rodando para os testes (LLM sempre mockado nos
testes); a categoria retornada pelo LLM nunca pode resultar em `confidence = high` (Princípio VI/FR-006)

**Scale/Scope**: ~1 mês de transações por execução, 2 contas conhecidas (Bradesco, Inter)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Aplicação nesta feature | Status |
|---|---|---|
| I. Simplicidade Pragmática | Taxonomia como config YAML, sem motor de regras genérico; detecção de transferência é uma checagem direta (padrão + janela de dias), não um sistema de matching genérico | PASS |
| II. Nodes Isolados de Infraestrutura | `nodes/categorize.py` orquestra; acesso ao LLM fica em `llm/client.py`, acesso a banco em `db/repository.py` — node não chama `init_chat_model` nem `sqlite3` diretamente | PASS |
| III. LLM Trocável por Abstração | Núcleo da feature — `llm/client.py` usa `init_chat_model`, hoje Ollama/Qwen2.5, trocável sem alterar `nodes/categorize.py` | PASS |
| IV. Persistência Portável | `merchant_memory` e o update de `transactions` usam SQL padrão | PASS |
| V. Revisão Humana Obrigatória | Respeitada por design: `confidence` médio/baixo e candidatos a transferência nunca são aplicados como definitivos por esta feature — ficam para `human_review` (feature futura) | PASS |
| VI. Confiança Categórica | Central — FR-006/FR-009: `high` só via memória, LLM nunca retorna `high` diretamente | PASS |
| VII. Deduplicação Determinística | N/A — esta feature não recalcula dedup (já resolvido pela ingestão) | N/A |

Nenhuma violação — Complexity Tracking não se aplica.

## Project Structure

### Documentation (this feature)

```text
specs/002-categorize-transacoes/
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
│   ├── nodes/
│   │   └── categorize.py            # node categorize — orquestra memória + transferência + LLM
│   ├── llm/
│   │   └── client.py                # abstração trocável do LLM (init_chat_model)
│   ├── categorization/
│   │   ├── taxonomy.py              # carrega/valida config/categories.yaml, fallback "Outros"
│   │   ├── merchant_memory.py       # leitura de merchant_memory via db/repository.py
│   │   ├── transfer_detection.py    # padrão PIX/TED/DOC + valor espelhado em ±2 dias
│   │   └── llm_categorizer.py       # chama llm/client.py, mapeia resposta para a taxonomia
│   ├── config/
│   │   └── categories.yaml          # taxonomia inicial (Anexo A do BRD)
│   └── db/
│       ├── schema.sql                # + tabela merchant_memory
│       └── repository.py             # + funções de leitura de merchant_memory e update de transação
└── tests/
    ├── fixtures/
    │   └── categorization/           # transações sintéticas: merchant conhecido, novo, fora da taxonomia, par de transferência
    └── test_categorize.py

frontend/                             # não usado nesta fase
```

**Structure Decision**: Reaproveita a estrutura do `backend/` criada pela feature 001. Novo módulo
`categorization/` concentra a lógica de domínio (taxonomia, memória, detecção de transferência, chamada ao LLM);
`llm/client.py` isola a abstração de LLM (Princípio III); `nodes/categorize.py` só orquestra, sem tocar
`init_chat_model` nem `sqlite3` diretamente (Princípio II).

## Complexity Tracking

*Não aplicável — nenhuma violação de constituição identificada.*
