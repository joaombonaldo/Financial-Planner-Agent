"""Schema tipado de domínio compartilhado pelos nodes do grafo.

Esta feature (detect_and_parse) só preenche o subconjunto de campos de Transacao
documentado em specs/001-ingest-extratos/data-model.md. category, subcategory,
confidence e installment_id ficam None/NULL até features futuras (categorize, etc.).
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
    """Levantado quando um arquivo de extrato não corresponde a nenhum banco suportado."""
