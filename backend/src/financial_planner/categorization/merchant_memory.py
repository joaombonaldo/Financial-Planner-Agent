"""Merchant key normalization and reading of confirmed memory.

This feature only reads merchant_memory (via db/repository.py) — writing new
confirmations is a future feature's responsibility (update_memory).
"""

import sqlite3

from financial_planner.db import repository


def normalize_merchant_key(description_raw: str) -> str:
    return description_raw.strip().lower()


def lookup(conn: sqlite3.Connection, description_raw: str) -> tuple[str, str | None] | None:
    merchant_key = normalize_merchant_key(description_raw)
    return repository.get_merchant_category(conn, merchant_key)
