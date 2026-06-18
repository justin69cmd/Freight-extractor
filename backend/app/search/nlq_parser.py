"""Natural-language query router (Enhancement #3).

Maps a free-text query to one of four intents and extracts structured filters
(origin / destination / vendor / mode / metric). Deterministic and explainable;
an AI fallback can refine intent when the heuristics are unsure (left as a hook).

  FREIGHT_SEARCH      "rate from Meerut to Bangalore"
  CLAUSE_SEARCH       "what is vendor X's penalty clause"
  VENDOR_COMPARISON   "compare rates between vendors to Kolkata"
  AGREEMENT_ANALYTICS "which transporter is cheapest to Kolkata", "agreements expiring"
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.core.enums import SearchIntent, TransportMode

_FROM_TO = re.compile(r"\bfrom\s+(?P<o>[a-z .]+?)\s+to\s+(?P<d>[a-z .]+?)(?:\?|$|\s+(?:by|for|with|via)\b)", re.I)
_TO_ONLY = re.compile(r"\bto\s+(?P<d>[a-z .]+?)(?:\?|$|\s+(?:by|for|with|via)\b)", re.I)

_CLAUSE_WORDS = re.compile(r"\b(clause|penalt|insurance|fuel\s*surcharge|payment\s*terms|liabilit|indemnit|credit\s*period)\b", re.I)
_COMPARE_WORDS = re.compile(r"\b(compare|versus|vs\.?|between vendors|across vendors)\b", re.I)
_ANALYTICS_WORDS = re.compile(r"\b(cheapest|lowest|highest|most expensive|how many|which (transporter|vendor|carrier)|all vendors|serving|expir\w*|count|average)\b", re.I)

_MODE_WORDS = {
    TransportMode.AIR: re.compile(r"\bair\b", re.I),
    TransportMode.COURIER: re.compile(r"\bcourier\b", re.I),
    TransportMode.COLD_CHAIN: re.compile(r"\bcold\s*chain|reefer|temperature\b", re.I),
}


class ParsedQuery(BaseModel):
    intent: SearchIntent
    origin: str | None = None
    destination: str | None = None
    vendor: str | None = None
    mode: TransportMode | None = None
    raw: str = ""


def parse_query(text: str, *, forced_intent: SearchIntent | None = None) -> ParsedQuery:
    q = (text or "").strip()
    origin = destination = None
    if (m := _FROM_TO.search(q)):
        origin = _clean(m.group("o"))
        destination = _clean(m.group("d"))
    elif (m := _TO_ONLY.search(q)):
        destination = _clean(m.group("d"))

    mode = next((mode for mode, rx in _MODE_WORDS.items() if rx.search(q)), None)

    intent = forced_intent or _detect_intent(q)
    return ParsedQuery(intent=intent, origin=origin, destination=destination, mode=mode, raw=q)


def _detect_intent(q: str) -> SearchIntent:
    # order matters: comparison & analytics cues beat a bare "rate" lane query
    if _COMPARE_WORDS.search(q):
        return SearchIntent.VENDOR_COMPARISON
    if _ANALYTICS_WORDS.search(q):
        return SearchIntent.AGREEMENT_ANALYTICS
    if _CLAUSE_WORDS.search(q):
        return SearchIntent.CLAUSE_SEARCH
    return SearchIntent.FREIGHT_SEARCH


def _clean(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"\s+", " ", s.strip(" .?")).title() or None
