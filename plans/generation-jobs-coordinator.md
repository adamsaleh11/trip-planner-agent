# Plan: Generation Jobs And Coordinator

> Source PRD: T3.2 generation jobs ticket and grill-me clarifications from 2026-06-10

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /trips/{tripId}/categories/{category}/generate` starts one independent category job. `POST /trips/{tripId}/generate` starts one coordinator generation job.
- **Schema**: category results live at `trips/{tripId}/categoryResults/{category}`. Coordinator generations live at `trips/{tripId}/generations/{generationId}`.
- **Key models**: category results expose `status`, `candidates`, `sourceParticipantIds`, `metrics`, `traceId`, `updatedAt`, `preferencesVersion`, `stale`, and optional fallback/error metadata. Generations expose `status`, `phase`, `agentStatuses`, `requestedBy`, `startedAt`, `traceId`, optional `itinerary`, `metrics`, and `error`.
- **Auth**: all generation endpoints are member-only and use existing trip membership guards.
- **External services**: ADK Runner executes category and coordinator agents; Google Places and Routes remain tool boundaries; collective memory is callable as a stub until the vector-memory phase lands.
- **Coordinator inputs**: the coordinator receives all five category result sets plus all participant preferences, including unclaimed participants.
- **Fallback behavior**: missing or failed category results do not remove the category from the coordinator input. The system retries, then creates fallback category recommendations from generic/inferred preferences and memory when available.
- **Suggested provenance**: `suggested` is decided per candidate. It is `false` only when a candidate directly traces to explicit current-trip participant preferences, and `true` for generic, inferred, padding, or memory-inspired recommendations.

---

## Phase 1: Category Result Job Baseline

**User stories**: member starts one category run; category panel receives live `running -> complete/error`; duplicate running category returns `409`; non-member blocked.

### What to build

Expose a member-only category generation endpoint that starts one category agent job, writes a running category result, completes with grounded candidates and metrics, and preserves the visible latest result for that category.

### Acceptance criteria

- [ ] Member POST returns `202 {"category": "<category>"}`.
- [ ] Unknown category returns `404`; non-member returns `403`.
- [ ] Fresh running category result returns `409`.
- [ ] Completed category result includes candidates, participant sources, metrics, trace id, update time, and preference version.

---

## Phase 2: Preference Freshness And Staleness

**User stories**: category results record `preferencesVersion`; reads expose advisory `stale`; edits after generation do not block UI but signal rerun.

### What to build

Record per-category preference update versions and mark existing category result docs stale when matching preferences change.

### Acceptance criteria

- [ ] Saving category preferences records an update version.
- [ ] Category generation stores the max relevant preference version.
- [ ] Editing the same category after generation marks that result `stale: true`.
- [ ] Staleness is advisory and does not delete prior candidates.

---

## Phase 3: Coordinator Generation Shell

**User stories**: member starts itinerary generation; duplicate generation returns existing running `generationId`; Firestore generation doc tracks phase and agent statuses.

### What to build

Expose a coordinator endpoint that creates a generation history doc, initializes agent progress, rejects duplicate in-flight generations with the existing id, and runs the background orchestration.

### Acceptance criteria

- [ ] Member POST returns `202 {"generationId": "<id>"}`.
- [ ] Existing running generation returns `409` with the current `generationId`.
- [ ] Generation doc includes status, phase, agent statuses, requester, start time, and trace id.
- [ ] Failures end in `status: "error"` and do not stay running.

---

## Phase 4: Coordinator Category Orchestration

**User stories**: coordinator reuses fresh category docs, auto-runs stale/missing categories, retries transient failures, and guarantees five category inputs.

### What to build

Before itinerary composition, inspect all five category result docs. Reuse fresh docs, run missing or stale categories, update per-agent statuses, and ensure the coordinator receives a complete five-category input map.

### Acceptance criteria

- [ ] Fresh category results are marked `skipped_fresh` and consume zero category model calls.
- [ ] Missing categories are run before coordinator composition.
- [ ] Stale categories are refreshed before coordinator composition.
- [ ] Coordinator receives all five category result sets.

---

## Phase 5: Fallback Category Recommendations

**User stories**: missing/failed category still produces usable category input through generic/inferred recommendations; same-location memory hook is respected when available; `suggested` remains item-level provenance.

### What to build

When a category agent fails after retries, generate fallback category candidates from generic destination assumptions, available participant context, and collective memory when available. Persist the fallback result as a usable complete category result with clear fallback metadata.

### Acceptance criteria

- [ ] Failed category auto-run can recover through fallback candidates.
- [ ] Fallback category result is `status: "complete"` with `fallback: true` and `fallbackReason`.
- [ ] Fallback candidates still use item-level `suggested` provenance.
- [ ] Coordinator generation completes when fallback provides usable candidates.

---

## Phase 6: Itinerary Build, Grounding, And Repair

**User stories**: coordinator builds schema-valid itinerary from five category inputs plus all participant preferences; every stop traces to tool/category output; one repair retry; trip flips to `generated`.

### What to build

Run the coordinator with persisted category results and participant preferences, validate the itinerary schema, validate stop grounding against captured tool outputs, retry one repair when needed, and update trip status.

### Acceptance criteria

- [ ] Final itinerary validates against the public itinerary schema.
- [ ] Every stop place id traces to category or coordinator tool output.
- [ ] Invalid grounding triggers one repair attempt before erroring.
- [ ] Successful generation writes itinerary, metrics, `phase: "done"`, and updates trip status/latest generation id.

---

## Phase 7: Metrics, Retry, And Runtime Hardening

**User stories**: token/tool/latency/cost metrics recorded; billing tier captured; AI Studio 503 retried; env loading is CWD-independent; backend selection deterministic.

### What to build

Wrap ADK calls in a runner adapter that records metrics, retries transient free-tier failures, computes estimated cost from constants, and loads configuration from absolute env paths at app startup.

### Acceptance criteria

- [ ] Metrics include token counts, latency, estimated cost, LLM calls, tool calls, tokens per second, and billing tier.
- [ ] Transient 503/high-demand failures retry before surfacing error.
- [ ] Env loading works from any process working directory.
- [ ] `GOOGLE_GENAI_USE_VERTEXAI` deterministically selects the backend.

---

## Phase 8: Contracts, Scale Notes, And End-To-End Verification

**User stories**: API contract matches implementation; Cloud Tasks upgrade documented; scripted-runner tests cover status sequences, exceptions, concurrency, reuse-vs-stale, participant scope, and fallback semantics.

### What to build

Update the contract and scale notes to match generation behavior, then verify through behavior-level tests and one live smoke path when credentials are available.

### Acceptance criteria

- [ ] Contract documents category results, generation docs, fallback metadata, stale semantics, and metrics.
- [ ] Scale notes document Cloud Tasks as the durable queue upgrade.
- [ ] Tests cover category generation, coordinator reuse, auto-run, fallback, stale edits, and concurrency conflicts.
- [ ] Live run records plausible metrics and updates the trip when credentials are configured.
