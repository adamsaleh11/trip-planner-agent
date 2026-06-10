from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.data.repository import Repository
from app.models.manual_plan import ManualPlan, ManualPlanCreate, ManualPlanUpdate
from app.models.trip import Trip
from app.services import trips as trips_service


def _collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/manualPlans"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_manual_plans(repo: Repository, trip_id: str, uid: str) -> list[ManualPlan]:
    trips_service.require_member(repo, trip_id, uid)
    return [
        ManualPlan(**data)
        for _, data in repo.list(_collection(trip_id))
        if not data.get("_deleted")
    ]


def create_manual_plan(
    repo: Repository, trip_id: str, uid: str, payload: ManualPlanCreate
) -> ManualPlan:
    trip = trips_service.require_admin(repo, trip_id, uid)
    data = payload.model_dump()
    _validate_date_in_trip(trip, data.get("date"))
    timestamp = _now()
    plan = ManualPlan(
        id=uuid.uuid4().hex,
        createdByUid=uid,
        createdAt=timestamp,
        updatedAt=timestamp,
        **data,
    )
    repo.set(_collection(trip_id), plan.id, plan.model_dump())
    return plan


def update_manual_plan(
    repo: Repository,
    trip_id: str,
    plan_id: str,
    uid: str,
    payload: ManualPlanUpdate,
) -> ManualPlan:
    trip = trips_service.require_admin(repo, trip_id, uid)
    existing = repo.get(_collection(trip_id), plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Manual plan not found")
    changes = payload.model_dump(exclude_unset=True)
    if "date" in changes:
        _validate_date_in_trip(trip, changes.get("date"))
    if changes:
        changes["updatedAt"] = _now()
        repo.update(_collection(trip_id), plan_id, changes)
    return ManualPlan(**{**existing, **changes})


def delete_manual_plan(repo: Repository, trip_id: str, plan_id: str, uid: str) -> None:
    trips_service.require_admin(repo, trip_id, uid)
    existing = repo.get(_collection(trip_id), plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Manual plan not found")
    repo.delete(_collection(trip_id), plan_id)


def _validate_date_in_trip(trip: Trip, value: str | None) -> None:
    if value is None:
        return
    try:
        plan_date = date.fromisoformat(value)
        start = date.fromisoformat(trip.startDate)
        end = date.fromisoformat(trip.endDate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Manual plan date must be YYYY-MM-DD") from exc
    if plan_date < start or plan_date > end:
        raise HTTPException(status_code=422, detail="Manual plan date must be inside the trip date range")
