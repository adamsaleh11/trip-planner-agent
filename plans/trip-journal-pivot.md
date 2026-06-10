# Plan: Trip Journal Product Pivot

> Source PRD: grill-me architecture session (2026-06-10) — multi-tenant trip journal with per-category preference agents, coordinator itinerary generation, email invites, anonymous collective trip memory (RAG), and a Mapbox journal map.

## Architectural decisions

Durable decisions that apply across all phases:

- **Repos**: This repo = Python backend (FastAPI wrapping ADK Runner, Cloud Run target). New separate repo = Next.js 15 + shadcn frontend (Vercel target). Local-first development; deploy is the final ticket.
- **Auth**: Firebase Auth (Google + email/password) on the client. FastAPI verifies ID tokens via `firebase-admin` on every request; every Firestore query is uid-scoped. No endpoint is reachable unauthenticated except invite-token lookup.
- **Database**: Firestore (free tier). Uniqueness encoded in doc IDs: invites keyed by token, memberships at `trips/{tripId}/memberships/{userId}`. User doc carries `memberTripIds` array for the journal/map query.
- **Key models**: `users`, `trips` (admin uid, destination, dates, lodging area/address text, status: planning|generated|completed), `memberships` (role: admin|member, access control only), `participants` (planning roster; can be unclaimed manual travelers or claimed by a uid), `invites` (token doc-ID, status), `preferences` (per trip+participant+category: structured chips + free text), `generations` (status per agent, trace_id, metrics, itinerary result), `journalEntries` (private by default), `collectiveMemoryMap` (private opaque-hash → owner mapping for deletion).
- **Categories**: 5 fixed — Food & Drink, Outdoors & Scenic, Nightlife, Culture & Local, Logistics. One specialist agent each + a coordinator agent.
- **Agents**: ADK agents constructed per-request with trip-parameterized instructions (no hardcoded people/rules). Coordinator fans out to category agents, merges into a structured itinerary: days → Morning/Afternoon/Evening blocks → timed stops with place_id, lat/lng, address, transport, "why it fits", and `suggested: true` on anything inferred. Empty category ⇒ agent infers from destination + other categories' filled preferences, all output flagged AI-suggested.
- **Generation execution**: `POST /trips/{id}/generate` returns 202; FastAPI background task drives `Runner.run_async`, streaming per-agent status to the trip's `generations` doc; frontend subscribes with a Firestore realtime listener. Cloud Tasks documented as the durable-queue production upgrade.
- **"Right Now" spontaneity agent**: app-wide instant agent — user types any momentary whim (or nothing) + location (browser geolocation, active trip destination, or typed city) → ONE random real suggestion in ≤ ~6s. Single flash agent, synchronous request (deliberate contrast with the async multi-agent itinerary engine — execution model matched to latency budget). The LLM interprets the whim and queries Places; **code does the random pick** from qualified candidates (LLMs are biased samplers); reroll excludes already-shown places. Whims persist (`whims/{whimId}`, uid-scoped) with the same metrics shape as generations; trip-context whims get group flavor + collective-memory tips and can be saved into the trip journal.
- **Preferences vs RAG split**: per-trip preferences are prompt-stuffed (small corpus; hard constraints like diet must never depend on retrieval recall). Vertex AI Vector Search serves only the **collective trip memory**.
- **Collective trip memory (RAG)**: journal notes/ratings are private by default; sharing is opt-in per entry. Shared payloads are anonymized before embedding: PII scrub (names/handles stripped), no user_id / trip_id / display names in the retrievable payload — only destination, category, venue place_id, rating, scrubbed note text, group-size bucket. Datapoint IDs are opaque hashes mapped in a private Firestore collection so entries are deletable (right-to-erasure) without being linkable from the index. Streaming-update index; deterministic IDs so edits overwrite. Seed with clearly synthetic demo entries only — never real user/trip data.
- **External services**: Google Places Text Search + Routes API (existing tools, kept), Vertex AI (Gemini via ADK, text-embedding-005, Vector Search), Gmail API (invite emails from the owner account; copyable invite link as fallback), Mapbox GL JS (journal map: dark style, heatmap-glow layer + waypoints, free tier).
- **Observability/evals**: ADK built-in OpenTelemetry spans exported to Cloud Trace; per-generation trace_id, token counts, latency, and cost stored on the generation doc. Offline eval runner (groundedness: every stop has a real place_id; constraint adherence: diet/budget respected; schema validity) writing results to Firestore, rendered on a dashboard page in the app.
- **Privacy invariants (all phases)**: itinerary/journal/member data visible only to trip members; collective memory can never answer "where did this person go" — only anonymized aggregate retrieval; no real personal data used as seed or fixture data.

---

## Phase 1: Backend platform — identity, trips, invites, preferences API

**User stories**: create an account; create a trip; admin adds traveler profiles immediately; admin optionally invites friends by email later; travelers' preferences can be filled before everyone has an account.

