"""RAG search service (Enhancement #3) — hybrid SQL + vector, 4 intents.

  FREIGHT_SEARCH      structured SQL filter on canonical rates + vector recall
  CLAUSE_SEARCH       vector recall over clause chunks + LLM synthesis
  VENDOR_COMPARISON   aggregate best/avg rate per vendor for a lane
  AGREEMENT_ANALYTICS cheapest / who-serves / expiring aggregates

Structured SQL gives precision; vectors give recall (typos, paraphrase,
Bengaluru vs Bangalore). LLM synthesis is optional — without a provider key the
service still returns ranked hits plus a templated answer, never an error.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.canonical.models import (
    Agreement,
    AgreementMetadata,
    CanonicalRate,
    Clause,
    DocumentChunk,
    Vendor,
)
from app.canonical.schemas import SearchHit, SearchResponse
from app.core.enums import ReviewItemKind, SearchIntent
from app.core.exceptions import AIValidationError
from app.search.embedder import embed
from app.search.indexer import build_rate_text
from app.search.nlq_parser import ParsedQuery, parse_query

log = logging.getLogger("freight.search")


def search(
    db: Session, query: str, *, intent: SearchIntent | None = None, top_k: int = 10
) -> SearchResponse:
    pq = parse_query(query, forced_intent=intent)
    if pq.intent is SearchIntent.FREIGHT_SEARCH:
        return _freight_search(db, pq, top_k)
    if pq.intent is SearchIntent.CLAUSE_SEARCH:
        return _clause_search(db, pq, top_k)
    if pq.intent is SearchIntent.VENDOR_COMPARISON:
        return _vendor_comparison(db, pq, top_k)
    return _analytics(db, pq, top_k)


# --- FREIGHT_SEARCH -------------------------------------------------------- #
def _freight_search(db: Session, pq: ParsedQuery, top_k: int) -> SearchResponse:
    stmt = select(CanonicalRate)
    if pq.origin:
        stmt = stmt.where(CanonicalRate.origin.ilike(f"%{pq.origin}%"))
    if pq.destination:
        stmt = stmt.where(CanonicalRate.destination.ilike(f"%{pq.destination}%"))
    if pq.mode:
        stmt = stmt.where(CanonicalRate.transport_mode == pq.mode)
    stmt = stmt.where(CanonicalRate.rate_value.isnot(None)).order_by(
        CanonicalRate.rate_value.asc()
    ).limit(top_k)

    rates = list(db.scalars(stmt))
    if not rates:  # structured miss -> vector recall (handles typos/paraphrase)
        return _vector_response(db, pq, ReviewItemKind.RATE, top_k)

    names = _vendor_names(db, {r.vendor_id for r in rates})
    hits = [
        SearchHit(
            kind="RATE", score=1.0, vendor=names.get(r.vendor_id),
            snippet=build_rate_text(r, names.get(r.vendor_id)), ref_id=r.id,
        )
        for r in rates
    ]
    return SearchResponse(intent=pq.intent, answer=None, hits=hits)


# --- CLAUSE_SEARCH --------------------------------------------------------- #
def _clause_search(db: Session, pq: ParsedQuery, top_k: int) -> SearchResponse:
    chunks = _vector_chunks(db, pq.raw, ReviewItemKind.CLAUSE, top_k)
    hits = [
        SearchHit(kind="CLAUSE", score=score, vendor=None, snippet=c.content, ref_id=c.ref_id)
        for c, score in chunks
    ]
    answer = _synthesize(pq.raw, [c.content for c, _ in chunks])
    return SearchResponse(intent=pq.intent, answer=answer, hits=hits)


# --- VENDOR_COMPARISON ----------------------------------------------------- #
def _vendor_comparison(db: Session, pq: ParsedQuery, top_k: int) -> SearchResponse:
    stmt = (
        select(
            CanonicalRate.vendor_id,
            func.min(CanonicalRate.rate_value),
            func.avg(CanonicalRate.rate_value),
            func.count(),
        )
        .where(CanonicalRate.rate_value.isnot(None))
        .group_by(CanonicalRate.vendor_id)
    )
    if pq.origin:
        stmt = stmt.where(CanonicalRate.origin.ilike(f"%{pq.origin}%"))
    if pq.destination:
        stmt = stmt.where(CanonicalRate.destination.ilike(f"%{pq.destination}%"))
    rows = list(db.execute(stmt))
    names = _vendor_names(db, {r[0] for r in rows})

    rows.sort(key=lambda r: r[1])  # cheapest first
    hits = [
        SearchHit(
            kind="RATE", score=1.0, vendor=names.get(vid),
            snippet=f"{names.get(vid)}: min INR {minr:.2f}, avg INR {avgr:.2f} ({n} lanes)",
            ref_id=vid,
        )
        for vid, minr, avgr, n in rows[:top_k]
    ]
    lane = f"{pq.origin or 'any'} -> {pq.destination or 'any'}"
    answer = (
        f"Cheapest for {lane}: {hits[0].vendor} at INR {rows[0][1]:.2f}." if hits else
        f"No rates found for {lane}."
    )
    return SearchResponse(intent=pq.intent, answer=answer, hits=hits)


# --- AGREEMENT_ANALYTICS --------------------------------------------------- #
def _analytics(db: Session, pq: ParsedQuery, top_k: int) -> SearchResponse:
    q = pq.raw.lower()
    if "expir" in q:
        soon = date.today() + timedelta(days=90)
        rows = list(
            db.execute(
                select(AgreementMetadata.vendor_name, AgreementMetadata.expiry_date)
                .where(AgreementMetadata.expiry_date.isnot(None))
                .where(AgreementMetadata.expiry_date <= soon)
                .order_by(AgreementMetadata.expiry_date.asc())
                .limit(top_k)
            )
        )
        hits = [
            SearchHit(kind="METADATA", score=1.0, vendor=v, snippet=f"{v} expires {d}", ref_id=_zero_uuid())
            for v, d in rows
        ]
        return SearchResponse(intent=pq.intent, answer=f"{len(rows)} agreement(s) expiring within 90 days.", hits=hits)

    if "serv" in q or "all vendors" in q:  # who serves a destination
        stmt = select(CanonicalRate.vendor_id).distinct()
        if pq.destination:
            stmt = stmt.where(CanonicalRate.destination.ilike(f"%{pq.destination}%"))
        vids = [r[0] for r in db.execute(stmt)]
        names = _vendor_names(db, set(vids))
        hits = [
            SearchHit(kind="RATE", score=1.0, vendor=names.get(v), snippet=names.get(v) or str(v), ref_id=v)
            for v in vids[:top_k]
        ]
        return SearchResponse(
            intent=pq.intent,
            answer=f"{len(vids)} vendor(s) serve {pq.destination or 'the network'}.",
            hits=hits,
        )

    # default analytics: cheapest to a destination
    return _vendor_comparison(db, pq, top_k)


# --- shared helpers -------------------------------------------------------- #
def _vector_chunks(db: Session, text: str, kind: ReviewItemKind, top_k: int):
    """Return [(DocumentChunk, score)] ordered by cosine similarity (pgvector)."""
    vec = embed(text)
    dist = DocumentChunk.embedding.cosine_distance(vec)
    stmt = (
        select(DocumentChunk, dist.label("d"))
        .where(DocumentChunk.kind == kind)
        .order_by(dist)
        .limit(top_k)
    )
    return [(row[0], 1.0 - float(row[1])) for row in db.execute(stmt)]


def _vector_response(db: Session, pq: ParsedQuery, kind: ReviewItemKind, top_k: int) -> SearchResponse:
    chunks = _vector_chunks(db, pq.raw, kind, top_k)
    hits = [
        SearchHit(kind=kind.value, score=score, vendor=None, snippet=c.content, ref_id=c.ref_id)
        for c, score in chunks
    ]
    return SearchResponse(intent=pq.intent, answer=None, hits=hits)


def _vendor_names(db: Session, ids: set) -> dict:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {v.id: v.name for v in db.scalars(select(Vendor).where(Vendor.id.in_(ids)))}


def _synthesize(query: str, snippets: list[str]) -> str | None:
    """Optional LLM synthesis; falls back to a templated answer without a key."""
    if not snippets:
        return "No matching clauses found."
    from app.config import settings
    from app.validation.llm_adapter import llm

    context = "\n---\n".join(snippets[:5])
    try:
        data = llm.complete_json(
            system=(
                "Answer the user's question about freight-agreement clauses using ONLY the "
                "provided clause excerpts. Cite the relevant clause. If the answer is not in "
                'the excerpts, say so. Respond as JSON: {"answer": "..."}'
            ),
            user=f"Question: {query}\n\nClause excerpts:\n{context}",
            model=settings.ai_model_classify,
            max_tokens=400,
        )
        return data.get("answer") or _template_answer(snippets)
    except AIValidationError:
        return _template_answer(snippets)


def _template_answer(snippets: list[str]) -> str:
    return "Top matching clause: " + snippets[0][:300]


def _zero_uuid():
    import uuid
    return uuid.UUID(int=0)
