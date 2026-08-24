"""Grafo mínimo para testar nodes/review.py isoladamente.

Contém só o node human_review (com o mesmo self-loop condicional de graph.py) — evita
que detect_and_parse/categorize rodem durante o teste e sobrescrevam os dados já
semeados pela fixture (categorize chamaria o LLM real, o que a constituição proíbe em
teste automatizado).
"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, Interrupt

from financial_planner.db.repository import connect, list_pending_review
from financial_planner.graph_state import GraphState
from financial_planner.nodes.review import review


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


def build_review_only_graph(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    builder = StateGraph(GraphState)
    builder.add_node("human_review", _review_node)
    builder.set_entry_point("human_review")
    builder.add_conditional_edges(
        "human_review", _has_pending_review, {"human_review": "human_review", END: END}
    )

    return builder.compile(checkpointer=checkpointer)


def drive_review(graph, thread_id: str, month_ref: str, db_path: str, answers: list[str]) -> list[dict]:
    """Roda o grafo, respondendo cada interrupt() na ordem de `answers`.

    Retorna os payloads de cada interrupt() encontrado, na ordem em que apareceram.
    """
    config = {"configurable": {"thread_id": thread_id}}
    payloads: list[dict] = []
    answer_iter = iter(answers)

    result = graph.invoke({"source_files": [], "month_ref": month_ref, "db_path": db_path}, config=config)

    while result.get("__interrupt__"):
        interrupt_obj: Interrupt = result["__interrupt__"][0]
        payloads.append(interrupt_obj.value)
        answer = next(answer_iter)
        result = graph.invoke(Command(resume=answer), config=config)

    return payloads
