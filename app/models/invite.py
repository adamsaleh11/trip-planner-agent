from pydantic import BaseModel, EmailStr


class InviteRequest(BaseModel):
    email: EmailStr


class InviteCreated(BaseModel):
    inviteUrl: str
    emailSent: bool


class InvitePreview(BaseModel):
    tripName: str
    destinationText: str
    inviterName: str
    status: str


class InviteAccepted(BaseModel):
    tripId: str
