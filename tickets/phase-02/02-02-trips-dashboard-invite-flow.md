# T2.2 — Trips dashboard, create trip, invite flow UI

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.1 + T1.4 contract · Parallel with: T3.1 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 2

## Goal

Users see their trips as journal-style cards, create a trip, and admins invite friends by email; invitees land on a polished accept page that handles every auth state.

## Responsibilities

- `/trips`: responsive card grid — destination name, date range, member avatars (stacked), status badge (Planning / Generated / Completed). Empty state sells the product ("Plan your first trip"). Cards link to `/trips/[id]`.
- Create-trip dialog: trip name, destination input (Places autocomplete via backend or Mapbox geocoding per contract — destination must resolve to {text, lat, lng, placeId} for the Phase 4 map), date range picker (shadcn calendar), optional lodging area text. Optimistic navigation to the new trip page.
- `/trips/[id]`: header (destination, dates, status), members section (avatars, names, admin badge), preference completion chips per member (from status endpoint — links into T2.3 forms), admin-only Invite button.
- Invite dialog (admin only): email input with validation → POST → success state showing "Email sent to X" + always the copyable invite link with copy button (the send-failed case still shows the link, per contract). List of pending invites with status.
- `/invite/[token]` (public route): fetches invite preview unauthenticated (trip name, destination, inviter). Three states: signed out → "Sign in to join" (preserves token through the login flow); signed in → "Join {trip}" button → accept → redirect to trip; invalid/used token → friendly error.
- Role awareness throughout: non-admins never see invite affordances.

## Tools / Interfaces

- Contract routes: trips CRUD, invites create/lookup/accept, members, preference status. shadcn: dialog, calendar, avatar, badge, toast.

## Patterns

- frontend-tdd full-state coverage: every fetch has loading skeleton, empty, error+retry.
- Invite token survives the sign-in redirect (query param or session storage) — test the signed-out path explicitly; it's the path every real invitee hits.

## Cost rules

- None. Keep Places autocomplete debounced (≥300ms) to respect API quota.

## Acceptance criteria

- [ ] Two-account flow works in the browser: A creates trip → invites B's email → B opens link signed-out → signs in → joins → both see updated member list.
- [ ] Destination selection always yields coordinates (asserted in the create payload).
- [ ] Copy-link works and is shown even when email send reports failure.
- [ ] Non-admin sees no invite UI; direct nav to another group's trip shows the 403 error state, not a crash.
- [ ] QA pass: mobile + desktop, skeletons on slow network (throttled), toasts for success/error.
