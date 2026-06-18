"""Validation result contracts (Layer 3)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CellEdit(BaseModel):
    row: int
    col: int
    old: str
    new: str


class ValidationResult(BaseModel):
    """Outcome of the AI gate for one table."""
    grid: list[list[str]]                 # possibly-repaired grid
    gates: list[str] = Field(default_factory=list)   # which gates tripped
    ai_touched: bool = False
    explanation: str | None = None
    edits: list[CellEdit] = Field(default_factory=list)
    new_confidence: float | None = None   # uplift after a successful repair


class RowViolation(BaseModel):
    """A deterministic schema-validation failure (gate G3)."""
    index: int
    field: str
    reason: str
