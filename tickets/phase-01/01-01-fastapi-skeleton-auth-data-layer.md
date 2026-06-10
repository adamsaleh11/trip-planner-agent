# T1.1 — FastAPI skeleton, Firebase auth, Firestore data layer

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI service
Skill: tdd · Agent: Claude · Parallel with: T2.1 (Codex, frontend repo)
Plan: plans/trip-journal-pivot.md · Phase 1

## Goal

Stand up the production backend skeleton: an app-factory FastAPI service where every request is authenticated via Firebase ID token, all data access goes through one Firestore module, and structured logging exists from the first endpoint.

## Responsibilities

- Restructure repo: `app/` package with `app/main.py` (app factory), `app/api/` (routers), `app/services/` (business logic), `app/models/` (Pydantic schemas), `app/core/` (config, logging, auth). Keep `travel_agent/tools/` (Places/Routes) untouched for Phase 3.
- Config via pydantic-settings reading `.env` (GCP project, Firebase credentials path, Gmail sender vars reserved for T1.2). No secrets in code.
- Auth dependency: verify `Authorization: Bearer <Firebase ID token>` with `firebase-admin`; reject 401 on missing/invalid/expired; expose `CurrentUser` (uid, email) to handlers.
- Firestore module: single client factory + thin typed repository helpers (get/set/query scoped by uid). All collections accessed through this module — no raw client usage in routers.
- `GET /me`: auto-provisions `users/{uid}` doc on first call (email, displayName, createdAt, `memberTripIds: []`), returns the profile.
- Structured JSON logging: request middleware assigns `request_id`, logs method/path/status/latency_ms/uid; all service logs carry `request_id`.

## Tools / Interfaces

- `firebase-admin` (token verification), `google-cloud-firestore`, `pydantic-settings`.
- Tests: pytest with a fake Firestore (in-memory dict repo implementing the same interface) and a stubbed token verifier — no emulator, no Docker.

## Patterns

- App factory + dependency injection so tests swap auth and Firestore fakes cleanly.
- Repository interface kept narrow so the fake stays trivial (tdd: test through the HTTP layer, not the repo internals).

## Cost rules

- No LLM calls in this ticket. Firestore free-tier discipline: single read per `GET /me` after provisioning.

## Acceptance criteria

- [ ] `uvicorn app.main:app` boots locally with `.env` config; `/healthz` returns 200 unauthenticated.
- [ ] `GET /me` without/with-invalid token → 401; with valid token → 200 and creates the user doc exactly once (idempotent on repeat calls).
- [ ] Every response logs a structured JSON line containing request_id, uid (or "anon"), path, status, latency_ms.
- [ ] All tests pass via fakes — no network, no emulator, no Docker.
- [ ] No router imports the Firestore client directly; only via the data-layer module.
