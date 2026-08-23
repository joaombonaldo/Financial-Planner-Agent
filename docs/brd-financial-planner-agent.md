# BRD — Financial Planner com Agentes de IA (LangGraph)

**Status:** Rascunho v1
**Última atualização:** 2026-08-22
**Autor:** João Miguel

---

## 1. Visão geral do projeto

Projeto pessoal de estudo com o objetivo de aprender arquitetura de agentes de IA na prática, construindo um planejador financeiro que:

- Importa extratos bancários (CSV/Excel) de 2 bancos
- Categoriza transações automaticamente usando um LLM, com revisão humana (human-in-the-loop)
- Rastreia parcelamentos de cartão de crédito, transferências entre contas próprias, receitas e despesas
- Compara gastos contra metas de orçamento definidas pelo usuário
- Gera insights mensais sobre a situação financeira
- Mantém histórico entre execuções mensais

O projeto é usado por um único usuário (o autor), com cadência de execução mensal (podendo chegar a semanal).

---

## 2. Objetivos de aprendizado

- Praticar LangGraph: `StateGraph`, `checkpointer`, `interrupt()`/human-in-the-loop, condicionais
- Praticar arquitetura desacoplada (separação domínio / infraestrutura / interface)
- Praticar React na Fase 2 (dashboard + revisão via UI)
- Aprender Supabase (Postgres hospedado) na Fase 2

---

## 3. Stack tecnológica

| Camada | Escolha | Observação |
|---|---|---|
| Orquestração de agentes | LangGraph | Grafo único com nodes especializados (não supervisor multi-agente — desnecessário para este fluxo) |
| LLM | Ollama local, modelo **Qwen2.5** | Troca futura para Claude/OpenAI via `init_chat_model()`, sem alterar nodes |
| Parsing de dados | pandas + openpyxl | Padrão de mercado para CSV/Excel |
| Persistência (fase 1) | SQLite | Checkpointer do LangGraph + memória de merchants + histórico, tudo no mesmo banco |
| Persistência (fase 2) | Supabase (Postgres) | Free tier ($0/mês); migração via `langgraph-checkpoint-postgres`, mesma interface do SQLite |
| Observability | LangSmith | Tracing automático via variáveis de ambiente, sem mudança de código |
| Gerenciador de dependências | `uv` | |
| Interface (fase 1) | CLI | Foco em validar o fluxo do agente antes de investir em UI |
| Interface (fase 2) | React + FastAPI | FastAPI expõe `core/` via API assíncrona (necessário por causa do `interrupt()`) |
| Repositório | Monorepo (`backend/` + `frontend/`) | Projeto pessoal, um único dev — repos separados não trazem benefício aqui |

---

## 4. Arquitetura do grafo (LangGraph)

Fluxo sequencial de 7 nodes, com um ponto de interrupção humana:

```
detect_and_parse → categorize → human_review (interrupt) → update_memory
    → budget_check → generate_insights → generate_report
```

| Node | Responsabilidade | Usa LLM? |
|---|---|---|
| `detect_and_parse` | Identifica o banco de origem e normaliza os dados via adapter pattern (1 parser por banco) | Não |
| `categorize` | Categoriza transações; usa memória de merchants já confirmados, só chama o LLM para casos novos/ambíguos | Sim |
| `human_review` | Interrompe o grafo (`interrupt()`) para revisão/correção de itens de confiança média/baixa | Não |
| `update_memory` | Persiste correções no mapeamento merchant → categoria | Não |
| `budget_check` | Compara gastos por categoria contra metas definidas | Não |
| `generate_insights` | Gera observações sobre tendências e comparação com meses anteriores | Sim (opcional) |
| `generate_report` | Monta o relatório final do mês | Não |

**Estratégia de threads:** cada mês processado é um `thread_id` próprio no checkpointer (ex: `2026-08`), permitindo reprocessar/auditar um mês isoladamente. Histórico entre meses vive na camada de dados (SQLite/Supabase), não no state do grafo.

---

## 5. Regras de negócio

### 5.1 Categorização
- Taxonomia com categorias e subcategorias (ver Anexo A), extensível conforme uso real
- Confiança representada de forma categórica (`high` / `medium` / `low`), não numérica — alinhado ao que LLMs conseguem estimar de forma confiável
- `high`: merchant já conhecido → passa direto
- `medium`/`low`: vai para `human_review`

### 5.2 Transferências entre contas próprias
- Transações com padrão de transferência (`TED`, `PIX`, `DOC`) e valor espelhado em outra conta (janela de ±2 dias) são **sugeridas** como "Transferência interna" pelo `categorize`, mas confirmadas via `human_review` — não são excluídas automaticamente sem supervisão
- Transferências confirmadas são excluídas do total de gastos/receitas

### 5.3 Parcelamentos (cartão de crédito)
- Cada parcela aparece no gasto mensal normal da categoria correspondente
- Existe uma tabela própria (`installments`) com valor total, número de parcelas, parcelas pagas/restantes — consultável como visão separada

