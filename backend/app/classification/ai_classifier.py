"""L2 Tier-3 — AI tiebreak (gated, cached).

Invoked ONLY when the rule classifier is ambiguous (low margin / low confidence).
The LLM is given the table grid and the fixed 9-label taxonomy and must pick one
label + reason — it never invents a 10th label and never fabricates data. Results
are cached by fingerprint upstream, so identical layouts never re-pay.
"""
from __future__ import annotations

from app.classification.result import ClassificationResult
from app.config import settings
from app.core.enums import PricingPattern
from app.core.exceptions import AIValidationError
from app.extraction.raw_table import RawTable
from app.validation.llm_adapter import llm

_LABELS = [p.value for p in PricingPattern if p != PricingPattern.UNKNOWN]

_SYSTEM = (
    "You are a freight-agreement table classifier. You are given a table extracted "
    "from a logistics pricing agreement. Classify it into EXACTLY ONE of these "
    f"pricing-structure labels: {_LABELS}. "
    "Rules: choose only from the provided labels; never invent a label; if the table "
    "is not a pricing/zone table, use UNKNOWN. Do NOT fabricate or transcribe cell "
    "values. Respond as JSON: "
    '{"pattern": "<LABEL>", "confidence": <0..1>, "reason": "<short>"}'
)


def classify_ai(table: RawTable) -> ClassificationResult:
    grid = table.grid()
    # keep the prompt bounded: header + up to 12 body rows
    preview = grid[:13]
    user = (
        "Table (row-major, first row is likely the header):\n"
        + "\n".join(" | ".join(cell for cell in row) for row in preview)
    )
    data = llm.complete_json(
        system=_SYSTEM, user=user, model=settings.ai_model_classify, max_tokens=300
    )

    label = str(data.get("pattern", "")).upper()
    if label not in _LABELS and label != "UNKNOWN":
        raise AIValidationError(f"AI returned out-of-taxonomy label {label!r}")

    pattern = PricingPattern(label) if label in {*_LABELS, "UNKNOWN"} else PricingPattern.UNKNOWN
    confidence = float(data.get("confidence", 0.7))
    return ClassificationResult(
        pattern=pattern,
        confidence=max(0.0, min(confidence, 0.97)),
        tier="ai",
        reason=f"AI tiebreak: {data.get('reason', '')[:160]}",
    )
