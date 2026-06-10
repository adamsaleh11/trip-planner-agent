"""Preference storage: one doc per member per trip, one field per category.

The writing uid always comes from the verified token — a member can never
write another member's preferences regardless of payload contents.
"""

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


def validate_category(category: str) -> type:
    model = CATEGORY_MODELS.get(category)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown preference category")
    return model


def save_category(
    repo: Repository, trip_id: str, user: CurrentUser, category: str, payload: dict
) -> MemberPreferences:
    model = validate_category(category)
    trips_service.require_member(repo, trip_id, user.uid)
    try:
        validated = model(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False))
    repo.update(
        _prefs_collection(trip_id), user.uid, {category: validated.model_dump()}
    )
    return get_my_preferences(repo, trip_id, user)


def get_my_preferences(
    repo: Repository, trip_id: str, user: CurrentUser
) -> MemberPreferences:
    trips_service.require_member(repo, trip_id, user.uid)
    data = repo.get(_prefs_collection(trip_id), user.uid) or {}
    return MemberPreferences(**data)


def get_group_preferences(
    repo: Repository, trip_id: str, uid: str
) -> list[GroupPreferencesEntry]:
    trips_service.require_member(repo, trip_id, uid)
    members = trips_service.list_members_raw(repo, trip_id)
    entries = []
    for member_uid, member in members:
        data = repo.get(_prefs_collection(trip_id), member_uid) or {}
        entries.append(
            GroupPreferencesEntry(
                uid=member_uid,
                displayName=member.get("displayName"),
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
            uid=entry.uid,
            displayName=entry.displayName,
            filled={
                category: getattr(entry.preferences, category) is not None
                for category in CATEGORY_MODELS
            },
        )
        for entry in entries
    ]
