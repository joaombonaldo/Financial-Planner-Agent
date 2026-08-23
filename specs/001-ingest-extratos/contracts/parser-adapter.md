# Contract: Adapter de Parser por Banco

Interface interna que cada adapter de banco (`parsers/bradesco.py`, `parsers/inter.py`) deve implementar. Consumida
por `parsers/detect.py` (seleção do adapter) e por `nodes/ingest.py` (orquestração) — nunca diretamente por outros
nodes, conforme Princípio II da constituição.

## Detecção de banco

**Entrada**: conteúdo bruto (ou caminho) do arquivo de extrato.

**Saída**: identificador do banco (`bradesco` | `inter`) ou sinal explícito de "não reconhecido".

**Regra**: baseada na estrutura de colunas do header (ver research.md — "Detecção automática do banco de origem").
Nunca lança exceção silenciosa; um arquivo não reconhecido é um resultado explícito, não uma falha de parsing
tratada como sucesso vazio.

## Parsing por adapter

**Entrada**: conteúdo bruto (ou caminho) do arquivo de extrato, já identificado como pertencente a um banco
específico.

**Saída**: lista de `Transação normalizada` (subset de campos definido em `data-model.md`) + informações
necessárias para montar o `ImportResult` (linhas de saldo lidas, na ordem do arquivo, para a checagem de sanidade).

**Garantias que o contrato exige de qualquer adapter**:
- Linhas de metadado, headers repetidos e rodapé nunca aparecem na lista de transações retornada.
- `description_raw` nunca é vazio (aplica fallback `Histórico` quando a coluna primária de descrição estiver em
  branco).
- `amount` sempre positivo; a direção (entrada/saída) vai inteiramente no campo `type`.
- `date` e `amount` já normalizados para o formato canônico (ISO date, decimal) — o chamador nunca recebe formato
  bruto do banco.
- A ordem das transações retornadas preserva a ordem do arquivo de origem (necessário para a checagem de saldo
  sequencial).

## Uso pelo node `detect_and_parse`

O node (`nodes/ingest.py`) apenas orquestra: chama a detecção de banco, seleciona o adapter correspondente, chama o
parsing, e delega a checagem de `dedup_hash` + persistência para `db/repository.py`. O node não lê arquivo nem
formata CSV diretamente — essa é a fronteira que o Princípio II da constituição protege.
