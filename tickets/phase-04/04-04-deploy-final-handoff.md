# T4.4 — Deploy (Cloud Run + Vercel) + final architecture handoff

Repo: both · System: Mac · Type: Deployment + documentation
Skill: contract-handoff · Agent: Claude (single agent — no parallel work during deploy) · Depends on: ALL previous tickets merged
Plan: plans/trip-journal-pivot.md · Phase 4 · FINAL TICKET

## Goal

Ship both apps to production and produce the final architecture document — the artifact you walk the hiring manager through: what was built, why each decision was made, and the explicit path from this MVP to 10,000+ users.

## Responsibilities

- **Backend → Cloud Run**: containerize the FastAPI app (Dockerfile written here for the BUILD only — `gcloud run deploy --source .` does the build remotely; nothing runs in Docker locally, honoring the no-local-Docker constraint). Secrets (Firebase admin creds, Gmail refresh token, server HMAC secret, Maps key) via Secret Manager; service account with least-privilege roles (Firestore, Vertex AI, Trace). Min instances 0, concurrency default; note that background generations need `--no-cpu-throttling` (or document Cloud Tasks as the fix) — verify a generation completes after the HTTP response on Cloud Run.
- **Frontend → Vercel**: env vars (API base URL, Firebase web config, Mapbox token); Firebase Auth authorized domains updated for the Vercel domain; CORS allowlist on FastAPI set to the Vercel origin (and localhost for dev).
- **Prod smoke test, two real accounts**: sign up → create trip → email invite received in a real inbox → accept → fill 2 categories, leave 3 empty → generate (live progress works in prod) → itinerary valid → Right Now whim from the trip page returns a suggestion in seconds → save whim to journal → complete trip → journal + opt-in share → second account generates for same destination and retrieval surfaces the shared tip → map page renders.
- **Final handoff doc** (`docs/contracts/trip-journal-architecture.md`): system diagram (frontend/backend/GCP services), every architecture decision from the grill session with its WHY (the decision log is the interview script), privacy model (anonymization pipeline, deletion path), observability story (trace screenshot), eval results table, cost-per-generation numbers from real metrics, and the scale section: Cloud Tasks for durable generation, Firestore composite indexes at scale, Vector Search namespace sharding, multi-region, rate limiting, monitoring/alerting — each as "what changes at 10k users and what I'd do".
- README refresh in both repos: 5-minute local setup, env templates, architecture doc link.

## Tools / Interfaces

- gcloud CLI, Vercel CLI/dashboard, Secret Manager, real Gmail inbox for the smoke test.

## Patterns

- Deploy is sequential and single-agent: backend first (get the prod URL), then frontend env pointing at it, then auth-domain/CORS closure.

## Cost rules

- Cloud Run scale-to-zero + Firestore/Firebase free tiers + flash pricing: idle cost ≈ $0; record actual measured cost-per-generation in the handoff doc (it's a rubric line item).

## Acceptance criteria

- [ ] Both apps live on public URLs; full two-account smoke test passes end-to-end in production (checklist in doc, each step ticked).
- [ ] A production generation completes after the 202 (background work verified on Cloud Run) and its trace appears in Cloud Trace.
- [ ] No secret exists in either repo or build artifact (grep + env audit); all prod secrets in Secret Manager/Vercel env.
- [ ] Handoff doc complete with decision log, privacy model, real metrics, eval table, and the 10k-user scale section.
- [ ] Fresh-clone local setup still works per READMEs (deploy didn't break dev).

## Updates (2026-06-10 — free-tier switch, participants)

- Secrets now include `GOOGLE_API_KEY` (AI Studio) and the `GOOGLE_GENAI_USE_VERTEXAI` flag. Decide at deploy: stay free-tier (rate limits shared across all prod users — fine for demo) or flip to Vertex for the interview demo (one env var; pennies). Document both in the handoff.
- No Vector Search deploy step — retrieval is in-process (see T4.1 update). The handoff doc's scale section gains the `MemoryRetriever` swap story and the measured $3.25/day figure you actually saw from the old deployed index as the cost rationale.
- Prod smoke test additions: admin creates an UNCLAIMED participant + fills their preferences → invite links/claims that participant → generation reflects them.
