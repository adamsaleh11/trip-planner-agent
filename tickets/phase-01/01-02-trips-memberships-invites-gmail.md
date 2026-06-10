# T1.2 — Trips, memberships, invites, Gmail invite sender

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI service
Skill: tdd · Agent: Claude · Depends on: T1.1 · Parallel with: T2.1 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 1

## Goal

The full multi-tenant trip lifecycle over HTTP: create a trip (creator becomes admin), add traveler participants separately from account access, invite by email via the Gmail API with a copyable-link fallback, accept an invite, list members — with tenant isolation enforced at every endpoint.

## Responsibilities

- `POST /trips` (name, destination {text, lat, lng, placeId}, startDate, endDate, lodgingArea optional) → creates `trips/{tripId}` with `status: planning`, `adminUid`, plus `memberships/{uid}` subdoc `{role: admin}`, appends to creator's `memberTripIds`, and creates a claimed participant for the creator.
- Participant roster: `GET /trips/{id}/participants` (members), `POST /trips/{id}/participants` and `PATCH /trips/{id}/participants/{participantId}` (admin). Participants are planning travelers and can be unclaimed manual profiles.
- `GET /trips` (mine), `GET /trips/{id}` (members only), `PATCH /trips/{id}` (admin only: name/dates/lodging), `DELETE` deferred — out of scope.
- `POST /trips/{id}/invites` (admin only, body: email, optional participantId) → creates `invites/{token}` (token = URL-safe secrets token as doc ID; uniqueness for free) with email, tripId, invitedBy, optional participantId, status pending, createdAt. Sends email via Gmail API; response always includes `inviteUrl` so the UI can offer copy-link even if send fails (send failure is logged, not fatal).
- Gmail sender service: OAuth2 client + stored refresh token from env (owner performs the one-time consent manually — documented in the ticket's setup notes). Plain HTML email: trip name, inviter name, button to `{FRONTEND_URL}/invite/{token}`.
- `GET /invites/{token}` — the ONLY unauthenticated read: returns trip name, destination, inviter display name, status. No member list, no dates leak.
- `POST /invites/{token}/accept` (authenticated) → idempotent: creates `memberships/{uid}` `{role: member}`, sets invite status accepted, appends to `memberTripIds`, and claims the linked participant (or unclaimed participant with matching email) instead of creating a duplicate. Accepting an already-accepted invite by the same user → 200; by a different user → 410.
- `GET /trips/{id}/members` (members only): uid, displayName, role, joinedAt.
- Authorization helpers: `require_member(trip_id, uid)` / `require_admin(trip_id, uid)` used as dependencies — every trip-scoped route goes through one of them.

## Tools / Interfaces

- Gmail API (`google-api-python-client`) with `gmail.send` scope; sender = owner's account.
- Tests: fake Firestore from T1.1; Gmail sender behind an interface with a recording fake.

## Patterns

- Token-as-doc-ID for invite uniqueness; membership-doc-ID-as-uid for one-membership-per-user.
- Email send is fire-and-forget with logged failure — invite creation must never 500 because Gmail hiccuped.

## Cost rules

- Gmail consumer limit ~500 sends/day — fine; no batching needed. One Firestore transaction per accept (membership + invite status + memberTripIds atomically).

## Acceptance criteria

- [ ] Non-member `GET /trips/{id}` → 403; non-admin `POST /invites` → 403; tests cover both.
- [ ] Full flow in tests: user A creates trip → invites b@example.com → fake sender captured correct recipient + link → user B accepts → B appears in members, B's `GET /trips` includes the trip.
- [ ] Admin can add a traveler without inviting them; if that traveler is later invited and accepts, the existing participant becomes claimed by the accepting uid and keeps its preferences.
- [ ] Accept is idempotent and transactional (no partial membership on simulated failure).
- [ ] `GET /invites/{token}` works unauthenticated and leaks nothing beyond trip name/destination/inviter.
- [ ] Real Gmail send verified once manually against your account (setup notes followed); send failure path returns 201 with inviteUrl and a logged warning.
