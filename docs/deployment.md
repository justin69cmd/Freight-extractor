# Deployment Guide (Phase 10)

Operational runbook for the Freight Agreement Intelligence Platform.

## Topology
```
            ┌────────────┐      ┌──────────────┐
  users ───►│  frontend  │────► │     api      │  (stateless, N replicas)
            │ (Next.js)  │      │  (FastAPI)   │
            └────────────┘      └──────┬───────┘
                                       │ enqueue (Redis)
                                ┌──────▼───────┐
                                │   workers    │  (Celery, autoscaled — bursty)
                                │ PDF/OCR/AI   │
                                └──────┬───────┘
                         ┌─────────────┼──────────────┐
                   ┌─────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐
                   │ Postgres  │ │   Redis   │ │ Object store│
                   │ +pgvector │ │  broker   │ │  (S3/MinIO) │
                   └───────────┘ └───────────┘ └─────────────┘
```
**Scale the workers independently of the API** — extraction load is spiky
(a 200-page scanned agreement is minutes of OCR), the API is light. Keep the API
stateless so it scales horizontally; all state is in Postgres/Redis/object store.

## Local / staging
```bash
cp backend/.env.example backend/.env        # fill keys
docker compose -f infra/docker-compose.yml up --build
# migrate service bootstraps the DB, then api/worker/frontend start in order.
# API  http://localhost:8000/docs    UI  http://localhost:3000
```
Startup is ordered by healthchecks; `migrate` runs `scripts/init_db.py` (pgvector
extension + tables) and must complete before api/worker boot.

## Database migrations
- Dev/CI bootstrap: `python -m scripts.init_db` (idempotent create-all).
- Production: **Alembic**. Generate the initial revision against a live pgvector DB:
  ```bash
  cd backend && alembic revision --autogenerate -m "init" && alembic upgrade head
  ```
  `migrations/env.py` already creates the `vector` extension and imports all models.

## Secrets & configuration
- All config is env-driven (`FREIGHT_*`, see `backend/.env.example`).
- **Never bake LLM keys into images.** Inject via Kubernetes Secrets / AWS SSM /
  Vault. `FREIGHT_ANTHROPIC_API_KEY`, `FREIGHT_OPENAI_API_KEY` at minimum.
- Tune trust thresholds per Mankind's risk appetite without code:
  `FREIGHT_BAND_HIGH_MIN`, `FREIGHT_BAND_MEDIUM_MIN`, `FREIGHT_AI_PER_JOB_CALL_BUDGET`.

## Data residency (pharma)
Vendor agreements are sensitive commercial documents. Keep PDFs, crops, and
embeddings **in-region**. If contracts forbid sending agreement text to a US-hosted
LLM, run a **self-hosted model** behind the same `llm_adapter` surface
(`FREIGHT_AI_PROVIDER`) and set `FREIGHT_EMBEDDING_PROVIDER=local` or an in-region
embedding service — no application code changes required.

## Kubernetes / ECS notes
- Deployments: `api` (HPA on CPU/RPS), `worker` (HPA on Celery queue depth), `frontend`.
- Probes: liveness `GET /health`, readiness `GET /health/ready` (checks DB).
- Postgres: managed (RDS/Cloud SQL) with the `vector` extension enabled; PITR backups.
- Redis: managed (ElastiCache/Memorystore); it is the Celery broker + result backend.
- Object store: S3/GCS; set `FREIGHT_STORAGE_BACKEND=s3` + bucket (wire in `storage.py`).
- Worker concurrency low (`--prefetch-multiplier 1`, `acks_late`) so long jobs are
  resume-safe and a dying worker re-delivers, not loses, the task.

## Observability (§19)
- **Structured JSON logs** (`app/core/logging.py`), one line per event, correlate by
  `job_id`. Ship to CloudWatch/Loki/Datadog.
- Metrics to track (emit from the pipeline / a `/metrics` Prometheus exporter):
  - throughput: jobs/min, pages/min, avg job duration
  - quality: **flag rate** (flagged ÷ total rates), LOW-band %, UNKNOWN-pattern %
  - cost: **AI calls/agreement**, fingerprint cache hit rate, $/agreement
  - reliability: job failure rate, OCR fallback rate
- **Alert on a flag-rate spike** — it usually means a new vendor format the
  classifier hasn't learned, i.e. a vendor profile needs tuning.

## CI
`.github/workflows/ci.yml`: backend (ruff + pytest against pgvector+redis service
containers, `EMBEDDING_PROVIDER=local` so no external key) and frontend
(`typecheck` + `build`). Add image build/push + deploy stages per your registry.

## Production checklist
- [ ] LLM/API keys in a secret manager, not env files
- [ ] Postgres `vector` extension enabled; automated backups + PITR
- [ ] Object storage configured (`FREIGHT_STORAGE_BACKEND=s3`)
- [ ] Worker autoscaling on queue depth
- [ ] Alembic migration applied (`alembic upgrade head`)
- [ ] CORS locked to the frontend origin (set in `app/main.py`, currently `*` in debug)
- [ ] Auth/RBAC in front of the API (uploader / reviewer / admin) — add at the gateway
- [ ] Log aggregation + flag-rate alerting wired
- [ ] Data-residency review signed off for the chosen LLM/embedding provider
