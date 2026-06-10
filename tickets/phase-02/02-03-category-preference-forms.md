# T2.3 — Category preference forms (5 categories)

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: GEMINI (Antigravity, frontend) · Depends on: T2.2 · Parallel with: T3.2 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 2

## Goal

The preference capture experience — fast, fun, zero-friction forms for the 5 categories, targeted at trip participants rather than only authenticated members. Admins can fill preferences for manually added travelers before anyone accepts an invite.

## Responsibilities

- Preferences section on `/trips/[id]`: participant-first layout. Select a traveler profile, then show 5 category cards (Food & Drink, Outdoors & Scenic, Nightlife, Culture & Local, Logistics) each with icon, fill-state (Not filled / Filled), and "AI will fill this if left empty" hint on unfilled cards.
- Each category opens a sheet/drawer form generated from the contract schemas: chip/toggle groups for enums (multi-select chips for arrays, segmented control for single-selects like budget/pace), switches for booleans, textarea for mobility notes.
- Free-text wishlist prominent at the top of every form, with rotating placeholder examples drawn from real phrasing: "hikes with nice sunsets", "best gelato spots", "a bar to watch the game", "crazy street parties", "small side quests". Emoji-safe.
- Save per category using `PUT /trips/{tripId}/preferences/participants/{participantId}/{category}`, with saved-state feedback; forms rehydrate from `GET /preferences/participants/{participantId}`. Dirty-state guard on close.
- Edit rules: admins can edit every participant, including unclaimed manual travelers. Non-admins can edit only their claimed participant; other participants are read-only.
- Group view: per-participant completion matrix on the trip page (from status endpoint) — traveler rows × categories with checkmarks; tapping a filled participant+category opens view/edit depending on permission.
- Generate button placeholder (disabled, "Coming soon") wired into the layout so T3.3 drops in cleanly.

## Tools / Interfaces

- Contract participant and preference schemas as TypeScript types; shadcn: sheet, toggle-group, switch, textarea, tooltip.

## Patterns

- frontend-tdd: forms are the highest-interaction surface — test validation, rehydration, dirty-guard, and the empty→filled card transition.
- Schema-driven rendering where cheap (map enum arrays to chip groups) so backend schema tweaks don't mean form rewrites.

## Cost rules

- None. Saves are single-doc writes; no autosave-on-keystroke (save on submit) to stay in Firestore free tier.

## Acceptance criteria

- [ ] All 5 forms save, reload, and re-edit correctly for a selected participant against the real backend; enum values match contract exactly.
- [ ] Empty categories visibly communicate the AI-fallback behavior.
- [ ] Participant completion matrix updates after a save without full page reload.
- [ ] Admin-created unclaimed travelers can receive preferences before any invite is sent.
- [ ] A claimed traveler's fills are visible to the group per design; their forms are editable only by the claimed user or an admin.
- [ ] QA pass: drawer forms usable on mobile, chips wrap correctly, free-text accepts long multilingual input.
