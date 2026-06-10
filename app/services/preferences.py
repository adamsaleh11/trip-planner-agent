"""Preference storage: one doc per participant per trip, one field per category.

Membership controls trip access. Participants are the planning roster, so an
admin can fill preferences for unclaimed traveler profiles before invites exist.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.preferences import (
    CATEGORY_MODELS,
    CompletionEntry,
    GroupPreferencesEntry,
    MemberPreferences,
)
from app.services import trips as trips_service


def _prefs_collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/preferences"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_category(category: str) -> type:
    model = CATEGORY_MODELS.get(category)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown preference category")
    return model


def save_category(
    repo: Repository, trip_id: str, user: CurrentUser, category: str, payload: dict
) -> MemberPreferences:
    participant = trips_service.find_participant_for_uid(repo, trip_id, user.uid)
    if participant is None:
        trips_service.require_member(repo, trip_id, user.uid)
        raise HTTPException(status_code=404, detail="No participant claimed by user")
    return save_participant_category(
        repo, trip_id, participant.id, user, category, payload
    )


def save_participant_category(
    repo: Repository,
    trip_id: str,
    participant_id: str,
    user: CurrentUser,
    category: str,
    payload: dict,
) -> MemberPreferences:
    model = validate_category(category)
    if not trips_service.can_write_participant_preferences(
        repo, trip_id, participant_id, user.uid
    ):
        raise HTTPException(status_code=403, detail="Cannot edit this participant")
    try:
        validated = model(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False))
    existing = repo.get(_prefs_collection(trip_id), participant_id) or {}
    updated_at = {**existing.get("_updatedAt", {}), category: _now()}
    repo.update(
        _prefs_collection(trip_id),
        participant_id,
        {category: validated.model_dump(), "_updatedAt": updated_at},
    )
    result_collection = f"{trips_service.TRIPS_COLLECTION}/{trip_id}/categoryResults"
    result = repo.get(result_collection, category)
    if result is not None and result.get("status") == "complete":
        repo.update(result_collection, category, {"stale": True})
    return get_participant_preferences(repo, trip_id, participant_id, user.uid)


def get_my_preferences(
    repo: Repository, trip_id: str, user: CurrentUser
) -> MemberPreferences:
    trips_service.require_member(repo, trip_id, user.uid)
    participant = trips_service.find_participant_for_uid(repo, trip_id, user.uid)
    if participant is None:
        return MemberPreferences()
    data = repo.get(_prefs_collection(trip_id), participant.id) or {}
    return MemberPreferences(**data)


def get_participant_preferences(
    repo: Repository, trip_id: str, participant_id: str, uid: str
) -> MemberPreferences:
    trips_service.require_member(repo, trip_id, uid)
    trips_service.get_participant(repo, trip_id, participant_id)
    data = repo.get(_prefs_collection(trip_id), participant_id) or {}
    return MemberPreferences(**data)


def get_group_preferences(
    repo: Repository, trip_id: str, uid: str
) -> list[GroupPreferencesEntry]:
    trips_service.require_member(repo, trip_id, uid)
    participants = trips_service.list_participants_raw(repo, trip_id)
    entries = []
    for participant_id, participant in participants:
        data = repo.get(_prefs_collection(trip_id), participant_id) or {}
        entries.append(
            GroupPreferencesEntry(
                participantId=participant_id,
                displayName=participant.get("displayName"),
                claimedByUid=participant.get("claimedByUid"),
                preferences=MemberPreferences(**data),
            )
        )
    return entries


def get_completion_status(
    repo: Repository, trip_id: str, uid: str
) -> list[CompletionEntry]:
    entries = get_group_preferences(repo, trip_id, uid)
    return [
        CompletionEntry(
            participantId=entry.participantId,
            displayName=entry.displayName,
            claimedByUid=entry.claimedByUid,
            filled={
                category: getattr(entry.preferences, category) is not None
                for category in CATEGORY_MODELS
            },
        )
        for entry in entries
    ]