### 5.4 Receitas e despesas
- O sistema rastreia movimentação completa (entradas e saídas), não apenas gastos
- Campo `type` da transação: `income` / `expense` / `transfer` (extensível para suportar investimentos na Fase 3)

### 5.5 Metas de orçamento
- Fase 1: arquivo `config/budget.local.yaml` (gitignored), lido via função `get_budget()`
- Fase 2: mesma função passa a ler do Supabase, sem alterar o restante do sistema

---

## 6. Modelo de dados

### 6.1 Transação (schema normalizado)

```
id                  # PK auto-incremento
dedup_hash          # hash(date + description_raw + amount + account) — evita duplicação em reimportação
date
description_raw     # como veio do banco
account             # banco/conta de origem
type                # income | expense | transfer
amount              # sempre positivo; type indica a direção
category
subcategory
confidence          # high | medium | low
installment_id      # FK, nullable
month_ref           # ex: "2026-08"
```

### 6.2 Parcelamentos

```
installments
├── id
├── description
├── total_amount
├── num_installments
├── installment_amount
├── first_charge_date
└── account
```

### 6.3 Formato de origem por banco

**Status: confirmado a partir de exports reais** (período 24/07 a 22/08/2026, 1 mês, ambos os bancos).

| Aspecto | Bradesco | Inter |
|---|---|---|
| Encoding | UTF-8 **com BOM** (`EF BB BF`) — exige `utf-8-sig` na leitura | UTF-8 sem BOM |
| Separador | `;` | `;` |
| Formato numérico | Brasileiro (`1.645,20` = mil seiscentos e quarenta e cinco vírgula vinte) | Brasileiro, igual |
| Formato de data | `DD/MM/AAAA` | `DD/MM/AAAA` |
| Coluna de valor | **Duas colunas separadas**: `Crédito (R$)` e `Débito (R$)` (uma populada, outra em branco) | **Uma coluna única** `Valor`, com sinal (negativo = débito) |
| Descrição da transação | `Histórico` (ex: "PIX ENVIADO", "PIX RECEBIDO") — **nunca inclui nome do favorecido/pagador** | `Histórico` (tipo genérico, ex: "Compra no débito") + `Descrição` (nome do estabelecimento/pessoa) — **`Descrição` vem vazia em algumas linhas**, precisa fallback pro `Histórico` |
| Identificador nativo | Coluna `Docto.` (número do documento) | Não existe — só saldo corrente |
| Saldo corrente | Sim, coluna `Saldo (R$)` | Sim, coluna `Saldo` |
| Linhas de metadado no arquivo | Linha 1 (agência/conta), depois header | 4 linhas (título, conta, período, saldo) + linha em branco, depois header |
| Estrutura de seções | **Duas seções no mesmo arquivo**: extrato principal + bloco "Últimos Lancamentos" (header repetido no meio do arquivo) + linha de rodapé "Total" | Seção única |

**Estratégia de parsing adotada (validada com os arquivos reais):** em vez de `skiprows` fixo, cada linha é testada contra um regex de data (`^\d{2}/\d{2}/\d{4};`) — só linhas que batem viram transação. Isso resolve de forma robusta o caso do Bradesco (metadado, header duplicado no meio do arquivo, linha de total no rodapé, linhas em branco) sem precisar mapear a estrutura exata linha a linha. Testado no arquivo real: 54 linhas totais → 42 linhas de transação válidas.

**Achados que impactam decisões já tomadas:**
- **Detecção de transferência interna (seção 5.2) fica mais fraca do lado Bradesco**: como o `Histórico` do Bradesco nunca cita o nome do favorecido/pagador (só "PIX ENVIADO"/"PIX RECEBIDO" genérico), o matching de transferência entre as duas contas próprias vai depender quase exclusivamente do **valor espelhado + janela de data**, não de texto — o que já era a regra desenhada, mas agora confirmamos que não há sinal textual adicional do lado Bradesco pra reforçar o match. Reforça a decisão de manter isso sempre em `human_review`, nunca automático.
- **`dedup_hash` (seção 6.1) segue necessário mesmo sem duplicata exata encontrada nesta amostra** — o Bradesco tem duas seções (`extrato principal` + `Últimos Lancamentos`) com potencial de sobreposição em reexportações futuras (ex: exportar de novo incluindo dias já processados).
- **Coluna `Saldo` de ambos os bancos** pode servir como checagem de sanidade do parser em teste automatizado: saldo da linha anterior ± valor da linha atual deve bater com o saldo da linha seguinte.

---

## 7. Estrutura do repositório

