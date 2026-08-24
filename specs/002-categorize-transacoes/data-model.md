# Data Model: Categorização de Transações

## Transação (campos preenchidos por esta feature)

Estende o schema já criado pela feature 001 (`transactions`). Esta feature preenche os campos que a ingestão
deixou `NULL`:

| Campo | Tipo | Origem / regra |
|---|---|---|
| `category` | string | "Transferência interna" (candidata), categoria mapeada em memória, categoria sugerida pelo LLM, ou "Outros" (fallback) |
| `subcategory` | string, nullable | idem, quando aplicável (transferência e "Outros" podem não ter subcategoria) |
| `confidence` | enum: `high`\|`medium`\|`low` | `high` somente via merchant memory; LLM e candidatos a transferência nunca produzem `high` |

Campos já preenchidos pela feature 001 (`dedup_hash`, `date`, `description_raw`, `account`, `type`, `amount`,
`month_ref`) são apenas lidos, nunca alterados por esta feature. `installment_id` continua fora do escopo.

## Merchant Memory

Nova tabela, só leitura nesta feature (escrita é responsabilidade de uma feature futura, `update_memory`).

| Campo | Tipo | Descrição |
|---|---|---|
| `merchant_key` | string, PK | texto normalizado (trim + lowercase) de `description_raw` |
| `category` | string | categoria confirmada em execução anterior |
| `subcategory` | string, nullable | subcategoria confirmada, quando aplicável |

**Validação**: se `merchant_key` não existe na tabela, a transação segue para detecção de transferência / LLM
(não é um erro — é o caso esperado de merchant novo, ver User Story 2).

## Taxonomia

Não é uma tabela — é configuração carregada de `config/categories.yaml` (Anexo A do BRD).

| Campo | Tipo | Descrição |
|---|---|---|
| `category` | string | nome da categoria (ex.: "Alimentação") |
| `subcategories` | list[string] | subcategorias válidas daquela categoria |

Duas entradas especiais sempre presentes: `"Outros"` (fallback, sem subcategoria obrigatória) e `"Transferência
interna"` (usada só pela detecção de transferência, nunca sugerida pelo LLM).

**Validação**: qualquer categoria/subcategoria fora desta lista, vinda do LLM, é substituída por `"Outros"` /
`confidence = low` (ver research.md).

## Candidato a Transferência (conceito, não é uma tabela própria)

Resultado da checagem de padrão + valor espelhado (FR-007), expresso como a combinação:
`category = "Transferência interna"`, `confidence = medium` (nunca `high` — sempre pendente de confirmação humana,
nunca `low`, porque é um match estrutural direto, não um palpite). Não existe uma entidade "TransferCandidate"
separada — a sinalização vive inteiramente nos campos da própria transação. A confirmação (ou rejeição) da
sugestão fica para uma feature futura (`human_review`).
