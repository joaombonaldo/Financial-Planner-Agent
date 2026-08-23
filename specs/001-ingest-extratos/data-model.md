# Data Model: Ingestão de Extratos Bancários

Escopo: apenas os campos e entidades que esta feature (`detect_and_parse`) produz ou consome. Campos preenchidos
por features posteriores (categorização, revisão humana, parcelamento) são citados como `deferred` e não são
responsabilidade desta feature.

## Transação normalizada

Corresponde ao subconjunto do schema `transactions` (BRD 6.1) que esta feature preenche.

| Campo | Tipo | Origem / regra | Obrigatório nesta feature? |
|---|---|---|---|
| `dedup_hash` | string | hash determinístico sobre `date + description_raw + amount + account` normalizados (ver research.md) | Sim |
| `date` | date (ISO) | normalizado de `DD/MM/AAAA` | Sim |
| `description_raw` | string | Bradesco: coluna `Histórico`. Inter: `Descrição`, com fallback para `Histórico` quando `Descrição` vier vazia | Sim |
| `account` | string | identificador da conta/banco de origem (Bradesco ou Inter), determinado na detecção automática | Sim |
| `type` | enum: `income` \| `expense` | derivado do sinal/coluna de origem (Bradesco: qual das colunas `Crédito`/`Débito` está populada; Inter: sinal de `Valor`) | Sim |
| `amount` | decimal, sempre positivo | normalizado do formato numérico brasileiro (`1.645,20` → `1645.20`) | Sim |
| `month_ref` | string (ex: `"2026-08"`) | derivado de `date` | Sim |
| `category` | string, nullable | — | Não — `deferred` para a feature de categorização |
| `subcategory` | string, nullable | — | Não — `deferred` |
| `confidence` | enum: `high`\|`medium`\|`low`, nullable | — | Não — `deferred` |
| `installment_id` | FK, nullable | — | Não — `deferred` (feature de parcelamentos) |

**Validação**:
- `dedup_hash` já existente na base → transação é descartada silenciosamente da inserção (não é erro; é o
  comportamento esperado de FR-006), mas segue contabilizada no relatório de importação (ver `ImportResult`).
- Linha do arquivo que não bate com o padrão de linha de transação (ver research.md) nunca vira `Transação` — é
  ignorada antes de chegar neste modelo.

## Resultado de importação (`ImportResult`)

Não é persistido — é o valor de retorno do processo de ingestão para uma execução, usado para reportar ao usuário
(FR-009) e para consumo pelo node seguinte no grafo.

| Campo | Tipo | Descrição |
|---|---|---|
| `bank` | enum: `bradesco` \| `inter` | banco detectado para o arquivo |
| `source_file` | string | caminho do arquivo processado |
| `transactions_imported` | int | quantidade de transações novas inseridas |
| `transactions_skipped_duplicate` | int | quantidade de transações reconhecidas mas já existentes (dedup) |
| `balance_reconciliation` | enum: `ok` \| `mismatch` \| `not_available` | resultado da checagem de saldo (research.md); `not_available` quando o arquivo não tem coluna de saldo utilizável |
| `warnings` | list[string] | mensagens explicativas de qualquer divergência (ex.: linha de saldo que não reconcilia) |

**Estado de erro (não gera `ImportResult`)**: se o banco não for reconhecido (FR-001), o processo retorna erro
explícito antes de produzir qualquer transação — não é um `ImportResult` com zero transações, é uma falha
reportada distintamente.

## Arquivo de extrato (entrada, não persistida)

Representa o CSV fornecido pelo usuário. Não é uma entidade de domínio armazenada — existe apenas como entrada do
processo desta feature.

| Campo | Descrição |
|---|---|
| `path` | caminho local do CSV exportado manualmente |
| `bank` (detectado) | Bradesco ou Inter — resultado da detecção automática, não fornecido pelo usuário |
