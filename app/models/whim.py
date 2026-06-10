from typing import Optional

from pydantic import BaseModel, Field

from travel_agent.schemas import Category


class WhimLocation(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    city: Optional[str] = Field(default=None, min_length=1, max_length=160)


class WhimRequest(BaseModel):
    whimText: str = ""
    location: Optional[WhimLocation] = None
    tripId: Optional[str] = None
    excludePlaceIds: list[str] = Field(default_factory=list)


class WhimSuggestion(BaseModel):
    placeId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    category: Category
    whyThis: str = Field(min_length=1)
    openNow: str = "Not available"
    mapsUri: str
    travelersTip: Optional[str] = None


class WhimResponse(BaseModel):
    suggestion: WhimSuggestion
    whimId: str
