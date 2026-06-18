"""Confidence-band logic (Enhancement #4).

Single source of truth for turning a numeric confidence into a HIGH/MEDIUM/LOW
band and deciding what the pipeline should do next. Thresholds come from settings,
never hardcoded at call sites.
"""
from __future__ import annotations

from app.config import settings
from app.core.enums import ConfidenceBand


def to_band(confidence: float) -> ConfidenceBand:
    """Map numeric confidence [0,1] -> categorical band."""
    if confidence >= settings.band_high_min:
        return ConfidenceBand.HIGH
    if confidence >= settings.band_medium_min:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def needs_ai_validation(band: ConfidenceBand) -> bool:
    """MEDIUM-band items go through the AI validation gate (Layer 3)."""
    return band is ConfidenceBand.MEDIUM


def needs_human_review(band: ConfidenceBand, ai_touched: bool) -> bool:
    """Enhancement #2 — decide whether an item must be human-reviewed before export."""
    if band.value in settings.review_required_bands:
        return True
    if ai_touched and settings.review_required_if_ai_touched:
        return True
    return False
