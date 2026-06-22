"""L1 — extraction router.

Picks the extraction path per page from the L0 digital/scanned decision, tags
each resulting RawTable with its page kind, and stamps the structural
fingerprint (Enhancement #5). This is the single entry point the pipeline calls.
"""
from __future__ import annotations

import logging

from app.core.enums import PageKind
from app.core.exceptions import ExtractionError
from app.extraction.digital_extractor import extract_digital_tables
from app.extraction.ocr_extractor import extract_scanned_tables
from app.extraction.raw_table import RawTable
from app.ingestion.page_classifier import classify_page
from app.ingestion.pdf_loader import LoadedDocument

log = logging.getLogger("freight.extractor")

# Page kinds that carry pricing tables worth extracting.
_TABLE_PAGE_KINDS = {PageKind.RATE_CARD, PageKind.ANNEXURE, PageKind.ZONE_MAP, PageKind.MIXED}


def extract_tables(
    doc: LoadedDocument, *, profile_keywords: list[str] | None = None
) -> list[RawTable]:
    """Extract all candidate pricing tables from a loaded document."""
    tables: list[RawTable] = []
    for page in doc.pages:
        kind = classify_page(page, extra_keywords=profile_keywords)

        if page.is_digital:
            # Digital extraction is cheap and returns [] when there's no table, so
            # always attempt it — a rate table that shares a page with legal text
            # (common in single-page agreements) must never be skipped.
            page_tables = extract_digital_tables(doc.path, page.number)
        elif kind in _TABLE_PAGE_KINDS:
            # OCR is expensive; only run it on pages that look like rate content.
            # In slim local mode the OCR libs may be absent — skip the page with a
            # warning rather than failing the whole job.
            try:
                page_tables = extract_scanned_tables(doc.path, page.number)
            except ExtractionError as exc:
                log.warning("skipping scanned page %d (OCR unavailable): %s", page.number, exc)
                page_tables = []
        else:
            page_tables = []

        for t in page_tables:
            t.page_kind = kind
            tables.append(t)
    return tables
