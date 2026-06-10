# T3.3 — Generation UX: live agent progress + itinerary view

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: GEMINI (Antigravity, frontend) · Depends on: T2.3 + generations-doc shape from contract (T1.4); integrates with live T3.2 when it lands · Parallel with: T3.2/T4.1 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 3

## Goal

The signature interaction: each category has its own visible panel and generate button; click Generate Itinerary, watch six agents light up in real time, land on a beautiful day-by-day itinerary with real venues and honest AI-suggested labels.

**Wave 2 correction, must-have**: this ticket also fixes the trip-page UX gaps from Wave 1. Users must be able to see saved preferences after saving/reloading, run each category independently, and admins must be able to add guided manual plans that the itinerary generator will honor.

## Responsibilities

- Saved preferences visibility:
  - On trip page load, fetch and display saved preferences for the selected participant/category using `GET /trips/{tripId}/preferences/participants/{participantId}`.
  - The user should never see a blank form after saving unless the saved value is genuinely empty.
  - Show a compact read summary on each category panel: filled chips, key toggles, and the free-text wishlist preview.
  - After save, update the local UI immediately and revalidate from the backend; completion matrix and category panel must agree.
  - Include unclaimed admin-created participants in the same flow.
- Per-category independent agent panels:
  - Render five separate category divs/panels on `/trips/[id]`: Food & Drink, Outdoors & Scenic, Nightlife, Culture & Local, Logistics.
  - Each panel has its own **Generate** button that calls `POST /trips/{tripId}/categories/{category}/generate`.
  - Each panel listens to `trips/{tripId}/categoryResults/{category}` and renders its own status, stale hint, error state, metrics summary, and candidate results.
  - Candidate result rows show venue/name, address, time-of-day fit, why it fits, price level, and `AI-suggested` only when `suggested: true`.
  - A full itinerary generation must not be the only way to see category recommendations.
- Admin manual plans UI:
  - Add an admin-only "Manual plans" section on the trip page before Generate Itinerary.
  - This must be guided, not a freeform text box. Required inputs:
    - category: the same five category options.
    - activity: short activity/name input.
    - time of day: morning / afternoon / evening segmented control.
  - Optional inputs: date within trip range, address/place text, notes.
  - Read existing manual plans from `GET /trips/{tripId}/manual-plans`; create/edit/delete via the backend endpoints from T3.4.
  - Members who are not admins can see manual plans but cannot edit them.
  - The Generate Itinerary confirmation must list manual plans as required context so the user understands they will be included.
- Generate button (replaces T2.3 placeholder): confirmation dialog summarizing what feeds the run — which participants' preferences are in, which travelers/categories are empty ("AI will fill: Sarah / Nightlife, Logistics"). Any member can generate.
- The confirmation dialog must include all participants present in the trip, not just authenticated members, and must mention manual plans separately from preferences.
- POST generate → navigate to/overlay the progress view; handle 409 (already running) by attaching to the running generation, not erroring.
- Live progress panel: Firestore client SDK realtime listener on `trips/{id}/generations/{genId}` (direct Firestore read per contract — no polling). Six rows (5 category agents + coordinator) with named, icon'd cards animating pending → running (pulse) → done (check) → error. Phase label ("Researching food & drink…"). Tasteful, not noisy.
- Error state: readable message + Retry (new POST). Stale guard: if doc stops updating > 3 min, show a soft warning with retry option.
- Itinerary view on `trips/[id]` once complete: day sections (Day 1 — Mon, Jul 6) → Morning/Afternoon/Evening blocks → stop cards: time, venue name, address, category icon, transport chip (mode + duration or "Not available"), "why it fits" line, and a clearly-styled "AI-suggested" badge on `suggested: true` stops.
- Regenerate action (with confirmation: "replaces current itinerary; previous runs kept"); metrics footer (subtle): generated in Xs · ~N tokens.
- Build against a hand-written mock generations doc FIRST (contract shape), then integrate live when T3.2 lands — this ticket must not block on backend timing.

## Tools / Interfaces

- Firebase Firestore web SDK (listener), API client (generate POST, category generate POST, manual plans CRUD, preference reads). shadcn: dialog, card, badge, separator, segmented control/toggle group; small CSS animations for agent states.

## Patterns

- frontend-tdd: progress panel states driven by mock docs in tests (pending/partial/complete/error/stale); itinerary renders from a fixture itinerary JSON.
- Listener cleanup on unmount/navigation; reconnect-safe.

## Cost rules

- One Firestore listener per open progress view; detach on completion +5s.

## Acceptance criteria

- [ ] With a mocked doc walked through its states, the panel animates correctly through all six agents, including the error path.
- [ ] Saved preferences are visible after reload/return for every participant/category; form state, summary chips, and completion matrix agree.
- [ ] Every category has its own visible panel/div and independent Generate button; running Food & Drink does not run Nightlife, Culture, Logistics, etc.
- [ ] Category result listeners render per-category candidates and stale hints independently.
- [ ] Admin can add/edit/delete manual plans with guided category/activity/time-of-day fields; non-admin members can read but not edit.
- [ ] Generate confirmation lists manual plans as required itinerary context.
- [ ] Confirmation dialog names participants/travelers, not only authenticated members, and includes unclaimed admin-created travelers.
- [ ] Live integration: real generate shows real-time transitions without refresh; 409 attaches to the in-flight run (test by double-clicking).
- [ ] Itinerary renders every stop field; suggested badges appear exactly where the data says; empty transport renders "Not available", never blank.
- [ ] Regenerate produces a new run and the view swaps to the new itinerary on completion.
- [ ] QA pass: progress panel + itinerary on mobile width; long venue names truncate gracefully; no listener leaks (verified via repeated mount/unmount).

## Updates (2026-06-10 — post T3.1/T2.2)

- Confirmation dialog lists PARTICIPANTS (claimed + unclaimed, e.g. "Mom — filled by Adam") and which categories are empty — use `/trips/{id}/preferences/status` (keyed by participantId now, per updated contract).
- Generation may briefly retry on free-tier 503s — progress UI just keeps showing the running state; no special handling beyond the existing stale guard.

## Updates (2026-06-10 — per-agent UI panels)

- Each of the 5 category cards becomes an AGENT PANEL: "Run agent" button → live status (listener on `categoryResults/{category}`) → results list (venue, why-it-fits, suggested badge, travelers-tip slot) → rerun + stale hint ("preferences changed since this ran").
- The Generate Itinerary button shows a pre-flight summary: which categories have fresh results (will be reused, "skipped_fresh"), which will auto-run. Progress panel renders reused categories as instantly-done with a "reused" marker.
- Itinerary view unchanged. Mock-first still applies: mock both categoryResults docs and the generations doc.

## Updates (2026-06-10 — Wave 2 correction)

- Do not bury category generation behind the itinerary flow. Each category must be independently runnable from its own category div/panel.
- Do not leave saved preferences invisible after save/reload. Rehydrate and summarize them on the trip page.
- Add manual plans UI in this ticket, backed by the T3.4 manual-plans API. Manual plans are concrete admin commitments, not preferences, and must be shown in the Generate Itinerary preflight.