### What to build

The complete multi-tenant API surface in this repo, verified end-to-end with tests against the Firestore emulator-free path (uid-scoped fakes or a dev Firestore project). After this phase the entire product works via curl.

**Tickets**

1. **T1.1 — FastAPI skeleton + auth + data layer** *(skill: tdd)*
   App factory, Firebase ID-token verification dependency, Firestore client module, `GET /me` (auto-provisions user doc), structured JSON logging with request IDs from day one. Restructure repo: `app/` (api, services, models), keep `travel_agent/` tools.
2. **T1.2 — Trips, memberships, invites, Gmail sender** *(skill: tdd)*
   Trip CRUD with admin-role enforcement; participant roster endpoints (`Add traveler` separate from invite); invite create (token doc-ID) → Gmail API send + copyable link in response; `GET /invites/{token}` public lookup; accept endpoint creates membership + updates `memberTripIds`; members list endpoint.
3. **T1.3 — Preference API for 5 categories** *(skill: tdd)*
   Pydantic schemas per category (structured chips: diet, budget, pace, transport, interests + free-text wishlist), save/read endpoints scoped to trip membership, admin-on-behalf writes for unclaimed participants, per-participant completion status endpoint for the trip dashboard.
4. **T1.4 — API contract handoff** *(skill: contract-handoff)*
   Generate `docs/contracts/trip-journal-api.md`: every route, auth header, request/response schema, Firestore collections the frontend reads directly (generations listener), error shapes. This is the frontend repo's source of truth.

### Acceptance criteria

- [ ] All endpoints reject missing/invalid Firebase tokens; cross-tenant access (non-member hitting a trip) returns 403 in tests.
- [ ] Invite flow works end-to-end via curl: create → email received (or link copied) → accept as second account → membership visible.
- [ ] Preferences for all 5 categories round-trip with validation; completion status reflects who has filled what.
- [ ] Contract file exists and covers every route + the generations-listener Firestore path.

---

## Phase 2: Frontend app shell — sign in → trip → invite → preferences

**User stories**: sign up/sign in; see my trips; create a trip; add traveler profiles; fill preferences for each traveler; optionally invite people later to claim/manage their profile.

### What to build

The new Next.js repo, consuming the Phase 1 contract. After this phase a real user can do everything except generate.

**Tickets**

1. **T2.1 — Scaffold + auth + API client** *(skills: read-contract, frontend-tdd)*
   Next.js 15 (App Router) + shadcn + Tailwind, Firebase Auth (Google + email/password) with sign-in page and session handling, typed API client attaching ID tokens, protected layout, app shell/nav with a travel-journal visual identity (dark, warm accents).
2. **T2.2 — Trips dashboard + invite flow** *(skill: frontend-tdd)*
   Trip list (journal-style cards), create-trip dialog (destination autocomplete via Places, dates, lodging area/address), trip detail page with participants and members; admin Add Traveler UI separate from Invite UI; `/invite/[token]` accept page remains available but is not required to plan.
3. **T2.3 — Category preference forms** *(skill: frontend-tdd)*
   The 5 category forms: chip/toggle groups for structured fields + free-text wishlist with example placeholders drawn from real phrasing ("sunset hikes", "best gelato", "bar to watch the game"); per-participant completion indicators on the trip page; empty categories clearly marked "AI will fill this".

### Acceptance criteria

- [ ] A creator can add unclaimed traveler profiles and fill preferences for them without sending invites; invite acceptance still works as an optional account-access flow.
- [ ] All 5 category forms save and reload correctly; completion states update per member.
- [ ] Unauthenticated users are routed to sign-in; non-members cannot open a trip page.
- [ ] UI passes the frontend-tdd QA pass (states, responsive, dark mode consistent).

---

## Phase 3: Generation engine — multi-agent itinerary, live progress, itinerary UI

**User stories**: any member clicks Generate; watches agents work live; empty categories are AI-filled and labeled; the group gets a day-by-day itinerary with real venues.

### What to build

The core demo. Parameterized ADK agent graph + background execution + realtime progress + itinerary rendering.

**Tickets**

1. **T3.1 — Trip-parameterized agent graph** *(skill: tdd)*
   Rewrite agents: builder functions producing the 5 category agents + coordinator per request, instructions templated from trip context (destination, dates, lodging area/address, group size) + prompt-stuffed participant preferences; empty-category inference path with `suggested` flagging; structured itinerary output schema (Pydantic) the coordinator must satisfy; Places/Routes tools wired per category. Delete all hardcoded friend logic.
2. **T3.2 — Generation job + progress + metrics** *(skill: tdd)*
   `POST /trips/{id}/generate` (member-only, 202, idempotency guard against double-clicks); background task drives `Runner.run_async`, mapping events to per-agent status updates on the generation doc; on completion writes itinerary + metrics (trace_id, token counts, latency, est. cost); failure states recorded, job survivability notes for Cloud Tasks upgrade documented.
