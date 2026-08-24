"""Minimal state that flows between the StateGraph's nodes.

Deliberately small: nodes fetch and persist transactions directly in the database (the
pattern already established in ingest/categorize), so the graph state doesn't carry
the transaction list — only what the nodes need to know what to process.
"""

from typing import TypedDict


class GraphState(TypedDict):
    source_files: list[str]
    month_ref: str
    db_path: str
