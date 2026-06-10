# T3.4 — "Right Now" spontaneity agent + API

Repo: trip-planner-agent (backend) · System: Mac · Type: Google ADK agent (single, synchronous)
Skill: tdd · Agent: Claude · Depends on: T3.1 (reuses tools + builder patterns) · Parallel with: T2.3/T3.5 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 3

## Goal

An anytime, instant agent for "I'm bored": the user types whatever they feel like doing in the moment ("something sweet", "I wanna dye my hair", "somewhere to watch the game", or literally nothing) and gets ONE random, real, open-now-biased suggestion nearby — in seconds, not minutes. Deliberately the architectural opposite of the itinerary engine: single agent, synchronous, cheap.

## Responsibilities

- `POST /whims` (authenticated): body `{whimText: str (may be empty), location: {lat, lng} | {city: str}, tripId?: str, excludePlaceIds?: [str]}` → synchronous response `{suggestion: {placeId, name, address, lat, lng, category, whyThis, openNow|"Not available", mapsUri, travelersTip?}, whimId}`. Target p95 latency ≤ ~6s.
- Location resolution: explicit lat/lng (browser geolocation) wins; else tripId → trip destination (member-checked); else city string; none → 422 with clear message.
- `build_whim_agent(location_context, whim_text, trip_context?)`: single flash agent. Two-step flow:
  1. Agent interprets the whim (or invents an interesting angle when empty — time-of-day aware: morning → cafés/walks, night → late-night spots) and issues 1–2 `search_location_options` queries.
  2. **Code, not the LLM, does the dice roll**: backend filters candidates (operational, rated, not in excludePlaceIds) and picks RANDOMLY from the qualified pool — true spontaneity, since LLMs are biased samplers. Agent then writes the one-line `whyThis` for the chosen place.
- If on an active trip: prompt enriched with the trip's group preferences for flavor, and `search_collective_memory` (stub until T4.1 wires it; real after) may attach a `travelersTip` to the suggestion.
- Reroll = same endpoint with `excludePlaceIds` accumulated by the client; suggestions logged to `whims/{whimId}` {uid, whimText, suggestion, createdAt, tripId?} — feeds T4.1's "log this to my trip journal" tie-in and dashboard metrics in T4.3.
- Per-request metrics on the whim doc: latencyMs, tokens, estCostUsd (same metric shape as generations — dashboard reuses it).

## ADK patterns

- Single agent, per-request construction, `InMemorySessionService`, synchronous `run_async` consumed to completion inside the request (no background job — the contrast with T3.2 is an interview talking point: match execution model to latency budget).

## Model routing

- `gemini-2.5-flash`, same config constant as T3.1. High temperature for whim interpretation; randomness itself lives in code.

## Cost rules

- Max 2 Places queries per whim; max 1 LLM interpretation call + 1 short whyThis call (or one combined call); no route estimation; no retries beyond one repair. Per-whim cost target: a fraction of a cent.

## Acceptance criteria

- [ ] Empty whim + lat/lng returns a real open-now-biased place with whyThis in ≤ ~6s (live test).
- [ ] Oddball whims degrade gracefully: "I wanna dye my hair" returns a real salon/barber via Places; nonsense input returns a fun fallback suggestion, never a 500.
- [ ] Randomness test: same request 5× with accumulating excludePlaceIds yields 5 distinct places (no repeats).
- [ ] tripId path: non-member → 403; member gets trip-flavored suggestion (instruction content asserted in tests).
- [ ] Whim docs persist with metrics; uid-scoped (users can only read their own whims).

## Updates (2026-06-10 — post T3.1, free-tier switch)

- Reuse T3.1's patterns: per-request agent build like `build_category_agent` in `travel_agent/graph.py`, `ToolCallBudget` for the 2-Places-query cap, and the same model config constant (AI Studio free tier; Vertex flip via env).
- Free-tier 503s: one retry with short backoff, then a friendly "try again in a moment" error — never burn the ≤6s budget on long waits.
- Trip-context whims read the PARTICIPANTS' preferences (GroupPreferencesEntry), same as generation.
