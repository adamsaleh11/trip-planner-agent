# Plan: Right Now And Manual Plans

> Source PRD: T3.4 Right Now spontaneity agent + manual plans backend patch, with grill-me decisions from 2026-06-10.

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `GET /trips/{tripId}/manual-plans`, `POST /trips/{tripId}/manual-plans`, `PATCH /trips/{tripId}/manual-plans/{planId}`, and `DELETE /trips/{tripId}/manual-plans/{planId}` manage manual plans. `POST /whims` returns one synchronous Right Now suggestion.
- **Schema**: manual plans live at `trips/{tripId}/manualPlans/{planId}`. Whims live at top-level `whims/{whimId}` with `uid`, optional `tripId`, suggestion, timestamps, and generation-compatible metrics.
- **Key models**: `ManualPlan` has `id`, `category`, `activity`, `timeOfDay`, nullable `date`, optional `placeId`, optional `address`, optional `notes`, `createdByUid`, `createdAt`, and `updatedAt`. Itinerary stops keep `suggested` and gain provenance via `source` plus optional `manualPlanId`. Itineraries can expose `manualPlanWarnings`.
- **Auth**: manual plan reads are trip-member only; manual plan writes are admin only. Trip-context whims require trip membership even when explicit coordinates are supplied. Whim docs are uid-scoped.
- **Coordinator boundary**: manual plans are itinerary/coordinator-only context. They never affect category agents, standalone category runs, category result freshness, or category stale states.
- **Manual plan inclusion**: manual plans are concrete user/admin-added commitments. The coordinator should place them into the itinerary when possible, marked `suggested: false` and `source: "manual_plan"`. If a plan cannot be placed, the itinerary should include a visible `manualPlanWarnings` entry.
- **Location precedence**: `POST /whims` resolves location as explicit `lat/lng`, then `tripId` destination, then typed `city`; missing usable location returns 422.
- **Right Now execution**: the endpoint is synchronous and cheap. A single flash agent interprets the whim and query angle; code filters Places candidates and performs the random selection. Reroll is client-managed via accumulated `excludePlaceIds`.
- **External services**: Google Places remains the venue source. Collective memory is best-effort and optional until the Phase 4 retrieval implementation replaces the stub. Free-tier LLM 503s retry once with a short backoff.

---

## Phase 1: Manual Plans CRUD

**User stories**: admin creates, edits, and deletes guided manual plans; members can read them; dates are validated against the trip range; non-admin writes are blocked.

### What to build

Expose trip-scoped manual plan management through the public API. The slice is complete when an admin can create a guided plan, a member can list it, invalid dates are rejected, and non-admins cannot mutate it.

### Acceptance criteria

- [ ] Admin can create a manual plan and receives the normalized stored shape.
- [ ] Trip members can list manual plans for the trip.
- [ ] Non-members cannot read manual plans.
- [ ] Non-admin members cannot create, update, or delete manual plans.
- [ ] `category`, `activity`, and `timeOfDay` are required and validated.
- [ ] `date`, when present, must fall within the trip date range.

---

## Phase 2: Manual Plans In Coordinator Itinerary

**User stories**: manual plans are passed only to the itinerary/coordinator agent; category agents are unaffected; generated itinerary includes manual plans as user-added stops with provenance; unschedulable plans produce visible warnings.

### What to build

Include fresh manual plans in the coordinator input every time a trip itinerary generation runs. Preserve category-agent behavior, extend itinerary output provenance, and allow the final itinerary to surface manual plan warnings.

### Acceptance criteria

- [ ] Coordinator receives `manualPlans` alongside `categoryResults` and `groupPreferences`.
- [ ] Category generation does not receive or stale on manual plan changes.
- [ ] Manual-plan stops can be represented with `suggested: false`, `source: "manual_plan"`, and `manualPlanId`.
- [ ] Final itinerary can include `manualPlanWarnings`.
- [ ] Scheduled manual plans pass grounding/validation without requiring category-agent tool results.

---

## Phase 3: Whim API Baseline

**User stories**: authenticated user posts a whim with lat/lng, city, or trip context; backend resolves location precedence; endpoint returns one synchronous suggestion and persists a whim doc with metrics.

### What to build

Add the public Right Now endpoint with dependency-injectable runtime behavior so the HTTP contract and persistence can be verified without live LLM or Places calls.

### Acceptance criteria

- [ ] Authenticated `POST /whims` returns `{suggestion, whimId}` synchronously.
- [ ] Missing location returns 422 with a clear message.
- [ ] Explicit `lat/lng` wins over trip destination while still allowing trip flavor.
- [ ] Trip-context whim checks membership and returns 403 for non-members.
- [ ] Successful whim persists a uid-owned doc with metrics.

---

## Phase 4: Whim Agent And Places Filtering

**User stories**: single flash agent interprets empty and oddball whims; backend caps Places queries, filters operational/rated/excluded candidates, and code performs the random selection.

### What to build

Wire the runtime to interpret a whim, issue at most two Places searches, filter usable candidates, and choose one result randomly in backend code. Keep fallback behavior friendly for nonsense or sparse results.

### Acceptance criteria

- [ ] Empty whim produces a time-aware search angle.
- [ ] Oddball whims map to plausible real venue searches.
- [ ] Places search is capped to two queries per request.
- [ ] Excluded place IDs are filtered before random selection.
- [ ] If strict filters produce too few candidates, the runtime relaxes gracefully without returning a 500.

---

## Phase 5: Trip-Flavored Whims And Reroll Hardening

**User stories**: trip-context whims require membership, use group preferences for flavor, optionally attach traveler tips, and support distinct rerolls through accumulated `excludePlaceIds`.

### What to build

Enrich trip-context whim requests with destination and group preference context. Treat collective memory tips as optional, and harden no-repeat behavior for repeated requests.

### Acceptance criteria

- [ ] Trip-context runtime input includes participant preferences.
- [ ] `travelersTip` is optional and never blocks a suggestion.
- [ ] Repeated requests with accumulated `excludePlaceIds` return distinct places while candidates remain.
- [ ] Exhausted candidate pools fail gracefully with a user-readable response.

---

## Phase 6: Error Handling, Metrics, And Live Smoke

**User stories**: free-tier 503s retry once; failures return friendly responses; whim docs use generation-compatible metrics; live tests verify empty whim, oddball whim, and no-repeat rerolls within the latency target.

### What to build

Finish operational behavior around latency, transient provider errors, and metrics parity with itinerary generations. Verify the live path when credentials are configured.

### Acceptance criteria

- [ ] Transient LLM 503/high-demand errors retry once with a short backoff.
- [ ] Provider failures return friendly HTTP errors instead of 500s.
- [ ] Whim metrics include latency, token counts, estimated cost, call counts, tokens per second, and billing tier.
- [ ] Live empty-whim request with coordinates returns a real nearby place in the latency target.
- [ ] Live oddball whim and five-reroll smoke paths work when credentials are present.
