"""Trip lifecycle and tenant-isolation rules.

Creating a trip makes the caller its admin (membership doc keyed by uid —
one membership per user for free) and registers the trip on the caller's
profile so "my trips" is a single profile read plus per-trip gets.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.trip import (
    Member,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
    Trip,
    TripCreate,
    TripUpdate,
)
from app.services.users import USERS_COLLECTION, get_or_create_profile

logger = logging.getLogger(__name__)

TRIPS_COLLECTION = "trips"


def _memberships(trip_id: str) -> str:
    return f"{TRIPS_COLLECTION}/{trip_id}/memberships"


def _participants(trip_id: str) -> str:
    return f"{TRIPS_COLLECTION}/{trip_id}/participants"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_trip(repo: Repository, user: CurrentUser, payload: TripCreate) -> Trip:
    profile = get_or_create_profile(repo, user)
    trip = Trip(
        id=uuid.uuid4().hex,
        adminUid=user.uid,
        createdAt=_now(),
        **payload.model_dump(),
    )
    repo.set(TRIPS_COLLECTION, trip.id, trip.model_dump())
    repo.set(
        _memberships(trip.id),
        user.uid,
        Member(
            uid=user.uid,
            displayName=user.display_name,
            role="admin",
            joinedAt=trip.createdAt,
        ).model_dump(),
    )
    repo.update(
        USERS_COLLECTION,
        user.uid,
        {"memberTripIds": [*profile.memberTripIds, trip.id]},
    )
    _create_claimed_participant(repo, trip.id, user, trip.createdAt)
    logger.info("trip created", extra={"trip_id": trip.id})
    return trip


def get_membership(repo: Repository, trip_id: str, uid: str) -> dict | None:
    return repo.get(_memberships(trip_id), uid)


def require_member(repo: Repository, trip_id: str, uid: str) -> Trip:
    trip = repo.get(TRIPS_COLLECTION, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if get_membership(repo, trip_id, uid) is None:
        raise HTTPException(status_code=403, detail="Not a member of this trip")
    return Trip(**trip)


def require_admin(repo: Repository, trip_id: str, uid: str) -> Trip:
    trip = require_member(repo, trip_id, uid)
    membership = get_membership(repo, trip_id, uid)
    if membership is None or membership.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return trip


def list_my_trips(repo: Repository, user: CurrentUser) -> list[Trip]:
    profile = get_or_create_profile(repo, user)
    trips = []
    for trip_id in profile.memberTripIds:
        data = repo.get(TRIPS_COLLECTION, trip_id)
        if data is not None:
            trips.append(Trip(**data))
    return trips


def update_trip(
    repo: Repository, trip_id: str, uid: str, payload: TripUpdate
) -> Trip:
    trip = require_admin(repo, trip_id, uid)
    changes = payload.model_dump(exclude_none=True)
    if changes:
        repo.update(TRIPS_COLLECTION, trip_id, changes)
    return Trip(**{**trip.model_dump(), **changes})


def list_members(repo: Repository, trip_id: str, uid: str) -> list[Member]:
    require_member(repo, trip_id, uid)
    return [Member(**data) for _, data in repo.list(_memberships(trip_id))]


def list_members_raw(repo: Repository, trip_id: str) -> list[tuple[str, dict]]:
    """(uid, membership) pairs without an access check — caller enforces it."""
    return repo.list(_memberships(trip_id))


def list_participants(repo: Repository, trip_id: str, uid: str) -> list[Participant]:
    require_member(repo, trip_id, uid)
    return [Participant(**data) for _, data in repo.list(_participants(trip_id))]


def list_participants_raw(repo: Repository, trip_id: str) -> list[tuple[str, dict]]:
    """(participant_id, participant) pairs without an access check."""
    return repo.list(_participants(trip_id))


def get_participant(repo: Repository, trip_id: str, participant_id: str) -> Participant:
    data = repo.get(_participants(trip_id), participant_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    return Participant(**data)


def create_participant(
    repo: Repository, trip_id: str, uid: str, payload: ParticipantCreate
) -> Participant:
    require_admin(repo, trip_id, uid)
    participant = Participant(
        id=uuid.uuid4().hex,
        displayName=payload.displayName,
        email=str(payload.email).lower() if payload.email else None,
        notes=payload.notes,
        createdByUid=uid,
        createdAt=_now(),
    )
    repo.set(_participants(trip_id), participant.id, participant.model_dump())
    return participant


def update_participant(
    repo: Repository,
    trip_id: str,
    participant_id: str,
    uid: str,
    payload: ParticipantUpdate,
) -> Participant:
    require_admin(repo, trip_id, uid)
    participant = get_participant(repo, trip_id, participant_id)
    changes = payload.model_dump(exclude_none=True)
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    if changes:
        repo.update(_participants(trip_id), participant_id, changes)
    return Participant(**{**participant.model_dump(), **changes})


def remove_participant(
    repo: Repository, trip_id: str, participant_id: str, uid: str
) -> None:
    """Remove a traveler from the trip.

    Claimed participants also lose their membership and the trip is removed
    from their profile, so access is revoked along with the roster row. The
    trip admin cannot be removed.
    """
    trip = require_admin(repo, trip_id, uid)
    participant = get_participant(repo, trip_id, participant_id)
    if participant.claimedByUid == trip.adminUid:
        raise HTTPException(status_code=409, detail="The trip admin cannot be removed")
    if participant.claimedByUid:
        repo.delete(_memberships(trip_id), participant.claimedByUid)
        profile = repo.get(USERS_COLLECTION, participant.claimedByUid)
        if profile and trip_id in profile.get("memberTripIds", []):
            repo.update(
                USERS_COLLECTION,
                participant.claimedByUid,
                {
                    "memberTripIds": [
                        t for t in profile["memberTripIds"] if t != trip_id
                    ]
                },
            )
    repo.delete(f"{TRIPS_COLLECTION}/{trip_id}/preferences", participant_id)
    repo.delete(_participants(trip_id), participant_id)
    logger.info("participant removed", extra={"trip_id": trip_id})


def find_participant_for_uid(
    repo: Repository, trip_id: str, uid: str
) -> Participant | None:
    for _, data in list_participants_raw(repo, trip_id):
        if data.get("claimedByUid") == uid:
            return Participant(**data)
    return None


def find_unclaimed_participant_by_email(
    repo: Repository, trip_id: str, email: str
) -> Participant | None:
    normalized = email.lower()
    for _, data in list_participants_raw(repo, trip_id):
        if data.get("claimedByUid") is None and data.get("email") == normalized:
            return Participant(**data)
    return None


def claim_participant_for_user(
    repo: Repository, trip_id: str, participant_id: str, user: CurrentUser
) -> Participant:
    participant = get_participant(repo, trip_id, participant_id)
    if participant.claimedByUid and participant.claimedByUid != user.uid:
        raise HTTPException(status_code=409, detail="Participant already claimed")
    changes = {
        "displayName": user.display_name or user.email or participant.displayName,
        "email": user.email.lower() if user.email else participant.email,
        "claimedByUid": user.uid,
        "isClaimed": True,
    }
    repo.update(_participants(trip_id), participant_id, changes)
    return Participant(**{**participant.model_dump(), **changes})


def can_write_participant_preferences(
    repo: Repository, trip_id: str, participant_id: str, uid: str
) -> bool:
    require_member(repo, trip_id, uid)
    membership = get_membership(repo, trip_id, uid)
    if membership and membership.get("role") == "admin":
        get_participant(repo, trip_id, participant_id)
        return True
    participant = get_participant(repo, trip_id, participant_id)
    return participant.claimedByUid == uid


def add_member(
    repo: Repository,
    trip_id: str,
    user: CurrentUser,
    participant_id: str | None = None,
    invite_email: str | None = None,
) -> Participant:
    """Create a membership (idempotent) and register the trip on the profile."""
    if get_membership(repo, trip_id, user.uid) is None:
        profile = get_or_create_profile(repo, user)
        repo.set(
            _memberships(trip_id),
            user.uid,
            Member(
                uid=user.uid,
                displayName=user.display_name,
                role="member",
                joinedAt=_now(),
            ).model_dump(),
        )
        if trip_id not in profile.memberTripIds:
            repo.update(
                USERS_COLLECTION,
                user.uid,
                {"memberTripIds": [*profile.memberTripIds, trip_id]},
            )
    existing = find_participant_for_uid(repo, trip_id, user.uid)
    if existing is not None:
        return existing
    if participant_id:
        return claim_participant_for_user(repo, trip_id, participant_id, user)
    if invite_email:
        participant = find_unclaimed_participant_by_email(repo, trip_id, invite_email)
        if participant is not None:
            return claim_participant_for_user(repo, trip_id, participant.id, user)
    return _create_claimed_participant(repo, trip_id, user, _now())


def _create_claimed_participant(
    repo: Repository, trip_id: str, user: CurrentUser, created_at: str
) -> Participant:
    participant = Participant(
        id=uuid.uuid4().hex,
        displayName=user.display_name or user.email or "Traveler",
        email=user.email.lower() if user.email else None,
        createdByUid=user.uid,
        claimedByUid=user.uid,
        isClaimed=True,
        createdAt=created_at,
    )
    repo.set(_participants(trip_id), participant.id, participant.model_dump())
    return participant
