from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.models.places import DestinationSearchResult
from app.services.places import DestinationSearcher, get_destination_searcher

router = APIRouter(prefix="/places")


@router.get("/search", response_model=list[DestinationSearchResult])
def search_destinations(
    query: str = Query(min_length=2, max_length=120),
    user: CurrentUser = Depends(get_current_user),
    searcher: DestinationSearcher = Depends(get_destination_searcher),
) -> list[DestinationSearchResult]:
    return searcher.search(query)
