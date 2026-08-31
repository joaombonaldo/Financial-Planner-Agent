import pytest

from financial_planner.interface.cli import DEFAULT_DB_PATH, _build_parser


def test_parses_valid_arg_list():
    args = _build_parser().parse_args(
        ["2026-08", "bradesco.csv", "inter.csv", "--db", "/tmp/fp.db"]
    )

    assert args.month_ref == "2026-08"
    assert args.statement_files == ["bradesco.csv", "inter.csv"]
    assert args.db_path == "/tmp/fp.db"


def test_db_path_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)

    args = _build_parser().parse_args(["2026-08", "bradesco.csv"])

    assert args.db_path == DEFAULT_DB_PATH


def test_db_path_defaults_to_env(monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", "/env/fp.db")

    args = _build_parser().parse_args(["2026-08", "bradesco.csv"])

    assert args.db_path == "/env/fp.db"


def test_errors_on_missing_statement_files():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["2026-08"])
