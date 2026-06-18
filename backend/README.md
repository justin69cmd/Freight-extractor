# Freight Intelligence — Backend (Phase 2)

FastAPI + Celery + Postgres/pgvector skeleton for the Freight Agreement
Intelligence Platform. Phase 2 delivers the **canonical data model, database
schema, and API skeleton**. Pipeline logic arrives in Phases 3–8.

## Layout
```
app/
  config.py            settings + confidence-band thresholds (Enh #4)
  db.py                engine / session / Base
  core/
    enums.py           controlled vocabulary (patterns, bands, statuses)
    confidence.py      numeric -> band + routing decisions (Enh #4)
    exceptions.py      typed per-layer errors (§17)
    celery_app.py      async pipeline runner
  canonical/
    models.py          SQLAlchemy schema — all entities incl. 6 enhancements
    schemas.py         Pydantic API contracts
  api/                 route stubs (upload/jobs/rates/review/search/export/vendors)
vendor_profiles/       no-code vendor onboarding (Enh #5)
migrations/            alembic
tests/
```

## Where each enhancement lives
| # | Enhancement | Code |
|---|---|---|
| 1 | Agreement metadata + clauses (separate from rates) | `AgreementMetadata`, `Clause` |
| 2 | Human review gate before export | `JobStatus.REVIEW_PENDING`, `ReviewTask`, `routes_review.py` |
| 3 | RAG (freight/clause/comparison/analytics) | `DocumentChunk`, `routes_search.py`, `SearchIntent` |
| 4 | Confidence bands HIGH/MEDIUM/LOW | `core/confidence.py`, `ConfidenceBand` |
| 5 | Fingerprint + pattern learning | `TableFingerprint`, `vendor_profiles/` |
| 6 | Traceability / AI explanation | `ProvenanceMixin`, `routes_rates.py` provenance endpoint |

## Run (dev)
```bash
cp .env.example .env            # fill in keys
pip install -e ".[dev]"
docker compose -f ../infra/docker-compose.yml up -d db redis
alembic revision --autogenerate -m "init"   # generates from models
alembic upgrade head
uvicorn app.main:app --reload
# -> http://localhost:8000/docs
```

Route handlers currently raise `NotImplementedError` by design — the contracts
are frozen; implementations land phase-by-phase.
