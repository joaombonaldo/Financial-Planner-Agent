"""Estado mínimo que flui entre os nodes do StateGraph.

Deliberadamente pequeno: os nodes buscam e persistem transações direto no banco
(padrão já estabelecido em ingest/categorize), então o estado do grafo não carrega a
lista de transações — só o necessário para os nodes saberem o que processar.
"""

from typing import TypedDict


class GraphState(TypedDict):
    source_files: list[str]
    month_ref: str
    db_path: str
