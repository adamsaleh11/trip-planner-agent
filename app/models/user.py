from typing import List, Optional

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    uid: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    createdAt: str
    memberTripIds: List[str] = Field(default_factory=list)
