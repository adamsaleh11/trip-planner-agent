from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.services import generation as generation_service

router = APIRouter(prefix="/trips/{trip_id}")


@router.post("/categories/{category}/generate", status_code=202)
def generate_category(
    trip_id: str,
    category: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    runner: generation_service.GenerationRunner = Depends(
        generation_service.get_generation_runner
    ),
) -> dict[str, str]:
    return generation_service.request_category_generation(
        repo, background_tasks, user, trip_id, category, runner
    )


@router.post("/generate", status_code=202)
def generate_trip(
    trip_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    runner: generation_service.GenerationRunner = Depends(
        generation_service.get_generation_runner
    ),
) -> dict[str, str]:
    return generation_service.request_trip_generation(
        repo, background_tasks, user, trip_id, runner
    )
