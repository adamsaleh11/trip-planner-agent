# T3.2 — Generation jobs: per-category agent runs + coordinator, live progress, metrics

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI + ADK Runner
Skill: tdd · Agent: CLAUDE CODE (backend) · Depends on: T3.1 (done) · Parallel with: 02-03 (Gemini), 03-05 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 3 · Wave 1
CONSOLIDATED 2026-06-10 — single source of truth; supersedes the earlier draft and its appended update notes. Includes: independent per-agent runs, participants model, AI Studio free-tier reality.

## Goal

Two execution surfaces over the T3.1 agent graph, both 202 + background job + Firestore live progress:
1. **Per-category runs** — each of the 5 category agents is independently runnable and writes its own visible results doc (each agent gets its own UI panel on the frontend).
2. **Coordinator run** — the itinerary agent composes from fresh stored category results + ALL participants' preferences, auto-running missing/stale categories first.

## Build on (real, existing interfaces — do not reinvent)

- `travel_agent/graph.py`: `build_category_agent(...)`, `build_coordinator_agent(...)`, `build_trip_agent_graph(...)`, `validate_itinerary_grounding(...)`, `ToolCallBudget`, `search_collective_memory` (stub until T4.1).
- `travel_agent/schemas.py`: `CategoryCandidate`, `CategoryCandidateList`, `Itinerary` (+ blocks/stops).
- `app/` platform: `Repository` (get/set/update/list), `require_member`/`require_admin` in `app/services/trips.py`, `GroupPreferencesEntry` in `app/models/preferences.py` — **the planning unit is PARTICIPANTS (claimed + unclaimed), not just account members**; auth dependency; structured logging with request_id.
- Contract: `docs/contracts/trip-journal-api.md` §3.10 + §5.2 — the frontend mocks against these shapes. **If implementation diverges, update the contract in the same commit and announce it.**

## Responsibilities

### 1. `POST /trips/{tripId}/categories/{category}/generate` — member only
- 202 `{"category": "..."}`; 409 if that category is already `running` (younger than a 5-min staleness cutoff); 404 unknown category; 403 non-member.
- Background task: assemble that category's context from all participants' preferences (empty category → T3.1 inference path), run the single category agent, write to `trips/{tripId}/categoryResults/{category}`:
  `{status: running|complete|error, candidates: [CategoryCandidate dump incl. suggested flag], sourceParticipantIds, metrics, traceId, updatedAt, preferencesVersion, error?}`
- `preferencesVersion` = max preference `updatedAt` for that category at run time. Reads expose advisory `stale: true|false` — never a hard block.

### 2. `POST /trips/{tripId}/generate` — member only, the coordinator
- 202 `{"generationId": "..."}`; 409 with the running generationId when one is in flight (client attaches, doesn't error).
- Creates `trips/{tripId}/generations/{generationId}` per contract §5.2: `{status, phase, agentStatuses: {5 categories + coordinator}, requestedBy, startedAt, traceId}`.
- Orchestration per category: fresh stored result (`preferencesVersion` >= current preference version) → reuse, `agentStatuses.{category}: "skipped_fresh"`; missing/stale → run in parallel (`pending → running → done`). Then the coordinator composes the `Itinerary` from category results + participants' preferences; schema-validate + `validate_itinerary_grounding` with one repair retry.
- Completion: `itinerary`, `status: complete`, `phase: done`, `metrics: {totalTokens, promptTokens, outputTokens, latencyMs, estCostUsd, llmCalls, toolCalls, tokensPerSecond, billingTier: "free"|"vertex"}`. Trip status → `generated`; `latestGenerationId` updated; regeneration = new doc (history preserved).
- Failure: `status: error` + user-readable message; traceback logged with traceId; the doc never sticks in `running`.

### 3. Runtime/config hardening
- Move env loading to explicit app startup with absolute paths (currently an import side-effect with a relative path in `travel_agent/tools/location_research.py` — breaks when the server starts from another CWD). Backend selection (`GOOGLE_GENAI_USE_VERTEXAI`) must be deterministic.
- AI Studio free tier throws transient 503 "high demand": retry agent steps with backoff (2 retries) before marking error. `estCostUsd` always computed from pricing constants (it's a metric, not a bill); record `billingTier`. The Vertex flip is one env var — hardcode neither backend.
- Document Cloud Tasks as the durable-queue production upgrade in `docs/scale-notes.md`.

## Tools / Interfaces

- ADK `Runner` + `InMemorySessionService` per job; FastAPI BackgroundTasks; Firestore via the existing `Repository`. Status writes are merge-updates (never clobber); every write carries traceId. Real ADK event names verified against the installed version (2.0.0b1), not assumed.
- Tests: fake runner emitting scripted event sequences → assert the exact series of status writes for BOTH surfaces; mid-stream exception test; concurrent double-POST idempotency tests on both endpoints; reuse-vs-stale decision as a pure-function unit test on `preferencesVersion`.

## Cost rules

- One runner session per job. Reused fresh categories consume ZERO model calls — assert it. Status writes ≤ ~15 per coordinator run (transitions only, no per-token writes). Free-tier rate limits are the constraint, not dollars.

## Acceptance criteria

- [ ] Single category run end-to-end: 202 → categoryResults doc progresses running → complete with grounded candidates; concurrent re-run → 409; non-member → 403.
- [ ] Editing that category's preferences then reading its results shows `stale: true` (advisory).
- [ ] Coordinator with mixed state: fresh categories show `skipped_fresh` and consume zero model calls; missing/stale auto-run; final itinerary is schema-valid with every stop's placeId traceable to tool output.
- [ ] Scripted-runner tests prove the status sequences for both surfaces; mid-stream exception ends `status: error`, never stuck `running`.
- [ ] Generation context includes unclaimed participants and their admin-entered preferences; planning is never limited to authenticated memberships.
- [ ] Real live run (free tier) records plausible metrics incl. tokensPerSecond + billingTier; trip flips to `generated`.
- [ ] Contract §3.10/§5.2 match reality at merge (updated in-commit if diverged); env loading is CWD-independent.