3. **T3.3 — Generation UX + itinerary view** *(skill: frontend-tdd)*
   Generate button with confirmation showing whose preferences are in; live progress panel (Firestore listener — 5 agents + coordinator with status animation); itinerary page: day sections, Morning/Afternoon/Evening blocks, timed stops with venue, address, transport, "why it fits", and visible "AI-suggested" badges; regenerate action.
4. **T3.4 — "Right Now" spontaneity agent + API** *(skill: tdd)*
   `POST /whims` synchronous endpoint; single flash agent interprets the whim (time-of-day aware when empty), 1–2 Places queries, code-level random pick from qualified candidates, excludePlaceIds reroll support; trip-context flavor; whim docs persisted with metrics; collective-memory tip slot stubbed until Phase 4.
5. **T3.5 — "Right Now" UI** *(skill: frontend-tdd)*
   Nav-level modal/sheet reachable anywhere + inline card on trip pages; free-text whim input with empty-submit surprise mode; geolocation with typed-city fallback; suggestion card (open-now badge, whyThis, travelers tip, Maps link); reroll with session history strip; "Save to journal" action slot (activates in Phase 4).

### Acceptance criteria

- [ ] Generate on a trip with mixed filled/empty categories produces a valid structured itinerary where every stop has a real Places place_id and inferred content is flagged `suggested`.
- [ ] Progress UI shows agents transitioning pending → running → done live without polling code.
- [ ] Generation doc records trace_id, tokens, latency, and cost for every run; double-click does not start a second job.
- [ ] A failed generation surfaces a user-readable error state and is retryable.
- [ ] A whim ("something sweet", or empty) returns one real nearby suggestion in ≤ ~6s; rerolls never repeat a place within a session; oddball asks ("I wanna dye my hair") resolve to real venues, never errors.
- [ ] Whim from a trip page is group-flavored; non-members of the trip get 403 on trip-context whims.

---

## Phase 4: Journal, collective memory (RAG), map page, ship

**User stories**: completed trips appear in my journal; I can rate stops and write notes; I can opt in to sharing anonymized tips that improve everyone's future itineraries; I see all my trips on a beautiful heatmap-style map; the system is observable and evaluated; it's deployed.

### What to build

The journal/memory loop, the marquee map, and the production-readiness layer.

**Tickets**

1. **T4.1 — Journal + anonymous collective memory** *(skill: tdd)*
   Mark-trip-completed flow → journal entries per stop (rating + note, private by default); opt-in share pipeline: PII scrub → embed (text-embedding-005) → streaming upsert to Vector Search with opaque-hash datapoint IDs and anonymized payload (destination, category, place_id, rating, scrubbed text, group-size bucket); deletion endpoint that resolves the private hash map and removes datapoints; retrieval tool (`search_collective_memory`) wired into the category agents AND the Right Now whim agent (travelersTip on spontaneous suggestions), filtered by destination+category; whim→journal endpoint activating T3.5's "Save to journal" action so spontaneous outings join the trip's story; verify the streaming index (create if current index is batch); seed with synthetic demo entries only.
2. **T4.2 — Journal map page** *(skill: frontend-tdd)*
   Mapbox GL dark style; trips as glowing waypoints over a heatmap layer weighted by visit density; fly-to on select; trip popover/sheet showing itinerary summary, members, and what each member wanted (trip-members only); journal list view alongside the map; loading/empty states polished.
3. **T4.3 — Observability + eval dashboard** *(skill: tdd)*
   ADK OTel spans exported to Cloud Trace (trace per generation AND per whim, spans per agent/tool); eval runner over a ~10-case golden set scoring groundedness, constraint adherence, schema validity → results to Firestore; dashboard page in the app: recent generations and recent whims side by side (latency/tokens/cost — the two execution models contrasted), eval scores over time, link-out to Cloud Trace.
4. **T4.4 — Deploy + final handoff** *(skill: contract-handoff)*
   Backend → Cloud Run (env/secrets via Secret Manager), frontend → Vercel; CORS + auth verified in prod; smoke-test the full flow deployed; final contract/architecture doc covering scale path (Cloud Tasks, index sharding, multi-region) — the interview narrative artifact.

### Acceptance criteria

- [ ] Completing a trip creates journal entries; shared entries are retrievable by a *different* account's generation for the same destination, with zero identifying fields in the retrieved payload.
- [ ] Deletion removes a shared entry from the index (verified by retrieval before/after).
- [ ] Map renders all completed trips with heatmap glow + popovers; non-members never see another group's trip details.
- [ ] Eval runner produces scores on the golden set; dashboard shows them plus per-generation metrics; a trace for a real generation is visible in Cloud Trace.
- [ ] A trip-context whim can be saved to the journal and (if shared) flows into collective memory like any other entry.
- [ ] Deployed app passes the end-to-end smoke test (sign up → trip → invite → preferences → generate → whim → journal → map).
