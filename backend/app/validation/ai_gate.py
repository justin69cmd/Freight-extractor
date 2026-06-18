"""Layer 3 — the AI validation gate (gated, budgeted, no-fabrication).

Deterministic detection decides whether AI is needed at all (gates G1/G2); AI is
invoked only when a gate trips AND the per-job budget allows. The model may only
repair the suspect cells it is shown, transcribing from the visible table — it
must return "uncertain" rather than invent a value. Every repaired table is
marked ai_touched with an explanation (Enhancement #6).

  G1  low-OCR     : a price/number cell below the OCR confidence floor
  G2  ambiguous   : classifier confidence not HIGH (structure unclear)
  G3  schema-fail : handled deterministically in schema_validator (post-normalize)
  G4  zone-unmap  : handled in zone_resolver (kept + flagged)

This module owns G1/G2 (table-level cell/structure repair).
"""
from __future__ import annotations

import logging

from app.classification.result import ClassificationResult
from app.config import settings
from app.core.confidence import to_band
from app.core.enums import ConfidenceBand
from app.core.exceptions import AIValidationError
from app.extraction.raw_table import RawTable
from app.validation.llm_adapter import llm
from app.validation.result import CellEdit, ValidationResult

log = logging.getLogger("freight.ai_gate")

_OCR_FLOOR = 0.80  # numeric cells below this trip G1

_SYSTEM = (
    "You repair cells in a freight-rate table that were extracted with low OCR "
    "confidence. You are given the full table grid and a list of suspect cells "
    "(row,col). Return corrected text for ONLY those cells, reading from the "
    "visible table context. STRICT RULES: never invent values; if you cannot read "
    "a cell with confidence, return its value as \"uncertain\"; preserve numbers "
    "exactly; do not change any cell not listed. Respond as JSON: "
    '{"cells": [{"row": int, "col": int, "value": "..."}], "explanation": "..."}'
)


def detect_gates(table: RawTable, classification: ClassificationResult) -> list[str]:
    """Deterministically decide which gates trip — no AI cost here."""
    gates: list[str] = []
    if table.low_confidence_numeric_cells(_OCR_FLOOR):
        gates.append("G1")
    if to_band(classification.confidence) is not ConfidenceBand.HIGH:
        gates.append("G2")
    return gates


def validate_table(
    table: RawTable,
    classification: ClassificationResult,
    *,
    ai_budget: list[int] | None = None,
) -> ValidationResult:
    """Run the gate. Returns a (possibly repaired) grid + provenance."""
    grid = table.grid()
    gates = detect_gates(table, classification)

    # Nothing to do, or no budget -> return the grid unchanged (still flagged
    # downstream by band if low).
    if "G1" not in gates or not _budget_ok(ai_budget):
        return ValidationResult(grid=grid, gates=gates, ai_touched=False)

    suspects = table.low_confidence_numeric_cells(_OCR_FLOOR)
    suspect_coords = [{"row": c.row, "col": c.col} for c in suspects]
    user = (
        "Table (row-major):\n"
        + "\n".join(" | ".join(cell for cell in row) for row in grid)
        + f"\n\nSuspect cells: {suspect_coords}"
    )

    try:
        data = llm.complete_json(
            system=_SYSTEM, user=user, model=settings.ai_model_validation, max_tokens=600
        )
        _spend(ai_budget)
    except AIValidationError as exc:
        log.warning("AI gate repair failed (%s); leaving table flagged", exc)
        return ValidationResult(grid=grid, gates=gates, ai_touched=False)

    edits = _apply_edits(grid, data.get("cells", []))
    if not edits:
        return ValidationResult(grid=grid, gates=gates, ai_touched=False,
                                explanation=data.get("explanation"))
    return ValidationResult(
        grid=grid,
        gates=gates,
        ai_touched=True,
        explanation=(data.get("explanation") or "AI repaired low-confidence cells")[:500],
        edits=edits,
        new_confidence=0.9,  # repaired cells lift the table out of LOW
    )


def _apply_edits(grid: list[list[str]], cells: list[dict]) -> list[CellEdit]:
    edits: list[CellEdit] = []
    for c in cells:
        try:
            r, col = int(c["row"]), int(c["col"])
            new = str(c["value"])
        except (KeyError, ValueError, TypeError):
            continue
        if new.lower() == "uncertain":
            continue  # model declined to guess -> leave for human review
        if 0 <= r < len(grid) and 0 <= col < len(grid[r]):
            old = grid[r][col]
            if old != new:
                grid[r][col] = new
                edits.append(CellEdit(row=r, col=col, old=old, new=new))
    return edits


def _budget_ok(budget: list[int] | None) -> bool:
    return budget is None or budget[0] > 0


def _spend(budget: list[int] | None) -> None:
    if budget is not None and budget[0] > 0:
        budget[0] -= 1
