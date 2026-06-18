# Freight Intelligence — Frontend (Phase 9)

Next.js (App Router) + TypeScript + Tailwind. Talks to the FastAPI backend via
`/api/*` rewrites (configured in `next.config.js`), so no CORS in dev.

## Screens
| Route | Purpose |
|---|---|
| `/` | Landing / entry points |
| `/upload` | Upload a vendor PDF → dispatches the pipeline |
| `/jobs/[id]` | Live pipeline progress (polls `GET /api/jobs/{id}`) |
| `/review/[id]` | **Review QA** — metadata + clauses, fix flagged items (`PATCH /api/review/tasks`), approve & export (gated) |
| `/search` | NL search across the 4 RAG intents |
| `/compare` | Vendor rate comparison for a lane |

## Key files
- `lib/types.ts` — TS mirror of the backend Pydantic schemas
- `lib/api.ts` — typed client; `ApiError.isReviewBlocked` maps the 409 review gate
- `components/ConfidenceBadge.tsx` — HIGH/MEDIUM/LOW band chip (Enhancement #4)
- `components/JobProgress.tsx` — pipeline stage tracker

## Run (dev)
```bash
cp .env.local.example .env.local      # point BACKEND_URL at FastAPI
npm install
npm run dev                           # http://localhost:3000
```
Requires the backend running (see ../backend/README.md). `npm run typecheck`
validates the client against the schema types.
