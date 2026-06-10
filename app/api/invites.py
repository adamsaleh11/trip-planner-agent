from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.data.repository import Repository, get_repository
from app.models.invite import InviteAccepted, InviteCreated, InvitePreview, InviteRequest
from app.services import invites as invites_service
from app.services.email import InviteEmailSender, get_invite_sender

router = APIRouter()


@router.post("/trips/{trip_id}/invites", response_model=InviteCreated, status_code=201)
def create_invite(
    trip_id: str,
    payload: InviteRequest,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
    sender: InviteEmailSender = Depends(get_invite_sender),
) -> InviteCreated:
    return invites_service.create_invite(
        repo,
        sender,
        get_settings().frontend_url,
        trip_id,
        user,
        str(payload.email),
        payload.participantId,
    )


@router.get("/invites/{token}", response_model=InvitePreview)
def preview_invite(
    token: str,
    repo: Repository = Depends(get_repository),
) -> InvitePreview:
    """The only unauthenticated read in the API: invite landing-page preview."""
    return invites_service.preview_invite(repo, token)


@router.post("/invites/{token}/accept", response_model=InviteAccepted)
def accept_invite(
    token: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> InviteAccepted:
    return InviteAccepted(**invites_service.accept_invite(repo, token, user))
