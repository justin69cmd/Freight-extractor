"""L2 Tier-1 — deterministic, explainable rule classifier.

Each of the 9 patterns gets a score from structural features. The argmax wins;
the gap to the runner-up becomes the margin. A low margin (ambiguous) is what
later trips the AI tiebreak (Tier 3) — rules never silently guess on a coin-flip.

Confidence is derived from both the winning score and the margin, then mapped to
a band by the caller. Covers ~80% of tables without any AI cost.
"""
from __future__ import annotations

from app.classification.features import Features, extract_features
from app.classification.result import ClassificationResult
from app.core.enums import PricingPattern
from app.extraction.raw_table import RawTable


def _scores(f: Features) -> dict[PricingPattern, float]:
    k = f.keyword_hits
    s: dict[PricingPattern, float] = {p: 0.0 for p in PricingPattern if p != PricingPattern.UNKNOWN}

    # STATE_ZONE_MAPPING — states paired with a zone column, mostly textual.
    if f.state_label_count >= 2 and (k["zone"] or "zone" in f.header_tokens):
        s[PricingPattern.STATE_ZONE_MAPPING] += 4 + f.state_label_count * 0.5
    if k["state"] and k["zone"] and f.numeric_ratio < 0.3:
        s[PricingPattern.STATE_ZONE_MAPPING] += 2

    # ZONE_MATRIX — Zone A/B/C headers over a numeric grid.
    if f.zone_header_count >= 2:
        s[PricingPattern.ZONE_MATRIX] += 3 + f.zone_header_count
    if k["zone"] and f.numeric_ratio >= 0.4 and f.state_label_count < 2:
        s[PricingPattern.ZONE_MATRIX] += 2

    # VEHICLE_MATRIX — vehicle types + numeric grid.
    if k["vehicle"]:
        s[PricingPattern.VEHICLE_MATRIX] += 2 + min(k["vehicle"], 4) * 0.75
        if f.numeric_ratio >= 0.3:
            s[PricingPattern.VEHICLE_MATRIX] += 1.5

    # LANE_MATRIX — origin labels reappear as destination headers (square-ish).
    if f.matrix_symmetry >= 0.3 and f.numeric_ratio >= 0.3:
        s[PricingPattern.LANE_MATRIX] += 3 + f.matrix_symmetry * 4

    # ROUTE_TABLE — explicit origin & destination columns + a rate column.
    if k["origin"] and k["dest"]:
        s[PricingPattern.ROUTE_TABLE] += 4
    if (k["origin"] or k["dest"]) and k["rate"]:
        s[PricingPattern.ROUTE_TABLE] += 1.5

    # PER_KG_RATE — weight/slab vocabulary.
    if k["per_kg"]:
        s[PricingPattern.PER_KG_RATE] += 2 + min(k["per_kg"], 4) * 0.75

    # AIR_RATE — air/awb/airport tokens.
    if k["air"]:
        s[PricingPattern.AIR_RATE] += 3 + min(k["air"], 3)

    # COURIER_RATE — courier/docket/express tokens.
    if k["courier"]:
        s[PricingPattern.COURIER_RATE] += 3 + min(k["courier"], 3)

    # COLD_CHAIN_RATE — temperature signature dominates regardless of other shape.
    if k["cold"]:
        s[PricingPattern.COLD_CHAIN_RATE] += 4 + min(k["cold"], 3)

    # weak prior: a plain rate table with a rate column but no other signal.
    if k["rate"] and sum(s.values()) == 0:
        s[PricingPattern.ROUTE_TABLE] += 1
    return s


def _column_mapping(f: Features, pattern: PricingPattern) -> dict:
    """Best-effort logical-field -> column-index map for the normalizer (L4)."""
    from app.classification.features import (
        _DEST_KW, _ORIGIN_KW, _RATE_KW,  # reuse the same vocabularies
    )

    mapping: dict[str, int] = {}
    for idx, h in enumerate(f.header_tokens):
        if _ORIGIN_KW.search(h) and "origin" not in mapping:
            mapping["origin"] = idx
        elif _DEST_KW.search(h) and "destination" not in mapping:
            mapping["destination"] = idx
        elif _RATE_KW.search(h) and "rate" not in mapping:
            mapping["rate"] = idx
    return mapping


def classify_rules(table: RawTable) -> ClassificationResult:
    f = extract_features(table)
    scores = _scores(f)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (top, top_score), (runner, runner_score) = ranked[0], ranked[1]

    if top_score <= 0:
        return ClassificationResult(
            pattern=PricingPattern.UNKNOWN, confidence=0.0, tier="rules",
            reason="no structural signal matched any pattern",
        )

    margin = top_score - runner_score
    # Confidence: saturating function of top score, dampened by a thin margin.
    base = min(top_score / 8.0, 1.0)
    margin_factor = min(margin / 3.0, 1.0)
    confidence = round(0.5 * base + 0.5 * (base * margin_factor) + 0.0, 4)
    confidence = max(0.0, min(confidence, 0.99))

    return ClassificationResult(
        pattern=top,
        confidence=confidence,
        tier="rules",
        reason=f"top={top.value}({top_score:.1f}) vs {runner.value}({runner_score:.1f}); "
               f"numeric={f.numeric_ratio:.2f} symmetry={f.matrix_symmetry:.2f}",
        column_mapping=_column_mapping(f, top),
        runner_up=runner if runner_score > 0 else None,
        margin=round(margin, 3),
    )
