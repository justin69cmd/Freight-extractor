"""RawTable — the typed contract between extraction (L1) and classification (L2).

Carries the cell grid plus everything needed for traceability (Enhancement #6)
and confidence routing (Enhancement #4): per-cell confidences, bbox, page,
and the structural fingerprint used for pattern learning (Enhancement #5).
"""
from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, Field

from app.core.confidence import to_band
from app.core.enums import ConfidenceBand, PageKind

# digits + separators + characters OCR commonly confuses with digits
_NUMERIC_ISH_ALLOWED = set("0123456789.,/-₹rs ") | set("OolISBg")


def _is_numeric_ish(text: str | None) -> bool:
    t = (text or "").strip()
    if not t or not any(ch.isdigit() for ch in t):
        return False
    return all(ch in _NUMERIC_ISH_ALLOWED or ch.isdigit() for ch in t)


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class RawCell(BaseModel):
    row: int
    col: int
    text: str = ""
    confidence: float = 1.0  # 1.0 for born-digital text; OCR conf for scanned
    bbox: BBox | None = None


class RawTable(BaseModel):
    """A single extracted table, source-agnostic (digital or OCR)."""

    page_number: int
    page_kind: PageKind = PageKind.RATE_CARD
    bbox: BBox | None = None
    cells: list[RawCell] = Field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    source: str = "digital"  # "digital" | "ocr"

    # --- derived trust signals ---
    @property
    def extraction_confidence(self) -> float:
        """Table-level confidence = min over numeric/price-bearing cells is too harsh;
        use the mean of cell confidences, but the orchestrator separately escalates
        any *individual* low-confidence numeric cell to the AI gate."""
        if not self.cells:
            return 0.0
        return sum(c.confidence for c in self.cells) / len(self.cells)

    @property
    def confidence_band(self) -> ConfidenceBand:
        return to_band(self.extraction_confidence)

    def low_confidence_numeric_cells(self, threshold: float = 0.80) -> list[RawCell]:
        """Price/number cells below threshold — these force AI validation / review.

        Deliberately permissive: a *garbled* number like '125OO' (OCR read 0 as O)
        is exactly what gate G1 must catch, so we accept cells that contain a digit
        and are otherwise only separators or common OCR letter-confusions
        (O/o, l/I, S, B, g) — not just already-clean numbers.
        """
        return [c for c in self.cells if c.confidence < threshold and _is_numeric_ish(c.text)]

    def grid(self) -> list[list[str]]:
        """Dense 2D text grid (for classifiers / persistence)."""
        g = [["" for _ in range(self.n_cols)] for _ in range(self.n_rows)]
        for c in self.cells:
            if 0 <= c.row < self.n_rows and 0 <= c.col < self.n_cols:
                g[c.row][c.col] = c.text
        return g

    def header_tokens(self) -> list[str]:
        """First non-empty row, normalized — the basis of the fingerprint."""
        for r in self.grid():
            if any(cell.strip() for cell in r):
                return [re.sub(r"\s+", " ", cell.strip().lower()) for cell in r]
        return []

    def fingerprint(self) -> str:
        """Enhancement #5 — structural hash: header tokens + shape + source.

        Stable across documents with the same layout, so a known vendor table
        skips classification + AI on future uploads.
        """
        sig = {
            "headers": self.header_tokens(),
            "shape": (self.n_rows, self.n_cols),
            "source": self.source,
        }
        blob = json.dumps(sig, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]
