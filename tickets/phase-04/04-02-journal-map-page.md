# T4.2 — Journal map page (Mapbox heatmap + waypoints)

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 + Mapbox GL JS
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.2 (trip data), T3.3 (itinerary view reuse) · Parallel with: T4.1/T4.3 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 4

## Goal

The marquee page: every trip in your journal as a glowing waypoint on a gorgeous dark world map with a heatmap feel — click one, fly to it, and relive the trip (itinerary, people, what everyone wanted).

## Responsibilities

- `/map`: full-bleed Mapbox GL JS map, dark style (`mapbox://styles/mapbox/dark-v11`), token from `NEXT_PUBLIC_MAPBOX_TOKEN`, globe projection with subtle initial spin-to-fit over the user's trips.
- Data: user's trips (destination lat/lng, name, dates, status, member count) via the API client. ONLY the signed-in user's trips — the map is personal; no other groups' data ever reaches this page.
- Layers: (1) heatmap layer from trip points — soft warm glow (amber/coral ramp matching the app theme), radius/intensity tuned to look like an aura, weighted by stop count so bigger trips glow brighter; (2) waypoint layer on top — custom circular markers with pulse on hover; completed trips brighter than planning-stage ones.
- Interaction: click/tap waypoint → `flyTo` (smooth ease, zoom ~10) → side sheet (desktop) / bottom sheet (mobile) with: trip name, dates, hero list of itinerary stops (compact reuse of T3.3 stop cards), member avatars, and a "what everyone wanted" section (per-participant preference highlights: chips + a free-text quote line each).
- Cluster gracefully if two trips are near each other (Mapbox cluster or slight spiderfy on zoom).
- Empty state (no trips): stylized globe + CTA to create a trip. Loading: map skeleton w/ shimmer. Mapbox failure (bad token/offline): fallback list view of trips, never a blank page.
- Journal list toggle: switch between map and a chronological journal card list (same data, shared sheet component).

## Tools / Interfaces

- mapbox-gl + react wrapper or direct refs (keep it light — no heavy map framework). Contract endpoints: trips list (with coords), trip detail, preferences, journal entries.

## Patterns

- frontend-tdd: data-fetch states tested with mocks; map layer config isolated in a pure function (style JSON in, layers out) so the glow tuning is testable/tweakable without the map.
- Lazy-load mapbox-gl (dynamic import, ssr:false) — keep it out of the main bundle.

## Cost rules

- Mapbox free tier: 50k loads/month — one map instance, no style reloads on data refresh (update sources, not the map).

## Acceptance criteria

- [ ] Map renders the user's trips as glowing heatmap-backed waypoints in dark theme; visually consistent with the app's accent palette (screenshot proof).
- [ ] Click → flyTo → sheet shows itinerary stops, members, and per-participant wants for that trip.
- [ ] Only the signed-in user's trips are requested/rendered (network assertion in test).
- [ ] Empty, loading, and mapbox-failure states all render intentionally; mobile bottom-sheet works at 375px.
- [ ] Lighthouse/bundle sanity: mapbox-gl loaded only on /map.
