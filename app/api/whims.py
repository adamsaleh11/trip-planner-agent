from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.whim import WhimRequest, WhimResponse
from app.services import collective_memory
from app.services import whims as whims_service

router = APIRouter(prefix="/whims")


@router.post("", response_model=WhimResponse)
def create_whim(
    payload: WhimRequest,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    runner: whims_service.WhimRunner = Depends(whims_service.get_whim_runner),
    memory_pipeline: collective_memory.SharePipeline = Depends(
        collective_memory.get_share_pipeline
    ),
) -> WhimResponse:
    return whims_service.create_whim(repo, user, payload, runner, memory_pipeline)
