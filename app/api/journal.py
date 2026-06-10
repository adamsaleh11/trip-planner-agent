from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.journal import JournalContributionUpdate, JournalEntryView
from app.models.trip import Trip
from app.services import collective_memory
from app.services import journal as journal_service

router = APIRouter(prefix="/trips/{trip_id}")


@router.post("/complete", response_model=Trip)
def complete_trip(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Trip:
    return journal_service.complete_trip(repo, trip_id, user.uid)


@router.get("/journal", response_model=list[JournalEntryView])
def list_journal(
    trip_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[JournalEntryView]:
    return journal_service.list_journal(repo, trip_id, user.uid)


@router.post(
    "/journal/from-whim/{whim_id}",
    response_model=JournalEntryView,
    status_code=201,
)
def create_journal_entry_from_whim(
    trip_id: str,
    whim_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> JournalEntryView:
    entry = journal_service.create_entry_from_whim(repo, trip_id, whim_id, user.uid)
    return JournalEntryView(**entry.model_dump(), myEntry=None)


@router.put("/journal/{place_id:path}", response_model=JournalEntryView)
def update_journal_entry(
    trip_id: str,
    place_id: str,
    payload: JournalContributionUpdate,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    pipeline: collective_memory.SharePipeline = Depends(
        collective_memory.get_share_pipeline
    ),
) -> JournalEntryView:
    return journal_service.update_journal_entry(
        repo, trip_id, place_id, user.uid, payload, pipeline
    )
