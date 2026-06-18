"""Typed exception hierarchy — one class per pipeline layer.

Lets the orchestrator degrade gracefully: a failure in one stage flags the
affected unit and continues, rather than crashing the whole job (see §17).
"""
from __future__ import annotations


class FreightError(Exception):
    """Base for all domain errors."""


class IngestionError(FreightError):
    """L0 — could not load / segment the PDF."""


class ExtractionError(FreightError):
    """L1 — table or text extraction failed for a page."""


class MetadataExtractionError(FreightError):
    """L1.5 — agreement metadata / clause extraction failed."""


class ClassificationError(FreightError):
    """L2 — pricing pattern could not be determined."""


class AIValidationError(FreightError):
    """L3 — AI gate failed or returned unparseable output."""


class NormalizationError(FreightError):
    """L4 — could not map an extracted table to the canonical model."""


class RouteExpansionError(FreightError):
    """L4 — Cartesian expansion produced an invalid/over-sized lane set."""


class ReviewBlockedError(FreightError):
    """L6 attempted while items still await human review (Enhancement #2)."""


class ExportError(FreightError):
    """L6 — Excel generation failed."""
