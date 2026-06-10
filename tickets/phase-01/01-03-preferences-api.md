# T1.3 — Preference API for the 5 categories

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI service
Skill: tdd · Agent: Claude · Depends on: T1.2 · Parallel with: T2.1 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 1

## Goal

Members save and read per-category preferences (structured chips + free-text wishlist) for a trip, and the trip dashboard can show who has filled what. This schema is the contract the category agents consume in Phase 3 — get it right here.

## Responsibilities

- Categories enum: `food_drink`, `outdoors_scenic`, `nightlife`, `culture_local`, `logistics`.
- Pydantic schemas per category, all sharing `{freeText: str (max 2000 chars), updatedAt}` plus structured fields:
  - food_drink: dietaryRestrictions[] (vegetarian, vegan, halal, kosher, gluten_free, none), cuisineInterests[], mealBudget ($/$$/$$$), drinkInterests[] (local_drinks, cocktails, coffee, none), sportsBarInterest bool.
  - outdoors_scenic: activityLevel (chill/moderate/strenuous), interests[] (hikes, beaches, viewpoints, sunsets, water_activities, parks), photoSpotsPriority bool.
  - nightlife: vibe[] (clubs, bars, live_music, street_parties, chill_drinks, none), frequency (none/once_or_twice/most_nights), budget ($/$$/$$$).
  - culture_local: interests[] (markets, museums, landmarks, neighborhoods, local_events, side_quests), guidedTours (yes/no/maybe).
  - logistics: pace (relaxed/balanced/packed), wakeTime (early/mid/late), transport[] (walk, transit, rideshare, rental_car), dailyBudget ($/$$/$$$), mobilityNotes str.
- Storage: `trips/{tripId}/preferences/{uid}` single doc with one field per category (null = not filled) — one read fetches a member's everything.
- `PUT /trips/{id}/preferences/{category}` (member writes own only — uid from token, never from body), `GET /trips/{id}/preferences/me`, `GET /trips/{id}/preferences` (members only: all members' preferences — the group is planning together, visibility is intentional).
- `GET /trips/{id}/preferences/status`: per member × category boolean matrix + counts, for dashboard completion chips.

## Tools / Interfaces

- Pure FastAPI + Firestore module from T1.1. No LLM, no embedding — per-trip preferences are prompt-stuffed in Phase 3, never embedded (architectural decision).

## Patterns

- Validation is the product here: enums reject junk now so agent prompts never see garbage later.
- Category payloads are versioned with a `schemaVersion: 1` field for painless evolution.

## Cost rules

- One doc per member per trip keeps reads at members×1 for generation context assembly.

## Acceptance criteria

- [ ] Each of the 5 categories round-trips (PUT → GET) with full validation; invalid enum values → 422 with a clear field error.
- [ ] A member cannot write another member's preferences (uid is taken from the token; attempts via crafted body are ignored/rejected — test proves it).
- [ ] Status endpoint returns the correct member×category matrix after partial fills.
- [ ] Non-members get 403 on every preference route.
- [ ] Free text accepts emoji and multilingual content (the real user stories contain 🙏).
