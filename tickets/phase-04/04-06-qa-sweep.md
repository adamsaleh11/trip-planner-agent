# T4.6 — Cross-app QA sweep + paper-cut fixes

Repo: trip-journal-web (primary) + trip-planner-agent (read-only repro) · System: Mac · Type: QA + targeted fixes
Skills: frontend-tdd (QA pass section) · Agent: CODEX (GPT 5.5, fullstack) · Depends on: 03-06 done · Parallel with: 04-03a (Claude), 04-05 (Gemini)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 4 · Wave 4

## Coordination rules
- Gemini is actively editing trip-page/journal files (04-05). You may EDIT only files outside its scope this wave: /map, /dashboard, /login, app shell polish, global styles, the API client's error mapping. For issues in Gemini-owned files, FILE them (create `QA-FINDINGS.md` in the frontend repo) — do not fix them yourself.
- Backend: do not modify. Reproduce backend-suspect bugs, document repro steps in QA-FINDINGS.md for Claude Code.

## Goal

A systematic quality pass over the whole product before deploy: every screen, every state, both viewport sizes, with paper cuts fixed in your owned files and everything else triaged into a findings file.

## Responsibilities

Run the full matrix and fix-or-file:
- **Flows** (two accounts, real backend): sign-up/in/out both providers · create trip (destination autocomplete) · participants add/edit + admin-filled preferences · invite (email + copy link) → claim flow · all 5 preference forms · generate → progress → itinerary · regenerate · whim (geo, typed city, trip-context, rerolls) · map page interactions · dashboard.
- **States**: loading skeletons everywhere data loads; empty states (new user, no trips, no generations); error states (kill the backend mid-session — every screen should degrade, not crash); 401 redirect; 403 non-member page.
- **Viewports**: 375px and 1280px on every screen; dark-theme consistency (no light-mode leaks in shadcn components).
- **Hygiene**: zero console errors/warnings on a clean walkthrough; no Firestore listener leaks (navigate in/out of progress view 5×); `mapbox-gl` not in the main bundle; no secrets in the frontend bundle (`grep` the build output for `GOCSPX`, `1//`, `AQ.`).
- **Fix** paper cuts in owned files (copy, spacing, truncation, focus states, toasts). **File** everything else in `QA-FINDINGS.md`: severity (blocker/major/minor), screen, repro steps, owner (Gemini/Claude).

## Acceptance criteria

- [ ] Full flow matrix executed; results logged in `QA-FINDINGS.md` (including "pass" rows — it doubles as the pre-deploy checklist).
- [ ] All blockers either fixed (owned files) or filed with repro steps and owner.
- [ ] Console-clean walkthrough; bundle checks pass (no mapbox-gl in main, no secret strings).
- [ ] Zero edits to Gemini-owned (04-05) files or backend code (verify via git diff).
- [ ] Findings handed off: blockers called out to the owner at wave end.
