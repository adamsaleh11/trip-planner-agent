# T2.2 — Trips dashboard, create trip, invite flow UI

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js 15 app
Skills: read-contract, frontend-tdd · Agent: Codex · Depends on: T2.1 + T1.4 contract · Parallel with: T3.1 (Claude)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 2

## Goal

Users see their trips as journal-style cards, create a trip, add traveler profiles immediately, and optionally invite those travelers by email; invitees land on a polished accept page that handles every auth state and claims the matching traveler profile.

## Responsibilities

- `/trips`: responsive card grid — destination name, date range, member avatars (stacked), status badge (Planning / Generated / Completed). Empty state sells the product ("Plan your first trip"). Cards link to `/trips/[id]`.
- Create-trip dialog: trip name, destination input (Places autocomplete via backend or Mapbox geocoding per contract — destination must resolve to {text, lat, lng, placeId} for the Phase 4 map), date range picker (shadcn calendar), optional lodging area text. Optimistic navigation to the new trip page.
- `/trips/[id]`: header (destination, dates, status), participant roster section (traveler profiles, claimed/unclaimed state, optional email/notes), members/access section if useful, preference completion chips per participant (from status endpoint — links into T2.3 forms).
- Admin-only **Add Traveler** action: create an unclaimed participant with display name, optional email, and optional notes. This must not send an invite.
- Admin-only **Invite Traveler** action: invite either an existing participant (`participantId` + email) or a new email. Always show "Email sent to X" + copyable invite link with copy button; the send-failed case still shows the link, per contract.
- Merge/claim behavior: if an admin creates "Sarah" first and later invites Sarah using that participant, accepting the invite must show the same participant as claimed by Sarah's uid, not a duplicate traveler.
- `/invite/[token]` (public route): fetches invite preview unauthenticated (trip name, destination, inviter). Three states: signed out → "Sign in to join" (preserves token through the login flow); signed in → "Join {trip}" button → accept → redirect to trip; invalid/used token → friendly error.
- Role awareness throughout: non-admins never see invite affordances.

## Tools / Interfaces

- Contract routes: trips CRUD, participants list/create/update, invites create/lookup/accept, members, preference status. shadcn: dialog, calendar, avatar, badge, toast.

## Patterns

- frontend-tdd full-state coverage: every fetch has loading skeleton, empty, error+retry.
- Invite token survives the sign-in redirect (query param or session storage) — test the signed-out path explicitly; it's the path every real invitee hits.

## Cost rules

- None. Keep Places autocomplete debounced (≥300ms) to respect API quota.

## Acceptance criteria

- [ ] Admin can create a trip, add traveler profiles without sending invites, and see those travelers in the roster.
- [ ] Two-account flow works in the browser: A creates traveler B → invites B using that participant → B opens link signed-out → signs in → joins → the original traveler becomes claimed by B with no duplicate.
- [ ] Destination selection always yields coordinates (asserted in the create payload).
- [ ] Copy-link works and is shown even when email send reports failure.
- [ ] Non-admin sees no Add Traveler or Invite Traveler UI; direct nav to another group's trip shows the 403 error state, not a crash.
- [ ] QA pass: mobile + desktop, skeletons on slow network (throttled), toasts for success/error.
