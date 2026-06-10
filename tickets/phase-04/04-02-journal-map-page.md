# T4.2 — Journal map page (MapCN heatmap + waypoints)

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 + MapCN
Skills: read-contract, frontend-tdd · Agent: CODEX (GPT 5.5, fullstack) · Depends on: T2.2 (trip data), T3.3 (itinerary view reuse) · Parallel with: T4.1/T4.3 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 4

## Goal

The marquee page: every trip in your journal as a glowing waypoint on a gorgeous dark world map with a heatmap feel — click one, fly to it, and relive the trip (itinerary, people, what everyone wanted).

## Responsibilities

- `/map`: full-bleed MapCN map in a dark visual treatment, configured from the MapCN environment variables used by the frontend repo. Fit the initial viewport around the signed-in user's trip destinations.
- Data: user's trips (destination lat/lng, name, dates, status, member count) via the API client. ONLY the signed-in user's trips — the map is personal; no other groups' data ever reaches this page. Destination coordinates and `placeId` already come from the wired Google Places API flow; T4.2 must consume them, not rebuild destination autocomplete/geocoding.
- Layers/overlays: (1) heatmap-style glow from trip points — soft warm aura (amber/coral ramp matching the app theme), radius/intensity tuned by visit density or stop count so bigger trips glow brighter; (2) waypoint overlay on top — custom circular markers with pulse on hover; completed trips brighter than planning-stage ones.
- Interaction: click/tap waypoint → `flyTo` (smooth ease, zoom ~10) → side sheet (desktop) / bottom sheet (mobile) with: trip name, dates, hero list of itinerary stops (compact reuse of T3.3 stop cards), member avatars, a "what everyone wanted" section (per-participant preference highlights: chips + a free-text quote line each), and a compact "planned manually" section when the trip has admin manual plans.
- Cluster gracefully if two trips are near each other using MapCN's clustering support or a small client-side spiderfy/offset strategy on zoom.
- Empty state (no trips): stylized map/globe treatment + CTA to create a trip. Loading: map skeleton w/ shimmer. Map provider failure (bad token/offline/blocked script): fallback list view of trips, never a blank page.
- Journal list toggle: switch between map and a chronological journal card list (same data, shared sheet component).

## Tools / Interfaces

- MapCN frontend SDK/components or direct refs, following the repo's established wrapper pattern if one exists. Keep the map implementation isolated behind a small local adapter so provider setup, markers, viewport fitting, and teardown are not spread through page code.
- Contract endpoints: trips list (with coords), trip detail, preferences, manual plans, journal entries. Destination lookup is already handled by the Google Places API-backed create-trip flow and is out of scope for this ticket.

## Patterns

- frontend-tdd: data-fetch states tested with mocks; map point normalization and glow/marker config isolated in pure functions so tuning is testable/tweakable without loading the map provider.
- Lazy-load MapCN map code (dynamic import, ssr:false) — keep provider SDK code out of the main bundle.
- Do not add new destination-search UI or geocoding logic here. Assert that trips without coordinates degrade to list-only rendering and surface a non-blocking data-quality state.

## Cost rules

- One map instance on `/map`; update overlays/sources when trip data changes instead of reinitializing the provider. Avoid provider calls beyond what MapCN needs to render the current user's map.

## Acceptance criteria

- [ ] Map renders the user's trips as glowing heatmap-backed waypoints in dark theme; visually consistent with the app's accent palette (screenshot proof).
- [ ] Click → flyTo → sheet shows itinerary stops, members, and per-participant wants for that trip.
- [ ] Trip sheet shows admin manual plans when present, without mixing them up with participant preferences.
- [ ] Only the signed-in user's trips are requested/rendered (network assertion in test).
- [ ] Empty, loading, missing-coordinate, and map-provider-failure states all render intentionally; mobile bottom-sheet works at 375px.
- [ ] Lighthouse/bundle sanity: MapCN SDK code is lazy-loaded only on `/map`.
- [ ] Tests cover that the page consumes existing Google Places-derived `destination.lat`, `destination.lng`, and `destination.placeId` fields without making destination search/geocoding calls.

## Updates (2026-06-10 — post T2.2)

- The trip sheet's "what everyone wanted" section is per-PARTICIPANT (claimed + unclaimed; use displayName from the participants roster), per the updated contract shapes.
- Map provider changed from Mapbox to MapCN. Google Places API destination search is already wired upstream, so this ticket starts from persisted destination coordinates/place IDs.
