from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.services import generation as generation_service

router = APIRouter(prefix="/trips/{trip_id}")


class TripGenerationRequest(BaseModel):
    provider: Optional[Literal["groq", "gemini"]] = None


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


@router.get("/generation-quota")
def generation_quota(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> dict:
    return generation_service.get_generation_quota(repo, user, trip_id)


@router.post("/generate", status_code=202)
def generate_trip(
    trip_id: str,
    background_tasks: BackgroundTasks,
    payload: TripGenerationRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    runner: generation_service.GenerationRunner = Depends(
        generation_service.get_generation_runner
    ),
) -> dict[str, str]:
    return generation_service.request_trip_generation(
        repo,
        background_tasks,
        user,
        trip_id,
        runner,
        provider=payload.provider if payload else None,
    )
