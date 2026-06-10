from typing import Literal

from pydantic import BaseModel, Field, field_validator


Category = Literal[
    "food_drink",
    "outdoors_scenic",
    "nightlife",
    "culture_local",
    "logistics",
]


class CategoryCandidate(BaseModel):
    name: str = Field(min_length=1)
    place_id: str = Field(min_length=1)
    address: str
    lat: float | None = None
    lng: float | None = None
    why_it_fits: str = Field(min_length=1)
    time_of_day_fit: Literal["morning", "afternoon", "evening", "flexible"]
    estimated_price_level: str = "Not available"
    suggested: bool


class CategoryCandidateList(BaseModel):
    category: Category
    candidates: list[CategoryCandidate]


class Transport(BaseModel):
    mode: Literal["walk", "transit", "rideshare", "drive", "bike", "Not available"]
    durationText: str = "Not available"

    @field_validator("durationText")
    @classmethod
    def duration_text_is_present(cls, value: str) -> str:
        return value or "Not available"


class ItineraryStop(BaseModel):
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    placeId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str
    lat: float | None = None
    lng: float | None = None
    category: Category
    transport: Transport
    whyItFits: str = Field(min_length=1)
    suggested: bool


class ItineraryBlock(BaseModel):
    period: Literal["morning", "afternoon", "evening"]
    stops: list[ItineraryStop]


class ItineraryDay(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    blocks: list[ItineraryBlock]


class Itinerary(BaseModel):
    days: list[ItineraryDay]

    @field_validator("days")
    @classmethod
    def has_at_least_one_day(cls, value: list[ItineraryDay]) -> list[ItineraryDay]:
        if not value:
            raise ValueError("itinerary must contain at least one day")
        return value
