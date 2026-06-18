# Freight Agreement Intelligence Platform

AI-powered extraction, normalization, and search over vendor freight agreements
for **Mankind Pharma**. Turns inconsistent vendor PDFs (route tables, vehicle
matrices, zone rates, air/courier/cold-chain pricing) into one normalized,
searchable, auditable rate book — and generates Mankind Excel outputs.

> **Design principle:** deterministic extraction first, AI only on exception,
> human review before any export. Every rate is traceable to its source page,
> table, and cell, with a HIGH/MEDIUM/LOW confidence band. No number is ever
> guessed into a finance-facing output.

## Architecture at a glance
```
PDF ─► L0 ingest ─► L1 extract ─► L2 classify ─► L1.5 metadata/clauses
   ─► L3 AI gate ─► L4 normalize + route-expand + zone-resolve
   ─► L5 embed (RAG) ─► L5.5 HUMAN REVIEW ─► L6 Excel export
```
- **Backend** — FastAPI + Celery + Postgres/pgvector ([backend/](backend/))
- **Frontend** — Next.js App Router + TypeScript + Tailwind ([frontend/](frontend/))
- **Infra** — docker-compose (dev), K8s/ECS guidance ([infra/](infra/), [docs/deployment.md](docs/deployment.md))

## The 6 enhancements (v2)
1. Agreement metadata + clauses, stored separate from rates
2. Human review gate before Excel export
3. RAG search — freight / clause / vendor-comparison / analytics
4. Confidence bands HIGH / MEDIUM / LOW
5. Table fingerprinting + pattern learning (cheaper & more accurate with use)
6. AI explanation / full traceability (agreement → page → table → cell)

## Quick start
```bash
docker compose -f infra/docker-compose.yml up --build
# UI http://localhost:3000 · API docs http://localhost:8000/docs
```

## Build phases (all complete)
| Phase | Scope | Status |
|------|-------|--------|
| 1 | Architecture & design (v2) | ✅ |
| 2 | Canonical model, DB schema, API skeleton | ✅ |
| 3 | OCR & extraction (L0/L1) | ✅ |
| 4 | Pattern classification (L2, tiered + learning) | ✅ |
| 5 | Normalization, route expansion, metadata (L4/L1.5) | ✅ |
| 6 | Excel generation (L6, review-gated) | ✅ |
| 7 | AI validation gate + review workflow (L3) | ✅ |
| 8 | RAG knowledge search (L5) | ✅ |
| 9 | Next.js frontend | ✅ |
| 10 | Production deployment | ✅ |

## Tests
```bash
cd backend && pytest -q     # 50 backend tests (run inline without pytest too)
cd frontend && npm run typecheck && npm run build
```

See [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md),
and [docs/deployment.md](docs/deployment.md) for details.
