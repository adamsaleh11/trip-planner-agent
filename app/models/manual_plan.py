from typing import Literal, Optional

from pydantic import BaseModel, Field


ManualPlanCategory = Literal[
    "food_drink",
    "outdoors_scenic",
    "nightlife",
    "culture_local",
    "logistics",
]

TimeOfDay = Literal["morning", "afternoon", "evening"]


class ManualPlanCreate(BaseModel):
    category: ManualPlanCategory
    activity: str = Field(min_length=1, max_length=160)
    timeOfDay: TimeOfDay
    date: Optional[str] = None
    placeId: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ManualPlanUpdate(BaseModel):
    category: Optional[ManualPlanCategory] = None
    activity: Optional[str] = Field(default=None, min_length=1, max_length=160)
    timeOfDay: Optional[TimeOfDay] = None
    date: Optional[str] = None
    placeId: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ManualPlan(BaseModel):
    id: str
    category: ManualPlanCategory
    activity: str
    timeOfDay: TimeOfDay
    date: Optional[str] = None
    placeId: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    createdByUid: str
    createdAt: str
    updatedAt: str
