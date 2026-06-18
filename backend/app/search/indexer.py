"""L5 embedding indexer — builds the unified RAG corpus (Enhancement #3).

Rates, clauses, and metadata are denormalized into one searchable text per item
and embedded into DocumentChunk (pgvector). One vector space, queried by intent.

The `build_*_text` helpers are pure and unit-tested; `index_agreement` touches
the DB and is exercised under docker-compose.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.enums import ReviewItemKind
from app.search.embedder import embed_batch

log = logging.getLogger("freight.indexer")


def build_rate_text(rate, vendor_name: str | None = None) -> str:
    mode = getattr(rate.transport_mode, "value", str(rate.transport_mode))
    basis = getattr(rate.rate_basis, "value", str(rate.rate_basis))
    parts = [
        vendor_name or "",
        mode, "freight",
        f"from {rate.origin}" if rate.origin else "",
        f"({rate.origin_state})" if rate.origin_state else "",
        f"to {rate.destination}" if rate.destination else "",
        f"({rate.destination_state})" if rate.destination_state else "",
        f"zone {rate.destination_zone}" if rate.destination_zone else "",
        rate.vehicle_type or "",
        rate.service_level or "",
        f"{rate.temperature_band} cold chain" if rate.temperature_band else "",
        f"{basis} INR {rate.rate_value}" if rate.rate_value is not None else "",
    ]
    return " ".join(p for p in parts if p).strip()


def build_clause_text(clause, vendor_name: str | None = None) -> str:
    ctype = getattr(clause.clause_type, "value", str(clause.clause_type))
    return f"{vendor_name or ''} {ctype} clause: {clause.text}".strip()


def build_metadata_text(meta, vendor_name: str | None = None) -> str:
    return " ".join(
        p for p in [
            vendor_name or meta.vendor_name or "",
            "agreement",
            f"effective {meta.effective_date}" if meta.effective_date else "",
            f"expires {meta.expiry_date}" if meta.expiry_date else "",
            f"payment terms {meta.payment_terms}" if meta.payment_terms else "",
        ] if p
    ).strip()


def index_agreement(db: Session, agreement) -> int:
    """Create + embed DocumentChunks for every rate, clause, and the metadata."""
    from app.canonical.models import DocumentChunk  # lazy: keeps builders DB-free

    vendor_name = agreement.vendor.name if agreement.vendor else None
    items: list[tuple[ReviewItemKind, object, str]] = []

    for rate in agreement.rates:
        items.append((ReviewItemKind.RATE, rate, build_rate_text(rate, vendor_name)))
    for clause in agreement.clauses:
        items.append((ReviewItemKind.CLAUSE, clause, build_clause_text(clause, vendor_name)))
    if agreement.metadata_row:
        items.append(
            (ReviewItemKind.METADATA, agreement.metadata_row,
             build_metadata_text(agreement.metadata_row, vendor_name))
        )

    if not items:
        return 0

    vectors = embed_batch([text for _, _, text in items])
    for (kind, obj, text), vec in zip(items, vectors):
        db.add(
            DocumentChunk(
                agreement_id=agreement.id,
                vendor_id=agreement.vendor_id,
                kind=kind,
                ref_id=obj.id,
                content=text,
                embedding=vec,
            )
        )
    db.flush()
    log.info("indexed %d chunks for agreement %s", len(items), agreement.id)
    return len(items)
