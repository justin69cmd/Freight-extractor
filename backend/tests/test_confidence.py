"""Confidence-band logic — pure, no DB needed (Enhancement #4)."""
from app.core.confidence import needs_ai_validation, needs_human_review, to_band
from app.core.enums import ConfidenceBand


def test_band_thresholds():
    assert to_band(0.95) is ConfidenceBand.HIGH
    assert to_band(0.90) is ConfidenceBand.HIGH
    assert to_band(0.80) is ConfidenceBand.MEDIUM
    assert to_band(0.75) is ConfidenceBand.MEDIUM
    assert to_band(0.50) is ConfidenceBand.LOW


def test_medium_goes_to_ai():
    assert needs_ai_validation(ConfidenceBand.MEDIUM)
    assert not needs_ai_validation(ConfidenceBand.HIGH)


def test_low_or_ai_touched_needs_review():
    assert needs_human_review(ConfidenceBand.LOW, ai_touched=False)
    assert needs_human_review(ConfidenceBand.HIGH, ai_touched=True)
    assert not needs_human_review(ConfidenceBand.HIGH, ai_touched=False)
