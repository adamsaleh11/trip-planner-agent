# T1.4 — API contract handoff (sync point for Codex)

Repo: trip-planner-agent (backend) · System: Mac · Type: Documentation / contract
Skill: contract-handoff · Agent: Claude · Depends on: T1.1–T1.3 · Unblocks: T2.2, T2.3, T3.3
Plan: plans/trip-journal-pivot.md · Phase 1

## Goal

Produce `docs/contracts/trip-journal-api.md` — the single source of truth the frontend repo builds against. After this ticket the contract is FROZEN; any change goes through the owner, not either agent unilaterally.

## Responsibilities

- Document every route from T1.1–T1.3: method, path, auth requirement, request schema, response schema, error shapes (401/403/404/409/410/422) with example JSON for each.
- Document the auth handshake: Firebase client SDK → ID token → `Authorization: Bearer` header; token refresh expectations; which Firebase project/config the frontend uses.
- Document Firestore collections the frontend reads DIRECTLY via the client SDK (bypassing the API): `trips/{id}/generations/{genId}` realtime listener for generation progress (write the planned doc shape now — agentStatuses map {agent → pending|running|done|error}, phase, itinerary, metrics, error — so T3.3 can build against a mock before T3.2 lands).
- Document forward-declared Phase 3/4 routes as PLANNED (generate endpoint, `POST /whims` request/response for the Right Now feature, journal endpoints, map data endpoint) with their expected shapes, clearly marked non-final. The whims shape must be firm enough for T3.5 to build against a mock (synchronous response — no listener).
- Include participant roster semantics verbatim: participants are the planning roster; memberships are access control; Add Traveler is separate from Invite Traveler; invite acceptance can claim/overwrite an existing unclaimed participant while preserving its preferences.
- Include the category preference schemas verbatim (field names, enums) and participant-scoped preference routes — these become the frontend form types.
- Include environment contract for the frontend repo: `NEXT_PUBLIC_API_BASE_URL`, Firebase web config keys, `NEXT_PUBLIC_MAPBOX_TOKEN` (reserved for T4.2).

## Tools / Interfaces

- Generated from the live FastAPI OpenAPI schema where possible (`/openapi.json`), then human-curated — the contract must read as prose+schemas, not a raw OpenAPI dump.

## Patterns

- Contract-first handoff: Codex never reads the backend source; everything it needs is in this file. If the frontend needs something not in the contract, that's a contract change request, not an improvisation.

## Cost rules

- None (no runtime cost). Time-box: this is a 15–20 minute ticket; depth goes to schemas and the generations-doc shape, not prose.

## Acceptance criteria

- [ ] `docs/contracts/trip-journal-api.md` exists and covers 100% of implemented routes with example requests/responses.
- [ ] The `generations` Firestore doc shape is specified precisely enough for T3.3 to build the live progress UI from a hand-written mock doc.
- [ ] Preference category schemas match the Pydantic models exactly (spot-checked field by field).
- [ ] Frontend env contract section lists every variable the Next.js repo needs for Phases 2–4.
- [ ] File is copied/committed where the frontend repo can read it at session start (read-contract skill input).
