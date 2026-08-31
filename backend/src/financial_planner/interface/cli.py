"""Minimal driver for the interrupt()/resume loop. Knows nothing about taxonomy or
business rules — it only formats each interrupt()'s payload for the terminal and
returns a line of text (see contracts/review-node.md, specs/003-human-review).

All printed/prompted text stays in Portuguese: this is the app's actual runtime
language, since the user runs it in Portuguese (see contracts/review-node.md).
"""

import argparse
import os

from langgraph.types import Command

DEFAULT_DB_PATH = "data/financial-planner.db"

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
    subcategories = payload.get("suggested_subcategories") or []
    if subcategories:
        lines.append(f"  subcategorias válidas para {tx['category']}: {', '.join(subcategories)}")
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

    report = result.get("report")
    if report:
        _print_report(report)


def _print_report(report: dict) -> None:
    print(
        f"\nReceitas: R$ {report['total_income']:.2f} | Despesas: R$ {report['total_expense']:.2f} "
        f"| Saldo: R$ {report['net_balance']:.2f}"
    )
    if report["transfer_total"]:
        print(f"Transferências internas (fora do saldo): R$ {report['transfer_total']:.2f}")

    # Feature 012: shared-expense reimbursements. Values default to 0/absent when the
    # report was produced without netting (e.g. older graph projection).
    total_reimbursements = report.get("total_reimbursements", 0.0)
    if total_reimbursements:
        print(
            f"Reembolsos de despesas compartilhadas (abatidos das despesas): "
            f"R$ {total_reimbursements:.2f}"
        )
        unattributed = report.get("unattributed_reimbursements", 0.0)
        if unattributed:
            print(f"  não atribuídos a uma categoria: R$ {unattributed:.2f}")

    print("\nPor categoria:")
    for entry in report["category_breakdown"]:
        sign = "+" if entry["type"] == "income" else "-"
        reimbursed = entry.get("reimbursed", 0.0)
        if reimbursed:
            gross = entry.get("gross", entry["total"])
            print(
                f"  {sign} {entry['category']}: R$ {gross:.2f} bruto - "
                f"R$ {reimbursed:.2f} reembolso = R$ {entry['total']:.2f} líquido"
            )
        else:
            print(f"  {sign} {entry['category']}: R$ {entry['total']:.2f}")

    if report["budget_report"]:
        print("\nOrçamento:")
        for entry in report["budget_report"]:
            marker = "OK" if entry["status"] == "within_budget" else "ESTOUROU"
            print(
                f"  [{marker}] {entry['category']}: R$ {entry['actual_spend']:.2f} "
                f"de R$ {entry['goal']:.2f} (diferença: R$ {entry['difference']:.2f})"
            )

    if report["insights_summary"]:
        print(f"\n{report['insights_summary']}")
    elif report["insights_error"]:
        print(f"\n(Não foi possível gerar insights: {report['insights_error']})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="financial-planner",
        usage="financial-planner <month_ref> <extrato.csv> [extrato.csv ...] [--db PATH]",
    )
    parser.add_argument("month_ref", help="mês de referência, ex.: 2026-08")
    parser.add_argument(
        "statement_files",
        nargs="+",
        metavar="extrato.csv",
        help="um ou mais extratos bancários em CSV",
    )
    parser.add_argument(
        "--db",
        "--db-path",
        dest="db_path",
        default=os.environ.get("SQLITE_DB_PATH") or DEFAULT_DB_PATH,
        help="caminho do banco SQLite (padrão: $SQLITE_DB_PATH ou %(default)s)",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    run_month(args.month_ref, args.db_path, args.statement_files)


if __name__ == "__main__":
    main()
