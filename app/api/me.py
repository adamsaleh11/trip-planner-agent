from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.data.repository import Repository, get_repository
from app.models.user import UserProfile
from app.services.users import get_or_create_profile

router = APIRouter()


@router.get("/me", response_model=UserProfile)
def get_me(
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
) -> UserProfile:
    """Return the caller's profile, provisioning it on first call."""
    return get_or_create_profile(repo, user)
