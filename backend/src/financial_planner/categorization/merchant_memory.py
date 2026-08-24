"""Normalização de merchant key e leitura da memória confirmada.

Esta feature só lê merchant_memory (via db/repository.py) — gravar novas confirmações é
responsabilidade de uma feature futura (update_memory).
"""

import sqlite3

from financial_planner.db import repository


def normalize_merchant_key(description_raw: str) -> str:
    return description_raw.strip().lower()


def lookup(conn: sqlite3.Connection, description_raw: str) -> tuple[str, str | None] | None:
    merchant_key = normalize_merchant_key(description_raw)
    return repository.get_merchant_category(conn, merchant_key)
