"""Unit & value normalization.

Parses messy money/weight strings into clean floats and detects weight slabs.
Conservative by design: an unparseable price returns None (the row gets flagged
for review) rather than a guessed number — finance never pays against a guess.
"""
from __future__ import annotations

import re

# Money: tolerate ₹ / Rs / INR prefixes, thousands separators, trailing "/-".
_MONEY_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_THOUSANDS = re.compile(r",")

# Weight slab like "0-50 kg", "upto 100", "501 to 1000 kgs", "<25"
_SLAB_RE = re.compile(
    r"(?:(?P<lo>\d+(?:\.\d+)?)\s*(?:-|–|to)\s*)?(?P<hi>\d+(?:\.\d+)?)\s*(?:kgs?|kg)?",
    re.I,
)
_UPTO_RE = re.compile(r"\b(?:up\s*to|upto|<=?|below|max)\b", re.I)
_ABOVE_RE = re.compile(r"\b(?:above|over|>=?|min|more than)\b", re.I)


def parse_amount(text: str | None) -> float | None:
    """Parse a money/number cell to float, or None if not a clean number."""
    if not text:
        return None
    s = text.strip()
    if s.lower() in {"-", "na", "n/a", "nil", "tbd", ""}:
        return None
    m = _MONEY_RE.search(s)
    if not m:
        return None
    cleaned = _THOUSANDS.sub("", m.group(0))
    try:
        val = float(cleaned)
    except ValueError:
        return None
    # Reject implausible/negative freight values -> caller flags for review.
    if val < 0:
        return None
    return val


def parse_weight_slab(text: str | None) -> tuple[float | None, float | None]:
    """Return (min_kg, max_kg) for a slab label. Open-ended ends stay None."""
    if not text:
        return (None, None)
    s = text.strip()
    upto = bool(_UPTO_RE.search(s))
    above = bool(_ABOVE_RE.search(s))
    m = _SLAB_RE.search(s)
    if not m:
        return (None, None)
    lo = float(m.group("lo")) if m.group("lo") else None
    hi = float(m.group("hi")) if m.group("hi") else None
    if upto and lo is None:        # "upto 100" -> (None, 100)
        return (None, hi)
    if above:                      # "above 1000" -> (1000, None)
        return (hi, None)
    if lo is None:                 # single number -> treat as upper bound
        return (None, hi)
    return (lo, hi)
