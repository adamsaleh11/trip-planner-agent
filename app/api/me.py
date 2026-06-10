from fastapi import APIRouter, Depends, Response

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.user import UserProfile
from app.services import collective_memory
from app.services.users import get_or_create_profile

router = APIRouter()


@router.get("/me", response_model=UserProfile)
def get_me(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> UserProfile:
    """Return the caller's profile, provisioning it on first call."""
    return get_or_create_profile(repo, user)


@router.get("/me/shares")
def list_my_shares(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> list[dict]:
    return collective_memory.list_shares(repo, user.uid)


@router.delete("/me/shares/{opaque_id}", status_code=204)
def delete_my_share(
    opaque_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> Response:
    collective_memory.delete_share(repo, user.uid, opaque_id)
    return Response(status_code=204)
