"""Trip lifecycle and tenant-isolation rules.

Creating a trip makes the caller its admin (membership doc keyed by uid —
one membership per user for free) and registers the trip on the caller's
profile so "my trips" is a single profile read plus per-trip gets.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.trip import Member, Trip, TripCreate, TripUpdate
from app.services.users import USERS_COLLECTION, get_or_create_profile

logger = logging.getLogger(__name__)

TRIPS_COLLECTION = "trips"


def _memberships(trip_id: str) -> str:
    return f"{TRIPS_COLLECTION}/{trip_id}/memberships"


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


def add_member(repo: Repository, trip_id: str, user: CurrentUser) -> None:
    """Create a membership (idempotent) and register the trip on the profile."""
    if get_membership(repo, trip_id, user.uid) is not None:
        return
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
