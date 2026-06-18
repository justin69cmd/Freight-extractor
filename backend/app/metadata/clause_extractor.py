"""L1.5 — clause extraction (Enhancement #1).

Deterministic-first: locate clause paragraphs on LEGAL/MIXED pages by keyword,
capturing the surrounding sentence block as the clause text. Stored separate
from freight rates, each clause individually traceable to its page.

The AI gate (Phase 7) can later summarize/clean a low-confidence clause, but the
text itself is always lifted verbatim from the document — never fabricated.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.core.enums import ClauseType

# Trigger keywords per clause type. First match wins the paragraph's label.
_CLAUSE_TRIGGERS: list[tuple[ClauseType, re.Pattern]] = [
    (ClauseType.FUEL, re.compile(r"\bfuel\s*(surcharge|adjustment|clause|escalation)\b|\bfsc\b", re.I)),
    (ClauseType.INSURANCE, re.compile(r"\binsurance\b|\btransit\s*insurance\b|\bin\s*transit\s*cover\b", re.I)),
    (ClauseType.PENALTY, re.compile(r"\bpenalt(y|ies)\b|\bliquidated damages\b|\bdelay\s*charge", re.I)),
    (ClauseType.PAYMENT_TERMS, re.compile(r"\bpayment\s*terms?\b|\bcredit\s*period\b|\bpayable within\b", re.I)),
]


class ClauseRow(BaseModel):
    clause_type: ClauseType
    text: str
    summary: str | None = None
    source_page: int | None = None
    extraction_confidence: float = 1.0


def _paragraphs(text: str) -> list[str]:
    # split on blank lines or numbered-clause boundaries
    blocks = re.split(r"\n\s*\n|(?:\n(?=\d+\.\s))", text)
    return [re.sub(r"\s+", " ", b).strip() for b in blocks if b and b.strip()]


def extract_clauses(page_number: int, page_text: str) -> list[ClauseRow]:
    """Find clause paragraphs on one page. A paragraph maps to its first trigger."""
    rows: list[ClauseRow] = []
    seen: set[tuple[ClauseType, str]] = set()
    for para in _paragraphs(page_text or ""):
        for ctype, pattern in _CLAUSE_TRIGGERS:
            if pattern.search(para):
                key = (ctype, para[:80])
                if key in seen:
                    break
                seen.add(key)
                # confidence: longer, keyword-rich paragraphs are more reliable
                conf = 0.9 if len(para) > 60 else 0.7
                rows.append(
                    ClauseRow(
                        clause_type=ctype,
                        text=para[:2000],
                        source_page=page_number,
                        extraction_confidence=conf,
                    )
                )
                break  # one label per paragraph
    return rows
