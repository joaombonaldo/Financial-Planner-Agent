"""PDF text-layer extraction for credit-card fatura parsing (feature 013).

Same philosophy as the CSV adapters: pull the raw text out, then let a per-bank
adapter filter rows with a transaction regex — only matching lines become
transactions. Nothing here interprets a fatura; it just yields text.

Two real-world quirks handled here:

- **Leading NUL padding.** One of the sample Inter faturas is a valid PDF preceded
  by ~430 KB of ``0x00`` bytes (a save/download artifact). pdfminer refuses it with
  "No /Root object". Stripping leading NULs recovers a byte-identical, parseable
  PDF, so we always do that before handing the bytes to pdfplumber.
- **Password-protected PDFs.** If a bank ever ships an encrypted fatura, the
  password is read from an env var (never a CLI arg / never logged): the per-bank
  ``CREDIT_CARD_PDF_PASSWORD_BRADESCO`` / ``CREDIT_CARD_PDF_PASSWORD_INTER`` first,
  then the shared ``CREDIT_CARD_PDF_PASSWORD``. Neither sample PDF is encrypted.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pdfplumber

_PASSWORD_ENV_SHARED = "CREDIT_CARD_PDF_PASSWORD"


def _password(bank_hint: str | None) -> str | None:
    if bank_hint:
        per_bank = os.environ.get(f"{_PASSWORD_ENV_SHARED}_{bank_hint.upper()}")
        if per_bank:
            return per_bank
    return os.environ.get(_PASSWORD_ENV_SHARED) or None


def _load_bytes(path: str) -> io.BytesIO:
    raw = Path(path).read_bytes()
    # A well-formed PDF starts with "%PDF"; anything before it is padding.
    marker = raw.find(b"%PDF")
    if marker > 0:
        raw = raw[marker:]
    return io.BytesIO(raw)


def extract_pages(path: str, *, bank_hint: str | None = None) -> list[str]:
    """Return the text layer of each page, in document order."""
    stream = _load_bytes(path)
    with pdfplumber.open(stream, password=_password(bank_hint) or "") as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def extract_text(path: str, *, bank_hint: str | None = None) -> str:
    """Whole-document text, pages joined by a newline."""
    return "\n".join(extract_pages(path, bank_hint=bank_hint))


def extract_left_column_pages(
    path: str, *, x_max: float, bank_hint: str | None = None
) -> list[str]:
    """Per-page text rebuilt from only the words left of ``x_max``.

    Bradesco's fatura prints the transaction list on the left and an unrelated
    rates/limits table on the right at the same vertical positions, so a plain
    ``extract_text()`` interleaves the two. Filtering words by x-coordinate first
    keeps the transaction rows clean.
    """
    stream = _load_bytes(path)
    out: list[str] = []
    with pdfplumber.open(stream, password=_password(bank_hint) or "") as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True)
            rows: dict[int, list[dict]] = {}
            for w in words:
                if w["x0"] >= x_max:
                    continue
                rows.setdefault(round(w["top"] / 3.0), []).append(w)
            lines = []
            for top in sorted(rows):
                ordered = sorted(rows[top], key=lambda w: w["x0"])
                lines.append(" ".join(w["text"] for w in ordered))
            out.append("\n".join(lines))
    return out
