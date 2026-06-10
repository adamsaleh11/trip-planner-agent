from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.trip import Member, Trip, TripCreate, TripUpdate
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
