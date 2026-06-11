from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.trip import (
    Member,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
    Trip,
    TripCreate,
    TripUpdate,
)
from app.services import trips as trips_service

router = APIRouter(prefix="/trips")


@router.post("", response_model=Trip, status_code=201)
def create_trip(
    payload: TripCreate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Trip:
    return trips_service.create_trip(repo, user, payload)


@router.get("", response_model=list[Trip])
def list_my_trips(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[Trip]:
    return trips_service.list_my_trips(repo, user)


@router.get("/{trip_id}", response_model=Trip)
def get_trip(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Trip:
    return trips_service.require_member(repo, trip_id, user.uid)


@router.patch("/{trip_id}", response_model=Trip)
def update_trip(
    trip_id: str,
    payload: TripUpdate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Trip:
    return trips_service.update_trip(repo, trip_id, user.uid, payload)


@router.get("/{trip_id}/members", response_model=list[Member])
def list_members(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[Member]:
    return trips_service.list_members(repo, trip_id, user.uid)


@router.get("/{trip_id}/participants", response_model=list[Participant])
def list_participants(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[Participant]:
    return trips_service.list_participants(repo, trip_id, user.uid)


@router.post("/{trip_id}/participants", response_model=Participant, status_code=201)
def create_participant(
    trip_id: str,
    payload: ParticipantCreate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Participant:
    return trips_service.create_participant(repo, trip_id, user.uid, payload)


@router.patch("/{trip_id}/participants/{participant_id}", response_model=Participant)
def update_participant(
    trip_id: str,
    participant_id: str,
    payload: ParticipantUpdate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Participant:
    return trips_service.update_participant(
        repo, trip_id, participant_id, user.uid, payload
    )


@router.delete("/{trip_id}/participants/{participant_id}", status_code=204)
def remove_participant(
    trip_id: str,
    participant_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> None:
    trips_service.remove_participant(repo, trip_id, participant_id, user.uid)
