# T3.6 — Frontend live integration: real generation + real whims

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js integration pass
Skills: frontend-tdd · Agent: GEMINI (Antigravity, frontend) · Depends on: 03-02 + 03-04 (backend live), 03-03 + 03-05 (mock-built UI) · Parallel with: 04-01 (Claude), 04-03b (Codex)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 3 · Wave 3

## Coordination rules
- You own the trip pages, generation UI, whim UI, API client, and `lib/api/types.ts` this wave. Codex is working ONLY on `/dashboard` files — do not touch those.
- Backend shapes are governed by `docs/contracts/trip-journal-api.md`. If live responses differ from the contract, STOP and report the mismatch — do not silently adapt the UI.

## Goal

Swap the mock-built generation and whim UIs onto the live backend and make the full product flow work end-to-end in the browser: fill preferences → generate → watch live agent progress → itinerary; open Right Now → real suggestion → reroll.

## Responsibilities

- Replace the mock generations doc with the real Firestore listener on `trips/{tripId}/generations/{generationId}` (generationId from the live `POST /trips/{id}/generate` 202 response). Verify all six agent rows animate from real status transitions.
- Handle live 409 (generation already running): attach to the returned in-flight generationId instead of erroring. Verify by double-clicking Generate.
- Replace mock whim responses with live `POST /whims`: real geolocation path, typed-city fallback, trip-context path (tripId attached from trip page), reroll with accumulated `excludePlaceIds` against the live endpoint.
- Free-tier latency reality: generation may take 1–3 min and may include backend retry pauses — confirm the stale-guard (3 min no-update warning) doesn't false-fire during normal runs; loosen to 5 min if it does.
- Itinerary render check against real data: every stop field populates, `suggested` badges land where the data says, "Not available" renders for missing transport, regenerate produces a new doc and swaps views.
- Fix any seams found (type mismatches vs contract, listener cleanup, error shapes) — report contract divergences rather than papering over them.

## Acceptance criteria

- [ ] Full live flow in the browser, two accounts: preferences (incl. one admin-filled unclaimed participant) → generate → live progress → itinerary renders with correct suggested badges.
- [ ] Double-click Generate attaches to the running job (one generation doc, not two).
- [ ] Live whim from the trip page returns a real venue ≤ ~10s incl. retry headroom; 5 rerolls = 5 distinct places.
- [ ] Listener detaches on unmount/completion (verified via repeated navigation — no console leak warnings).
- [ ] No contract divergences remain unreported; any found are listed in the completion summary.
