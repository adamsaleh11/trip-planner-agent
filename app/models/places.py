from pydantic import BaseModel


class DestinationSearchResult(BaseModel):
    id: str
    text: str
    lat: float
    lng: float
    placeId: str
