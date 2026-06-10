# T3.3 — Generation UX: live agent progress + itinerary view

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.3 + generations-doc shape from contract (T1.4); integrates with live T3.2 when it lands · Parallel with: T3.2/T4.1 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 3

## Goal

The signature interaction: click Generate, watch six agents light up in real time, land on a beautiful day-by-day itinerary with real venues and honest AI-suggested labels.

## Responsibilities

- Generate button (replaces T2.3 placeholder): confirmation dialog summarizing what feeds the run — which members' preferences are in, which categories are empty ("AI will fill: Nightlife, Logistics"). Any member can generate.
- POST generate → navigate to/overlay the progress view; handle 409 (already running) by attaching to the running generation, not erroring.
- Live progress panel: Firestore client SDK realtime listener on `trips/{id}/generations/{genId}` (direct Firestore read per contract — no polling). Six rows (5 category agents + coordinator) with named, icon'd cards animating pending → running (pulse) → done (check) → error. Phase label ("Researching food & drink…"). Tasteful, not noisy.
- Error state: readable message + Retry (new POST). Stale guard: if doc stops updating > 3 min, show a soft warning with retry option.
- Itinerary view on `trips/[id]` once complete: day sections (Day 1 — Mon, Jul 6) → Morning/Afternoon/Evening blocks → stop cards: time, venue name, address, category icon, transport chip (mode + duration or "Not available"), "why it fits" line, and a clearly-styled "AI-suggested" badge on `suggested: true` stops.
- Regenerate action (with confirmation: "replaces current itinerary; previous runs kept"); metrics footer (subtle): generated in Xs · ~N tokens.
- Build against a hand-written mock generations doc FIRST (contract shape), then integrate live when T3.2 lands — this ticket must not block on backend timing.

## Tools / Interfaces

- Firebase Firestore web SDK (listener), API client (generate POST). shadcn: dialog, card, badge, separator; small CSS animations for agent states.

## Patterns

- frontend-tdd: progress panel states driven by mock docs in tests (pending/partial/complete/error/stale); itinerary renders from a fixture itinerary JSON.
- Listener cleanup on unmount/navigation; reconnect-safe.

## Cost rules

- One Firestore listener per open progress view; detach on completion +5s.

## Acceptance criteria

- [ ] With a mocked doc walked through its states, the panel animates correctly through all six agents, including the error path.
- [ ] Live integration: real generate shows real-time transitions without refresh; 409 attaches to the in-flight run (test by double-clicking).
- [ ] Itinerary renders every stop field; suggested badges appear exactly where the data says; empty transport renders "Not available", never blank.
- [ ] Regenerate produces a new run and the view swaps to the new itinerary on completion.
- [ ] QA pass: progress panel + itinerary on mobile width; long venue names truncate gracefully; no listener leaks (verified via repeated mount/unmount).
