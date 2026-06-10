# T3.5 — "Right Now" UI

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.1 shell + T1.4 contract (whim endpoint section) · Parallel with: T3.2/T3.4 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 3

## Goal

The instant-gratification surface: a "Right Now" button available anywhere in the app — type anything (or nothing), get one delightful suggestion card in seconds, reroll until something clicks. Must feel like a slot machine, not a form.

## Responsibilities

- Nav entry "Right Now" (sparkle/dice icon) opening a modal/sheet from anywhere; also a prominent inline card on `/trips/[id]` for active trips ("Bored right now?") that passes the tripId.
- Input: single free-text field, placeholder rotating moods ("something sweet 🍦", "watch the game", "surprise me"); empty submit allowed = full surprise. Big single CTA.
- Location: request browser geolocation on first use (graceful denial → city text input, remembered); trip context auto-attached when launched from a trip page.
- Loading state: brief playful animation (dice roll / radar sweep) — synchronous call, no progress listener (per contract: whims are instant, unlike generations).
- Suggestion card: place name, category icon, address, open-now badge (or "Hours not available"), one-line whyThis, travelersTip quote styled distinctly when present, Maps link-out. Actions: **Another one** (reroll — client accumulates excludePlaceIds), **Take me there** (Maps), and when in trip context **Save to journal** (appears post-T4.1; hidden before).
- Reroll history strip: small thumbnails of rejected suggestions this session (tapping one brings it back).
- Error states: location unavailable, no results for the whim ("nothing nearby for that — try another mood"), API failure with retry. Never a dead end.

## Tools / Interfaces

- Contract: `POST /whims` request/response shapes. shadcn: dialog/sheet, command-style input, card, badge. Browser Geolocation API.

## Patterns

- frontend-tdd: mock the whim response for all states (success, tip-present, no-results, geo-denied); reroll exclusion list asserted in the request payload.
- The modal is reachable in ≤ 2 interactions from any screen — measure it.

## Cost rules

- Client debounces double-submits; excludePlaceIds capped at 20 per session.

## Acceptance criteria

- [ ] From any page: open → empty submit → suggestion card within the loading animation, using real geolocation.
- [ ] Reroll never repeats a place this session (request payload asserted); history strip restores a previous suggestion.
- [ ] Trip-context launch attaches tripId; travelersTip renders distinctly when the backend supplies one.
- [ ] Geo-denied flow works end-to-end with typed city, and the choice is remembered.
- [ ] QA pass: sheet on mobile 375px, animation tasteful, all error states styled, no console errors.
