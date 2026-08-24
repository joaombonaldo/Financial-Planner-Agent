"""Swappable source of budget goals (BRD 5.5).

Phase 1: a local YAML file. Phase 2 swaps this function's implementation to read from
a hosted database, without changing nodes/budget.py at all (Principle IV).
"""

from pathlib import Path

import yaml

from financial_planner.state import BudgetNotConfiguredError

_DEFAULT_PATH = Path(__file__).parent.parent / "config" / "budget.local.yaml"


def get_budget(path: Path | str | None = None) -> dict[str, float]:
    budget_path = Path(path) if path is not None else _DEFAULT_PATH

    if not budget_path.exists():
        raise BudgetNotConfiguredError(
            f"No budget configuration found at {budget_path}. "
            "Copy config/budget.example.yaml to config/budget.local.yaml and set your goals."
        )

    raw = yaml.safe_load(budget_path.read_text(encoding="utf-8"))
    return raw or {}
