# T2.3 — Category preference forms (5 categories)

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.2 · Parallel with: T3.2 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 2

## Goal

The preference capture experience — fast, fun, zero-friction forms for the 5 categories that make people actually fill them, with free-text wishlists as the star input.

## Responsibilities

- Preferences section on `/trips/[id]`: 5 category cards (Food & Drink, Outdoors & Scenic, Nightlife, Culture & Local, Logistics) each with icon, fill-state (Not filled / Filled ✓), and "AI will fill this if left empty" hint on unfilled cards.
- Each category opens a sheet/drawer form generated from the contract schemas: chip/toggle groups for enums (multi-select chips for arrays, segmented control for single-selects like budget/pace), switches for booleans, textarea for mobility notes.
- Free-text wishlist prominent at the top of every form, with rotating placeholder examples drawn from real phrasing: "hikes with nice sunsets", "best gelato spots", "a bar to watch the game", "crazy street parties", "small side quests". Emoji-safe.
- Save per category (PUT), with saved-state feedback; forms rehydrate from `GET /preferences/me`. Dirty-state guard on close.
- Group view: per-member completion matrix on the trip page (from status endpoint) — avatars × categories with checkmarks; tapping a filled member+category a member can view (group preferences are visible to members by design).
- Generate button placeholder (disabled, "Coming soon") wired into the layout so T3.3 drops in cleanly.

## Tools / Interfaces

- Contract preference schemas as TypeScript types; shadcn: sheet, toggle-group, switch, textarea, tooltip.

## Patterns

- frontend-tdd: forms are the highest-interaction surface — test validation, rehydration, dirty-guard, and the empty→filled card transition.
- Schema-driven rendering where cheap (map enum arrays to chip groups) so backend schema tweaks don't mean form rewrites.

## Cost rules

- None. Saves are single-doc writes; no autosave-on-keystroke (save on submit) to stay in Firestore free tier.

## Acceptance criteria

- [ ] All 5 forms save, reload, and re-edit correctly against the real backend; enum values match contract exactly.
- [ ] Empty categories visibly communicate the AI-fallback behavior.
- [ ] Completion matrix updates after a save without full page reload.
- [ ] A second member's fills are visible to the group per design; their forms are not editable by others.
- [ ] QA pass: drawer forms usable on mobile, chips wrap correctly, free-text accepts long multilingual input.
