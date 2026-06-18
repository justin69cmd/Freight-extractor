"""L1.5 — agreement metadata extraction (Enhancement #1).

Pulls vendor name, effective/expiry dates, and a payment-terms summary from the
legal pages. Date parsing is conservative — an unparseable date stays None and
the field is flagged for review rather than guessed.
"""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from app.metadata.clause_extractor import ClauseRow, extract_clauses

_MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], start=1
    )
}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})

_EFFECTIVE_RE = re.compile(r"(?:effective\s*(?:date|from)|valid\s*from|w\.?e\.?f\.?|commenc\w*)\s*[:\-]?\s*(.{0,30})", re.I)
_EXPIRY_RE = re.compile(r"(?:expir\w*|valid\s*(?:up\s*to|until|till)|end\s*date|terminat\w*)\s*[:\-]?\s*(.{0,30})", re.I)
_VENDOR_RE = re.compile(r"(?:between|m/s\.?|messrs\.?|transporter[:\-]?|vendor[:\-]?|carrier[:\-]?)\s*([A-Z][A-Za-z0-9 &.\-]{2,60})", re.I)
_PAYMENT_RE = re.compile(r"(payment\s*terms?.{0,160}|credit\s*period.{0,120}|payable within.{0,120})", re.I)

_DATE_DMY = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_DATE_WORDS = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)[,\s]+(\d{4})\b")


class MetadataResult(BaseModel):
    vendor_name: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    payment_terms: str | None = None
    clauses: list[ClauseRow] = []
    source_page: int | None = None
    extraction_confidence: float = 0.8


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    m = _DATE_DMY.search(text)
    if m:
        d, mo, y = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        y = y + 2000 if y < 100 else y
        return _safe_date(y, mo, d)
    m = _DATE_WORDS.search(text)
    if m:
        d, mon, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mo = _MONTHS.get(mon) or _MONTHS.get(mon[:3])
        if mo:
            return _safe_date(y, mo, d)
    return None


def extract_metadata(legal_pages: list[tuple[int, str]]) -> MetadataResult:
    """legal_pages: list of (page_number, text) for LEGAL/MIXED pages."""
    result = MetadataResult()
    all_clauses: list[ClauseRow] = []
    blob_parts: list[str] = []

    for page_no, text in legal_pages:
        blob_parts.append(text or "")
        all_clauses.extend(extract_clauses(page_no, text or ""))
        if result.source_page is None:
            result.source_page = page_no

    blob = "\n".join(blob_parts)

    if (m := _VENDOR_RE.search(blob)):
        result.vendor_name = m.group(1).strip().rstrip(".,")
    if (m := _EFFECTIVE_RE.search(blob)):
        result.effective_date = parse_date(m.group(1))
    if (m := _EXPIRY_RE.search(blob)):
        result.expiry_date = parse_date(m.group(1))
    if (m := _PAYMENT_RE.search(blob)):
        result.payment_terms = re.sub(r"\s+", " ", m.group(1)).strip()[:500]

    result.clauses = all_clauses
    return result


def _safe_date(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None
