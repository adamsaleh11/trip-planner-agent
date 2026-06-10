from fastapi import APIRouter, Depends, Response

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.manual_plan import ManualPlan, ManualPlanCreate, ManualPlanUpdate
from app.services import manual_plans as manual_plans_service

router = APIRouter(prefix="/trips/{trip_id}/manual-plans")


@router.get("", response_model=list[ManualPlan])
def list_manual_plans(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[ManualPlan]:
    return manual_plans_service.list_manual_plans(repo, trip_id, user.uid)


@router.post("", response_model=ManualPlan, status_code=201)
def create_manual_plan(
    trip_id: str,
    payload: ManualPlanCreate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> ManualPlan:
    return manual_plans_service.create_manual_plan(repo, trip_id, user.uid, payload)


@router.patch("/{plan_id}", response_model=ManualPlan)
def update_manual_plan(
    trip_id: str,
    plan_id: str,
    payload: ManualPlanUpdate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> ManualPlan:
    return manual_plans_service.update_manual_plan(
        repo, trip_id, plan_id, user.uid, payload
    )


@router.delete("/{plan_id}", status_code=204)
def delete_manual_plan(
    trip_id: str,
    plan_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Response:
    manual_plans_service.delete_manual_plan(repo, trip_id, plan_id, user.uid)
    return Response(status_code=204)
