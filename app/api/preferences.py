from fastapi import APIRouter, Body, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.preferences import (
    CompletionEntry,
    GroupPreferencesEntry,
    MemberPreferences,
)
from app.services import preferences as prefs_service

router = APIRouter(prefix="/trips/{trip_id}/preferences")


@router.get("/me", response_model=MemberPreferences)
def get_my_preferences(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> MemberPreferences:
    return prefs_service.get_my_preferences(repo, trip_id, user)


@router.get("/status", response_model=list[CompletionEntry])
def completion_status(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[CompletionEntry]:
    return prefs_service.get_completion_status(repo, trip_id, user.uid)


@router.get("", response_model=list[GroupPreferencesEntry])
def group_preferences(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[GroupPreferencesEntry]:
    """All participant preferences — the group plans together by design."""
    return prefs_service.get_group_preferences(repo, trip_id, user.uid)


@router.put("/{category}", response_model=MemberPreferences)
def save_category(
    trip_id: str,
    category: str,
    payload: dict = Body(...),
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> MemberPreferences:
    """Save the caller's claimed participant preferences for one category."""
    return prefs_service.save_category(repo, trip_id, user, category, payload)


@router.get("/participants/{participant_id}", response_model=MemberPreferences)
def get_participant_preferences(
    trip_id: str,
    participant_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> MemberPreferences:
    return prefs_service.get_participant_preferences(
        repo, trip_id, participant_id, user.uid
    )


@router.put("/participants/{participant_id}/{category}", response_model=MemberPreferences)
def save_participant_category(
    trip_id: str,
    participant_id: str,
    category: str,
    payload: dict = Body(...),
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> MemberPreferences:
    return prefs_service.save_participant_category(
        repo, trip_id, participant_id, user, category, payload
    )
