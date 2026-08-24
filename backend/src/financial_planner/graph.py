"""Builds and compiles the StateGraph:
detect_and_parse -> categorize -> human_review -> update_memory -> budget_check.

human_review uses a self-loop conditional edge (instead of an internal loop) to handle
multiple pending items — see nodes/review.py for why. update_memory only runs once
human_review has fully resolved the month (no pending items left), and budget_check
runs right after, comparing the now-finalized month against configured goals.
"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from financial_planner.db.repository import connect, list_pending_review
from financial_planner.graph_state import GraphState
from financial_planner.nodes.budget import check_budget
from financial_planner.nodes.categorize import categorize
from financial_planner.nodes.ingest import detect_and_parse
from financial_planner.nodes.memory import update_memory
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


def _memory_node(state: GraphState) -> dict:
    update_memory(state["month_ref"], state["db_path"])
    return {}


def _budget_node(state: GraphState) -> dict:
    comparisons = check_budget(state["month_ref"], state["db_path"], state.get("budget_path"))
    return {
        "budget_report": [
            {
                "category": c.category,
                "goal": c.goal,
                "actual_spend": c.actual_spend,
                "difference": c.difference,
                "status": c.status.value,
            }
            for c in comparisons
        ]
    }


def _has_pending_review(state: GraphState) -> str:
    conn = connect(state["db_path"])
    try:
        pending = list_pending_review(conn, state["month_ref"])
    finally:
        conn.close()
    return "human_review" if pending else "update_memory"


def build_graph(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    builder = StateGraph(GraphState)
    builder.add_node("detect_and_parse", _ingest_node)
    builder.add_node("categorize", _categorize_node)
    builder.add_node("human_review", _review_node)
    builder.add_node("update_memory", _memory_node)
    builder.add_node("budget_check", _budget_node)

    builder.set_entry_point("detect_and_parse")
    builder.add_edge("detect_and_parse", "categorize")
    builder.add_edge("categorize", "human_review")
    builder.add_conditional_edges(
        "human_review",
        _has_pending_review,
        {"human_review": "human_review", "update_memory": "update_memory"},
    )
    builder.add_edge("update_memory", "budget_check")
    builder.add_edge("budget_check", END)

    return builder.compile(checkpointer=checkpointer)
