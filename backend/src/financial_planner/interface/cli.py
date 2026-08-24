"""Minimal driver for the interrupt()/resume loop. Knows nothing about taxonomy or
business rules — it only formats each interrupt()'s payload for the terminal and
returns a line of text (see contracts/review-node.md, specs/003-human-review).

All printed/prompted text stays in Portuguese: this is the app's actual runtime
language, since the user runs it in Portuguese (see contracts/review-node.md).
"""

import sys

from langgraph.types import Command

from financial_planner.graph import build_graph


def _format_payload(payload: dict) -> str:
    tx = payload["transaction"]
    lines = [
        f"\n{tx['date']} | {tx['account']} | R$ {tx['amount']:.2f}",
        f"  {tx['description_raw']}",
        f"  sugestão: {tx['category']} / {tx['subcategory'] or '-'} ({tx['confidence']})",
    ]
    if payload.get("error"):
        lines.append(f"  ! {payload['error']}")
    if payload["is_transfer_candidate"]:
        lines.append('  Responda "confirmar" ou "categoria|subcategoria" para rejeitar:')
    else:
        lines.append('  Responda "aceitar" ou "categoria|subcategoria" para corrigir:')
    return "\n".join(lines)


def run_month(month_ref: str, db_path: str, source_files: list[str]) -> None:
    graph = build_graph(db_path)
    config = {"configurable": {"thread_id": month_ref}}

    result = graph.invoke(
        {"source_files": source_files, "month_ref": month_ref, "db_path": db_path}, config=config
    )

    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        print(_format_payload(payload))
        answer = input("> ").strip()
        result = graph.invoke(Command(resume=answer), config=config)

    print(f"\nMês {month_ref} processado — nenhuma pendência de revisão restante.")


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: python -m financial_planner.interface.cli <month_ref> <db_path> [extrato.csv ...]")
        sys.exit(1)

    month_ref, db_path, *source_files = sys.argv[1:]
    run_month(month_ref, db_path, source_files)


if __name__ == "__main__":
    main()
