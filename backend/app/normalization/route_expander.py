"""Route Expansion Engine (critical business rule).

A single cell like "Hapur/Meerut/FRK" with destination "Kolkata/Delhi" is
shorthand for the Cartesian product of 3x2 = 6 lanes. This module:

  * splits multi-value cells on /, comma, &, newline, " or ",
  * resolves vendor aliases (FRK -> Faridabad),
  * emits every (origin, destination) combination,
  * guards against explosion (a paragraph misread as a cell).

Deterministic and idempotent: same input -> same lane set, safe to re-run.
"""
from __future__ import annotations

import re

from app.config import settings
from app.core.exceptions import RouteExpansionError

# Split on / , & newline, or the word "or" (surrounded by spaces).
_SPLIT_RE = re.compile(r"\s*(?:/|,|&|\n|\bor\b)\s*", re.I)
_CLEAN_RE = re.compile(r"\s+")


def split_places(cell: str | None, aliases: dict[str, str] | None = None) -> list[str]:
    """Split a multi-value place cell into canonical, de-duplicated names."""
    if not cell or not cell.strip():
        return []
    aliases = {k.lower(): v for k, v in (aliases or {}).items()}
    parts = [p for p in _SPLIT_RE.split(cell) if p and p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        name = _CLEAN_RE.sub(" ", p.strip())
        resolved = aliases.get(name.lower(), name)
        key = resolved.lower()
        if key not in seen:
            seen.add(key)
            out.append(resolved)
    return out


def expand_routes(
    origin_cell: str | None,
    destination_cell: str | None,
    aliases: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Cartesian product of split origins x destinations.

    If one side is empty it is treated as a single unknown (None-name skipped by
    callers), so a one-sided table still yields rows.
    """
    origins = split_places(origin_cell, aliases)
    destinations = split_places(destination_cell, aliases)

    if not origins and not destinations:
        return []

    n = max(len(origins), 1) * max(len(destinations), 1)
    if n > settings.max_lanes_per_cell:
        raise RouteExpansionError(
            f"route expansion produced {n} lanes (> {settings.max_lanes_per_cell}); "
            f"likely a mis-parsed cell: origins={origins!r} dests={destinations!r}"
        )

    lanes: list[tuple[str, str]] = []
    for o in origins or [""]:
        for d in destinations or [""]:
            lanes.append((o, d))
    return lanes
