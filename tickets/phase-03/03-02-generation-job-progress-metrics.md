# T3.2 — Generation job: background execution, live progress, metrics

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI + ADK Runner
Skill: tdd · Agent: CLAUDE CODE (backend) · Depends on: T3.1 · Parallel with: T2.3 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 3

## Goal

"Click Generate" becomes a 202 + background job driving `Runner.run_async`, streaming per-agent progress to a Firestore generations doc the frontend watches in realtime, recording LLM-native metrics on completion.

## Responsibilities

- `POST /trips/{id}/generate` (member-only): creates `trips/{id}/generations/{genId}` with `{status: running, phase: collecting_preferences, agentStatuses: {food_drink: pending, outdoors_scenic: pending, nightlife: pending, culture_local: pending, logistics: pending, coordinator: pending}, requestedBy, startedAt, traceId}` → returns 202 `{generationId}`.
- Idempotency guard: if a generation for this trip is already `running` (and younger than a 5-min staleness cutoff), return 409 with the running generationId — double-clicks and racing members get the same job.
- Background task (FastAPI BackgroundTasks): assembles trip context + all participant preferences (one Firestore read per participant doc, including unclaimed admin-created travelers), builds the agent graph (T3.1), iterates `run_async` events; maps agent start/finish events → `agentStatuses.{agent}: running|done` Firestore updates (real ADK event names verified against the installed version, not assumed).
- Completion: writes `itinerary` (schema-validated), `status: complete`, `phase: done`, `metrics: {totalTokens, promptTokens, outputTokens, latencyMs, estCostUsd, llmCalls, toolCalls}` (token usage from ADK event usage metadata; cost from a flash-pricing constant in config).
- Failure: any exception → `status: error`, `error: <user-readable message>`, full traceback logged with traceId; the doc never sticks in `running`.
- Trip doc `status` → `generated` on first success; `latestGenerationId` pointer updated. Regeneration = new generation doc (history preserved).
- Document Cloud Tasks as the production upgrade (durable dispatch, retries, instance-restart survival) in a short `docs/scale-notes.md` section — interview artifact.

## Tools / Interfaces

- ADK `Runner` + `InMemorySessionService`; Firestore module from T1.1. Tests: fake runner emitting a scripted event sequence → assert the exact series of Firestore status writes; fake that raises mid-stream → assert error state lands.

## Patterns

- Status writes are merge-updates (never clobber the doc); every write carries traceId for log correlation.
- The generations doc shape MUST match the contract (T1.4) — if reality diverges, update the contract file in the same commit and flag it.

## Model routing

- Inherits T3.1 (flash everywhere, config-driven).

## Cost rules

- One generation = one runner session. Firestore progress writes ≤ ~15 per generation (status transitions only — no per-token writes).

## Acceptance criteria

- [ ] 202 + doc created on generate; concurrent second call → 409 with the live generationId (test with two simultaneous requests).
- [ ] Scripted-runner test shows agentStatuses progressing pending→running→done in order, ending `status: complete` with itinerary + metrics populated.
- [ ] Mid-stream exception test ends `status: error` with readable message; doc never left `running`.
- [ ] Real end-to-end run: metrics show plausible non-zero tokens/latency/cost; traceId present; trip status flips to `generated`.
- [ ] Generation context includes unclaimed participants and their admin-entered preferences; it does not limit planning to authenticated memberships.
- [ ] Non-member POST → 403.

## Updates (2026-06-10 — post T3.1/T2.2, free-tier switch)

- Build on the REAL T3.1 interfaces: `travel_agent/graph.py` — `build_trip_agent_graph(trip_context, group_preferences)`, `validate_itinerary_grounding(...)`, `ToolCallBudget`; output schema `travel_agent/schemas.py:Itinerary`.
- Preferences context = ALL participants (claimed + unclaimed via `GroupPreferencesEntry`), not just account-holding members — the participants roster is the planning unit.
- Gemini now runs on the AI Studio free tier (`GOOGLE_GENAI_USE_VERTEXAI=0`). The free tier throws transient 503 "high demand" — the job must retry agent steps with backoff (2 retries) and only then mark `status: error`. Keep `estCostUsd` computed from pricing constants regardless of billing tier (it's a metric, not a bill).
- The Vertex flip for demo day is one env var; do not hardcode either backend.
