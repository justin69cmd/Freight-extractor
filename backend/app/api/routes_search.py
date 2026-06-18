"""RAG Agreement Intelligence endpoints (Enhancement #3).

One endpoint, four intents: freight search, clause search, vendor comparison,
agreement analytics. Intent is auto-detected by the NLQ router or passed in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.canonical.schemas import SearchRequest, SearchResponse
from app.db import get_db
from app.search.search_service import search as run_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(body: SearchRequest, db: Session = Depends(get_db)):
    """Natural-language query over rates + clauses + metadata (hybrid SQL + vector)."""
    return run_search(db, body.query, intent=body.intent, top_k=body.top_k)
