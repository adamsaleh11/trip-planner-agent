from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.services import admin as admin_service

router = APIRouter(prefix="/admin")


@router.get("/generations/recent")
def recent_generations(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[dict]:
    return admin_service.recent_generations(repo)


@router.get("/whims/recent")
def recent_whims(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[dict]:
    return admin_service.recent_whims(repo)


@router.get("/eval-runs")
def recent_eval_runs(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[dict]:
    return admin_service.recent_eval_runs(repo)
