"""L2 Tier-0 — table fingerprint learning store (Enhancement #5).

A vendor-scoped lookup: fingerprint -> (pattern, column_mapping). A hit lets the
classifier skip rules + AI entirely and reuse a known layout. Human review
corrections promote a fingerprint to `human_verified=True`, so the system gets
both cheaper and more accurate the more a vendor's documents flow through it.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canonical.models import TableFingerprint
from app.classification.result import ClassificationResult
from app.core.enums import PricingPattern


def lookup(
    db: Session, *, vendor_id: uuid.UUID | None, fingerprint: str
) -> ClassificationResult | None:
    """Return a cached classification for a known layout, or None."""
    row = db.scalar(
        select(TableFingerprint).where(
            TableFingerprint.vendor_id == vendor_id,
            TableFingerprint.fingerprint == fingerprint,
        )
    )
    if row is None:
        return None

    row.hit_count += 1
    db.add(row)
    db.flush()

    # A human-verified layout is trusted outright; an auto-learned one is high
    # but not certain.
    confidence = 0.99 if row.human_verified else 0.92
    return ClassificationResult(
        pattern=row.pattern,
        confidence=confidence,
        tier="fingerprint",
        reason=f"fingerprint hit (hits={row.hit_count}, "
               f"{'human-verified' if row.human_verified else 'learned'})",
        column_mapping=row.column_mapping or {},
    )


def learn(
    db: Session,
    *,
    vendor_id: uuid.UUID | None,
    fingerprint: str,
    result: ClassificationResult,
    header_signature: list | None = None,
    human_verified: bool = False,
) -> TableFingerprint:
    """Record (or upgrade) a fingerprint->pattern mapping.

    Called after a confident rules/AI classification, and again from the review
    workflow when a human corrects a table (with human_verified=True), which
    overwrites the learned pattern/mapping.
    """
    row = db.scalar(
        select(TableFingerprint).where(
            TableFingerprint.vendor_id == vendor_id,
            TableFingerprint.fingerprint == fingerprint,
        )
    )
    if row is None:
        row = TableFingerprint(
            vendor_id=vendor_id,
            fingerprint=fingerprint,
            pattern=result.pattern,
            column_mapping=result.column_mapping,
            header_signature=header_signature,
            hit_count=1,
            human_verified=human_verified,
        )
        db.add(row)
    else:
        # Human verification always wins; otherwise don't downgrade a verified row.
        if human_verified or not row.human_verified:
            row.pattern = result.pattern
            row.column_mapping = result.column_mapping
            row.human_verified = row.human_verified or human_verified
        db.add(row)
    db.flush()
    return row


def should_learn(result: ClassificationResult) -> bool:
    """Only memorialize confident, non-UNKNOWN classifications."""
    return result.pattern is not PricingPattern.UNKNOWN and result.confidence >= 0.85
