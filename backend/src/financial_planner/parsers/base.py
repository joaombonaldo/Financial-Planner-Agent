"""Contrato comum dos adapters de parser por banco.

Ver specs/001-ingest-extratos/contracts/parser-adapter.md. Cada adapter de banco
(bradesco.py, inter.py) expõe uma função `parse(path: str) -> list[Transaction]` com
essas garantias:

- Linhas de metadado, headers repetidos e rodapé nunca viram Transaction.
- description_raw nunca é vazio (fallback aplicado internamente pelo adapter).
- amount sempre positivo; a direção vai inteiramente em `type`.
- date e amount já normalizados para o formato canônico.
- A ordem das transações retornadas preserva a ordem do arquivo de origem.

Sem Protocol/ABC formal (Princípio I — simplicidade pragmática): a garantia é por
convenção de assinatura, não por contrato de tipo.
"""

import re

# Só linhas que começam com uma data DD/MM/AAAA seguida de ';' são candidatas a
# transação — resolve de forma robusta metadado, header duplicado e rodapé sem
# precisar mapear a estrutura exata do arquivo linha a linha (ver research.md).
TRANSACTION_LINE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4};")


def is_transaction_line(line: str) -> bool:
    return bool(TRANSACTION_LINE_PATTERN.match(line))


def filter_transaction_lines(raw_lines: list[str]) -> list[str]:
    """Retorna apenas as linhas candidatas a transação, na ordem original do arquivo."""
    return [line for line in raw_lines if is_transaction_line(line)]
