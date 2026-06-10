# T3.6 — Frontend live integration: real generation + real whims

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js integration pass
Skills: frontend-tdd · Agent: GEMINI (Antigravity, frontend) · Depends on: 03-02 + 03-04 (backend live), 03-03 + 03-05 (mock-built UI) · Parallel with: 04-01 (Claude), 04-03b (Codex)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 3 · Wave 3

## Coordination rules
- You own the trip pages, generation UI, whim UI, API client, and `lib/api/types.ts` this wave. Codex is working ONLY on `/dashboard` files — do not touch those.
- Backend shapes are governed by `docs/contracts/trip-journal-api.md`. If live responses differ from the contract, STOP and report the mismatch — do not silently adapt the UI.

## Goal

Swap the mock-built generation, manual plans, category-agent panels, and whim UIs onto the live backend and make the full product flow work end-to-end in the browser: fill preferences → see saved preferences → run one category independently → add manual plans → generate → watch live agent progress → itinerary; open Right Now → real suggestion → reroll.

## Responsibilities

- Replace the mock generations doc with the real Firestore listener on `trips/{tripId}/generations/{generationId}` (generationId from the live `POST /trips/{id}/generate` 202 response). Verify all six agent rows animate from real status transitions.
- Replace mock category result docs with real Firestore listeners on `trips/{tripId}/categoryResults/{category}`. Verify each category panel runs independently from its own Generate button.
- Replace mock manual plans with live `GET/POST/PATCH/DELETE /trips/{tripId}/manual-plans`.
- Verify saved preferences are visible after browser refresh for each participant/category before testing generation.
- Handle live 409 (generation already running): attach to the returned in-flight generationId instead of erroring. Verify by double-clicking Generate.
- Replace mock whim responses with live `POST /whims`: real geolocation path, typed-city fallback, trip-context path (tripId attached from trip page), reroll with accumulated `excludePlaceIds` against the live endpoint.
- Free-tier latency reality: generation may take 1–3 min and may include backend retry pauses — confirm the stale-guard (3 min no-update warning) doesn't false-fire during normal runs; loosen to 5 min if it does.
- Itinerary render check against real data: every stop field populates, `suggested` badges land where the data says, manual plans appear in the itinerary or surface a visible warning, "Not available" renders for missing transport, regenerate produces a new doc and swaps views.
- Fix any seams found (type mismatches vs contract, listener cleanup, error shapes) — report contract divergences rather than papering over them.

## Acceptance criteria

- [ ] Full live flow in the browser, two accounts: preferences (incl. one admin-filled unclaimed participant) → saved preferences visibly reload → one category generated independently → manual plan added by admin → generate → live progress → itinerary renders with correct suggested badges and manual plan inclusion.
- [ ] Each of the five category panels can generate independently; running one category does not trigger the other four.
- [ ] Manual plans CRUD works live with admin-only writes and member reads.
- [ ] Double-click Generate attaches to the running job (one generation doc, not two).
- [ ] Live whim from the trip page returns a real venue ≤ ~10s incl. retry headroom; 5 rerolls = 5 distinct places.
- [ ] Listener detaches on unmount/completion (verified via repeated navigation — no console leak warnings).
- [ ] No contract divergences remain unreported; any found are listed in the completion summary.

## Updates (2026-06-10 — per-agent runs)

- Live-integrate the per-category agent panels too: run one category alone → results render; edit a preference → stale hint appears; full generate reuses fresh results (verify "skipped_fresh" renders as reused, not re-run).
- Live-integrate manual plans too: add a morning/afternoon/evening plan, generate, and verify it is included or explicitly warned about.
