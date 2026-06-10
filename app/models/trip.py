from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class Destination(BaseModel):
    text: str
    lat: float
    lng: float
    placeId: Optional[str] = None


class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    destination: Destination
    startDate: str
    endDate: str
    lodgingArea: Optional[str] = None


class TripUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    lodgingArea: Optional[str] = None


class Trip(BaseModel):
    id: str
    name: str
    destination: Destination
    startDate: str
    endDate: str
    lodgingArea: Optional[str] = None
    status: Literal["planning", "generated", "completed"] = "planning"
    adminUid: str
    createdAt: str


class Member(BaseModel):
    uid: str
    displayName: Optional[str] = None
    role: Literal["admin", "member"]
    joinedAt: str


class MemberList(BaseModel):
    members: List[Member]


class ParticipantCreate(BaseModel):
    displayName: str = Field(min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ParticipantUpdate(BaseModel):
    displayName: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class Participant(BaseModel):
    id: str
    displayName: str
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    createdByUid: str
    claimedByUid: Optional[str] = None
    isClaimed: bool = False
    createdAt: str
