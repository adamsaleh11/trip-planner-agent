from typing import Optional

from pydantic import BaseModel, EmailStr


class InviteRequest(BaseModel):
    email: EmailStr
    participantId: Optional[str] = None


class InviteCreated(BaseModel):
    inviteUrl: str
    emailSent: bool
    participantId: Optional[str] = None


class InvitePreview(BaseModel):
    tripName: str
    destinationText: str
    inviterName: str
    status: str


class InviteAccepted(BaseModel):
    tripId: str
    participantId: Optional[str] = None
