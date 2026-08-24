"""Typed domain schema shared by the graph's nodes.

This feature (detect_and_parse) only fills in the subset of Transaction fields
documented in specs/001-ingest-extratos/data-model.md. category, subcategory,
confidence, and installment_id stay None/NULL until later features (categorize, etc.).
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Bank(str, Enum):
    BRADESCO = "bradesco"
    INTER = "inter"


class BalanceReconciliation(str, Enum):
    OK = "ok"
    MISMATCH = "mismatch"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class Transaction:
    dedup_hash: str
    date: date
    description_raw: str
    account: Bank
    type: TransactionType
    amount: float
    month_ref: str
    category: str | None = None
    subcategory: str | None = None
    confidence: str | None = None
    installment_id: int | None = None


@dataclass
class ImportResult:
    bank: Bank
    source_file: str
    transactions_imported: int = 0
    transactions_skipped_duplicate: int = 0
    balance_reconciliation: BalanceReconciliation = BalanceReconciliation.NOT_AVAILABLE
    warnings: list[str] = field(default_factory=list)


class UnrecognizedBankError(Exception):
    """Raised when a statement file doesn't match any supported bank."""


class BudgetStatus(str, Enum):
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"


@dataclass
class CategoryComparison:
    category: str
    goal: float
    actual_spend: float
    difference: float
    status: BudgetStatus


class BudgetNotConfiguredError(Exception):
    """Raised when no local budget configuration file exists."""


@dataclass
class InsightsResult:
    summary: str | None = None
    error: str | None = None


@dataclass
class CategoryBreakdownEntry:
    category: str
    type: TransactionType
    total: float


@dataclass
class MonthlyReport:
    month_ref: str
    total_income: float
    total_expense: float
    net_balance: float
    transfer_total: float
    category_breakdown: list[CategoryBreakdownEntry] = field(default_factory=list)
    transaction_count: int = 0
    budget_report: list[dict] = field(default_factory=list)
    insights_summary: str | None = None
    insights_error: str | None = None
