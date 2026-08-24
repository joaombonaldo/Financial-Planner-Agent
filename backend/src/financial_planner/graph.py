"""Monta e compila o StateGraph: detect_and_parse -> categorize -> human_review.

human_review usa uma aresta condicional de self-loop (em vez de um laço interno) para
tratar múltiplos itens pendentes — ver nodes/review.py para o motivo.
"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from financial_planner.db.repository import connect, list_pending_review
from financial_planner.graph_state import GraphState
from financial_planner.nodes.categorize import categorize
from financial_planner.nodes.ingest import detect_and_parse
from financial_planner.nodes.review import review


def _ingest_node(state: GraphState) -> dict:
    for path in state["source_files"]:
        detect_and_parse(path, state["db_path"])
    return {}


def _categorize_node(state: GraphState) -> dict:
    categorize(state["month_ref"], state["db_path"])
    return {}


def _review_node(state: GraphState) -> dict:
    review(state["month_ref"], state["db_path"])
    return {}


def _has_pending_review(state: GraphState) -> str:
    conn = connect(state["db_path"])
    try:
        pending = list_pending_review(conn, state["month_ref"])
    finally:
        conn.close()
    return "human_review" if pending else END


def build_graph(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    builder = StateGraph(GraphState)
    builder.add_node("detect_and_parse", _ingest_node)
    builder.add_node("categorize", _categorize_node)
    builder.add_node("human_review", _review_node)

    builder.set_entry_point("detect_and_parse")
    builder.add_edge("detect_and_parse", "categorize")
    builder.add_edge("categorize", "human_review")
    builder.add_conditional_edges(
        "human_review", _has_pending_review, {"human_review": "human_review", END: END}
    )

    return builder.compile(checkpointer=checkpointer)
