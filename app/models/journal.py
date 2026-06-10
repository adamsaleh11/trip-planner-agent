from typing import Literal, Optional

from pydantic import BaseModel, Field

JournalCategory = Literal[
    "food_drink",
    "outdoors_scenic",
    "nightlife",
    "culture_local",
    "logistics",
]


class JournalContribution(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=1000)
    shareAnonymously: bool = False
    sharedOpaqueId: Optional[str] = None
    updatedAt: str


class JournalContributionUpdate(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=1000)
    shareAnonymously: bool = False


class JournalEntry(BaseModel):
    id: str
    placeId: str
    name: str
    category: JournalCategory
    address: str = "Not available"
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: Literal["participant_preference", "ai_suggestion", "manual_plan", "whim"] = (
        "ai_suggestion"
    )
    manualPlanId: Optional[str] = None
    createdAt: str
    updatedAt: str


class JournalEntryView(BaseModel):
    id: str
    placeId: str
    name: str
    category: JournalCategory
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: Literal["participant_preference", "ai_suggestion", "manual_plan", "whim"]
    manualPlanId: Optional[str] = None
    myEntry: Optional[JournalContribution] = None
