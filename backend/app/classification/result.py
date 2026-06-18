"""ClassificationResult — the L2 output contract.

Carries the chosen pattern, a numeric confidence + derived band (Enhancement #4),
the tier that decided it (for auditability), a human-readable reason (feeds the
AI-explanation layer, Enhancement #6), and a column_mapping the normalizer (L4)
uses to read the table.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.confidence import to_band
from app.core.enums import ConfidenceBand, PricingPattern


class ClassificationResult(BaseModel):
    pattern: PricingPattern
    confidence: float
    tier: str = "rules"          # "fingerprint" | "rules" | "ai"
    reason: str = ""
    column_mapping: dict = Field(default_factory=dict)  # logical field -> col index
    runner_up: PricingPattern | None = None
    margin: float = 0.0          # gap between top-2 scores; low margin -> AI tiebreak

    @property
    def band(self) -> ConfidenceBand:
        return to_band(self.confidence)
