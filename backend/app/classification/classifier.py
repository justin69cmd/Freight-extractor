"""L2 — classification orchestrator (tiers the strategy from §6).

Order:
  Tier-0 fingerprint cache  -> reuse a learned layout (no compute).
  Tier-1 deterministic rules -> covers ~80%.
  Tier-3 AI tiebreak         -> ONLY when rules are ambiguous AND budget remains.
After a confident decision, the layout is memorialized in the fingerprint store
so the next identical table is free.

The AI gate condition (Enhancement #4 driven): rules confidence lands in the
MEDIUM/LOW band OR the top-2 margin is thin. AI is never called on a clear HIGH.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.classification import fingerprint_store as fp
from app.classification.ai_classifier import classify_ai
from app.classification.result import ClassificationResult
from app.classification.rule_classifier import classify_rules
from app.config import settings
from app.core.confidence import to_band
from app.core.enums import ConfidenceBand, PricingPattern
from app.core.exceptions import AIValidationError
from app.extraction.raw_table import RawTable

log = logging.getLogger("freight.classify")

# Below this top-2 margin the rule result is considered ambiguous -> AI tiebreak.
_AMBIGUOUS_MARGIN = 1.5


def classify_table(
    db: Session,
    table: RawTable,
    *,
    vendor_id: uuid.UUID | None = None,
    ai_budget: list[int] | None = None,  # mutable [remaining] shared across a job
) -> ClassificationResult:
    """Classify one table through the tier ladder; learns the layout on success."""
    fingerprint = table.fingerprint()

    # --- Tier 0: learned layout ------------------------------------------- #
    cached = fp.lookup(db, vendor_id=vendor_id, fingerprint=fingerprint)
    if cached is not None:
        log.debug("fingerprint hit %s -> %s", fingerprint, cached.pattern.value)
        return cached

    # --- Tier 1: deterministic rules -------------------------------------- #
    result = classify_rules(table)
    band = to_band(result.confidence)
    ambiguous = band is not ConfidenceBand.HIGH or result.margin < _AMBIGUOUS_MARGIN

    # --- Tier 3: AI tiebreak (gated + budgeted) --------------------------- #
    if ambiguous and _budget_ok(ai_budget):
        try:
            ai_result = classify_ai(table)
            _spend(ai_budget)
            # Trust AI when it is confident, or when rules produced nothing.
            if ai_result.pattern is not PricingPattern.UNKNOWN and (
                ai_result.confidence >= result.confidence
                or result.pattern is PricingPattern.UNKNOWN
            ):
                ai_result.column_mapping = ai_result.column_mapping or result.column_mapping
                result = ai_result
        except AIValidationError as exc:
            log.warning("AI tiebreak failed (%s); keeping rule result", exc)

    # --- learn confident decisions ---------------------------------------- #
    if fp.should_learn(result):
        fp.learn(
            db,
            vendor_id=vendor_id,
            fingerprint=fingerprint,
            result=result,
            header_signature=table.header_tokens(),
        )
    return result


def _budget_ok(budget: list[int] | None) -> bool:
    if budget is None:
        return True  # uncapped (e.g. unit context)
    return budget[0] > 0


def _spend(budget: list[int] | None) -> None:
    if budget is not None and budget[0] > 0:
        budget[0] -= 1