```
financial-planner-agent/
├── backend/
│   ├── pyproject.toml
│   ├── src/financial_planner/
│   │   ├── graph.py              # monta e compila o StateGraph
│   │   ├── state.py              # schema tipado (domínio)
│   │   ├── nodes/                # casos de uso — orquestram, não implementam I/O direto
│   │   │   ├── ingest.py
│   │   │   ├── categorize.py
│   │   │   ├── review.py
│   │   │   ├── memory.py
│   │   │   ├── budget.py
│   │   │   ├── insights.py
│   │   │   └── report.py
│   │   ├── parsers/               # adapters — 1 arquivo por banco
│   │   ├── db/                    # adapter de persistência
│   │   │   ├── schema.sql
│   │   │   └── repository.py
│   │   ├── config/
│   │   │   ├── categories.yaml
│   │   │   └── budget.example.yaml
│   │   └── interface/
│   │       ├── cli.py             # fase 1
│   │       └── api.py             # fase 2 — FastAPI
│   └── tests/
│       ├── fixtures/              # CSVs fake por banco
│       ├── golden_set.csv         # transações com categoria correta conhecida
│       ├── test_parsers.py
│       └── test_graph.py
├── frontend/                       # fase 2 — React
├── extracts/                       # gitignored — exports reais
└── README.md
```

**Princípio arquitetural:** nodes nunca acessam banco/LLM diretamente — sempre via `db/repository.py` ou cliente de LLM abstraído. Isso mantém a direção de dependência correta (lógica de negócio não depende de infraestrutura) sem precisar de interfaces formais (`Protocol`/ABC), que seriam over-engineering para este porte de projeto.

### Variáveis de ambiente (`.env`)
`OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `SQLITE_DB_PATH`

---

## 8. Estratégia de dados sensíveis

- Nenhum dado real (extratos, categorias personalizadas, metas, banco `.db`) entra no repositório
- `.gitignore` cobre: `extracts/`, `*.db`, `config/budget.local.yaml`, `.env`
- Repositório versiona apenas código reutilizável + `config/budget.example.yaml` com valores fictícios

---

## 9. Estratégia de testes

- **Testes unitários dos parsers** — fixtures pequenas (2-3 linhas) por banco, determinístico
- **Golden set de categorização** — ~30-40 transações reais/anonimizadas com categoria correta conhecida, usado para medir acurácia (crítico ao trocar de LLM local para Claude/OpenAI)
- **Grafo com LLM mockado** — valida conexão de nodes/edges sem depender do Ollama rodando

---

## 10. Escopo e roadmap

### MVP (Fase 1)
- CLI, 1 usuário, 2 bancos
- Categorização + revisão humana + relatório simples
- **Critério de aceite:**
  1. Processar um mês real de 2 bancos sem erro
  2. Revisão/correção funcional via CLI
  3. Relatório final bate com soma conferida manualmente no extrato
  4. Insights gerados refletem corretamente a situação financeira do mês, de forma que ajudem a entender para onde o dinheiro está indo

### Fase 2
- React + dashboards + histórico visual
- Migração de persistência para Supabase
- Backend FastAPI expondo `core/` via API assíncrona (padrão start-run → poll-status → resume-review)

### Fase 3
- Tracking de investimentos (além de planejamento financeiro)

---

## 11. Fora de escopo (explícito)

- Integração automática com banco (open banking/API) — export manual é premissa assumida do projeto inteiro
- Multiusuário/autenticação no MVP (mesmo migrando para Supabase na Fase 2, uso permanece pessoal)
- Aplicativo mobile
- Alertas em tempo real (`budget_check` roda apenas quando o mês é processado, não monitora continuamente)

---

## Anexo A — Taxonomia inicial de categorias

| Categoria | Subcategorias |
|---|---|
| Moradia | Aluguel/Financiamento, Condomínio, Energia, Água, Internet, Gás |
| Alimentação | Mercado, Restaurante/Delivery, Padaria/Café |
| Transporte | Combustível, Uber/99, Transporte público, Manutenção veículo, Estacionamento |
| Saúde | Plano de saúde, Farmácia, Consultas |
| Assinaturas | Streaming, Software/SaaS, Academia |
| Lazer | Viagem, Eventos/Shows, Hobbies |
| Educação | Cursos, Livros, Mensalidade |
| Vestuário | Roupas, Calçados |
| Cartão de crédito/Parcelamentos | (visão própria — ver seção 5.3) |
| Transferência interna | (excluída do total de gastos — ver seção 5.2) |
| Receita | Salário, Freelance/Extra, Reembolso, Outras entradas |
| Outros | Fallback para baixa confiança |

*Lista inicial — sujeita a expansão conforme merchants reais aparecerem na revisão mensal.*

**Achados dos exports reais que sugerem ajuste na taxonomia:**
- `Aplicação` (ex: "Cdb Pos Di Liq. Banco Inter") — aporte de investimento. Fica em `Outros` por enquanto (rastreio de investimento é Fase 3), mas já é sinal de que vale uma categoria `Investimento` dedicada quando a Fase 3 chegar.
- `Deb Cartao + Protegido` (seguro de cartão) — sugerido como subcategoria nova `Seguros` dentro de `Assinaturas`.
- `Pagamento efetuado` / "Pagamento Fatura" (pagamento da fatura do cartão de crédito, saindo da conta corrente) — mapeia para `Cartão de crédito/Parcelamentos` como o pagamento agregado do mês; compõe-se das parcelas individuais já categorizadas separadamente (ver seção 5.3). Vale confirmar esse relacionamento durante a `human_review` do primeiro mês real.
