"""Build a minimal single-page PDF with a real text layer from plain lines.

Pure stdlib — no reportlab. Used to turn the committed anonymized ``*_fatura.txt``
fixtures into actual PDF files at test time, so the detection + ingestion routing
path (extension sniff -> pdfplumber text extraction -> issuer match -> adapter) is
exercised end to end without committing a binary blob.

``leading_nul`` reproduces the NUL-padding corruption seen on a real Inter fatura
download (``parsers.pdf_text`` strips it before parsing).
"""

from __future__ import annotations

from pathlib import Path


def build_pdf_bytes(lines: list[str], *, leading_nul: int = 0) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    parts = ["BT", "/F1 10 Tf", "12 TL", "40 800 Td"]
    for ln in lines:
        parts.append(f"({esc(ln)}) Tj")
        parts.append("T*")
    parts.append("ET")
    stream = "\n".join(parts).encode("latin-1", "replace")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]

    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, body)
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        xref_pos,
    )
    return (b"\x00" * leading_nul) + out


def write_pdf(dest: str | Path, text: str, *, leading_nul: int = 0) -> str:
    dest = Path(dest)
    dest.write_bytes(build_pdf_bytes(text.splitlines(), leading_nul=leading_nul))
    return str(dest)
