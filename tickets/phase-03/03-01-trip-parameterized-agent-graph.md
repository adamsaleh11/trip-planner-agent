# T3.1 — Trip-parameterized ADK agent graph (5 category agents + coordinator)

Repo: trip-planner-agent (backend) · System: Mac · Type: Google ADK agents
Skill: tdd · Agent: Claude · Depends on: T1.3 · Parallel with: T2.2 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 3

## Goal

Replace the hardcoded 11-friend agent graph with builder functions that construct, per request, five category specialist agents and a coordinator — instructions templated from trip context and member preferences, output as a strict structured itinerary schema.

## Responsibilities

- Delete/retire hardcoded friend logic in `travel_agent/sub_agents/*` (names, diets, "Shubh vegetarian" rules — all of it). Keep `travel_agent/tools/` (Places/Routes).
- `build_category_agent(category, trip_context, group_preferences)` for: food_drink, outdoors_scenic, nightlife, culture_local, logistics. Each agent's instruction is templated from: destination, dates, lodging area, group size, and the prompt-stuffed structured chips + free-text wishlists of every member for that category.
- Empty-category path: when no member filled the category, the agent receives the OTHER categories' filled preferences + trip context and infers a best-fit profile; every recommendation it produces is flagged `suggested: true`. Filled categories produce `suggested: false` items (mixed allowed when an agent pads thin preferences — flag item-level, not category-level).
- Hard-constraint rule encoded in prompts: dietary restrictions and mobility notes are non-negotiable filters, never "preferences to balance".
- Category agents output a structured candidate list (venue name, place_id, address, lat/lng, why-it-fits, time-of-day fit, est. price level, suggested flag) — coordinator-ready, not prose.
- `build_coordinator_agent(trip_context)`: merges category candidates into the itinerary schema — days (from trip dates) → morning/afternoon/evening blocks → timed stops `{time, placeId, name, address, lat, lng, category, transport {mode, durationText | "Not available"}, whyItFits, suggested}`. Uses `estimate_route_time` for lodging→first-stop and stop→stop where it matters. Pydantic schema validates the final output; one repair retry on validation failure.
- Tools per category agent: `search_location_options` (category-tuned queries), `estimate_route_time` (coordinator + logistics only). `search_collective_memory` slot stubbed (no-op returning empty) — wired for real in T4.1.

## ADK patterns

- Per-request agent construction (no module-level singletons); ParallelAgent or asyncio fan-out for the 5 category agents, then coordinator; `InMemorySessionService` per run.
- Structured output enforced via output schema; self-check instruction: every venue must come from tool results — no invented places, missing data = "Not available".

## Model routing

- All agents `gemini-2.5-flash`. Model name read from config (single constant) — swap-ability is an interview point. No Pro escalation in MVP.

## Cost rules

- Max 3 Places queries per category agent; max 11 results per query; max 8 route estimates per generation (coordinator budget); no agent-to-agent debate; no retrieval loops; max output tokens configured per agent. Target: one generation ≤ ~15 LLM calls total.

## Acceptance criteria

- [ ] Unit tests (mocked tools + stubbed LLM where needed) prove: instructions contain the actual member preferences; empty category triggers the inference path; dietary restriction appears as a hard filter in the food agent's instruction.
- [ ] One real end-to-end run against live APIs for a synthetic trip (fake members, e.g. "Lisbon") produces a schema-valid itinerary where every stop's place_id exists in tool output captured during the run.
- [ ] Inferred content carries `suggested: true`; filled-preference content `false`.
- [ ] Zero references to real friend names anywhere in `travel_agent/` after this ticket (grep-verified).
- [ ] Generation respects the cost budget (tool-call counter asserted in the e2e run).
