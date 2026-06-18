"""L0 — page-kind classification (Requirement 2).

Labels each page LEGAL / ANNEXURE / RATE_CARD / ZONE_MAP / MIXED so that:
  * table extraction targets rate cards / annexures / zone maps,
  * metadata + clause extraction (L1.5) targets legal/text pages.

Deterministic keyword scoring, biased by the vendor profile's `page_keywords`.
Cheap, explainable, and good enough to *route*; precise table parsing happens
downstream. Genuine ambiguity falls through to MIXED (both paths run).
"""
from __future__ import annotations

import re

from app.core.enums import PageKind
from app.ingestion.pdf_loader import PageInfo

# Keyword signatures per page kind. Lowercased substring match.
_SIGNATURES: dict[PageKind, list[str]] = {
    PageKind.RATE_CARD: ["rate", "freight", "tariff", "charges", "per kg", "per box", "amount"],
    PageKind.ANNEXURE: ["annexure", "annexe", "schedule", "appendix"],
    PageKind.ZONE_MAP: ["zone", "state to zone", "zone mapping", "zone wise"],
    PageKind.LEGAL: [
        "agreement", "whereas", "indemnit", "liabilit", "terms and conditions",
        "payment terms", "insurance", "penalt", "fuel surcharge", "jurisdiction",
        "force majeure", "arbitration",
    ],
}

_NUM = re.compile(r"\d")


def classify_page(page: PageInfo, *, extra_keywords: list[str] | None = None) -> PageKind:
    """Return the most likely PageKind for a page."""
    text = (page.text or "").lower()
    if not text.strip():
        # No text layer -> scanned; assume it carries a rate table until proven
        # otherwise (the cheaper failure than skipping a rate card).
        return PageKind.RATE_CARD

    scores: dict[PageKind, int] = {k: 0 for k in _SIGNATURES}
    for kind, keywords in _SIGNATURES.items():
        for kw in keywords:
            if kw in text:
                scores[kind] += 1
    for kw in extra_keywords or []:
        kw = kw.lower()
        if kw in text:
            scores[PageKind.RATE_CARD] += 1  # profile hints point at rate content

    # Digit density nudges toward a rate/zone table vs prose.
    digit_ratio = sum(1 for ch in text if _NUM.match(ch)) / max(len(text), 1)

    best_kind = max(scores, key=lambda k: scores[k])
    best_score = scores[best_kind]

    if best_score == 0:
        return PageKind.MIXED

    # Strong legal signal + low digit density -> LEGAL (metadata path).
    if scores[PageKind.LEGAL] >= 2 and digit_ratio < 0.05:
        return PageKind.LEGAL

    # Tie between a table-kind and legal -> MIXED so both pipelines inspect it.
    table_kinds = (PageKind.RATE_CARD, PageKind.ANNEXURE, PageKind.ZONE_MAP)
    if best_kind in table_kinds and scores[PageKind.LEGAL] >= best_score:
        return PageKind.MIXED

    return best_kind
