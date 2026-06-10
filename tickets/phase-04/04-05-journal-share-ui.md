# T4.5 — Journal & anonymous-share UI

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js feature
Skills: read-contract, frontend-tdd · Agent: GEMINI (Antigravity, frontend) · Depends on: 04-01 (journal endpoints live), 03-06 done · Parallel with: 04-03a (Claude), 04-06 (Codex QA)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 4 · Wave 4

## Coordination rules
- You own trip pages + journal components this wave. Codex is on the QA sweep (04-06) — it may FILE issues against your files but only EDITS files you aren't touching; sync at wave end.
- Journal endpoint shapes come from `docs/contracts/trip-journal-api.md` as updated by 04-01 — read that section first.

## Goal

The trip-completion and memory loop in the UI: complete a trip, rate and journal each stop, opt in (or out) of sharing anonymized tips, save whims to the journal — feeding both the map page's richness and the collective memory.

## Responsibilities

- **Complete trip** (admin only): action on the trip page with confirmation ("moves to your journal; members can rate and journal stops") → `POST /trips/{id}/complete` → trip status badge flips to Completed; journal section appears.
- **Journal section** on completed trips: itinerary stops as journal cards — star rating (1–5), note textarea (≤1000), and a **"Share anonymously to help other travelers"** toggle, default OFF, with a one-line explainer ("your name and trip are never included"). Saves via `PUT /trips/{id}/journal/{placeId}`; edits re-save; unshare toggle works and is visually honest (shared ⇄ private state).
- **Privacy microcopy matters**: this is the product's trust surface — the toggle explainer and a small "what gets shared" info popover (destination, venue, rating, scrubbed tip — nothing identifying).
- **Whim → journal**: enable the "Save to journal" action on whim suggestion cards for trip-context whims (`POST /trips/{id}/journal/from-whim/{whimId}`); saved whims appear as journal cards.
- **My shares management**: a small "Shared tips" list (settings or profile menu) showing the user's shared entries with per-entry delete (`DELETE /me/shares/{opaqueId}`) — the right-to-erasure surface.
- States: unrated stubs vs filled cards, share-pending (scrub/embed happens server-side on save — show saved state immediately), delete confirmation.

## Acceptance criteria

- [ ] Admin completes a trip; members rate + journal stops; reload persists; non-members see nothing.
- [ ] Share toggle round-trips: ON → appears in "Shared tips" list; OFF/delete → gone (verify against backend, not just UI state).
- [ ] Trip-context whim saves to journal and renders as a journal card.
- [ ] Privacy explainer + info popover present and accurate to the 04-01 pipeline.
- [ ] QA pass: mobile, dark theme, all states; no edits to /dashboard files (Codex-owned).
