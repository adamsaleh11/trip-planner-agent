"""User profile provisioning.

On first sight of an authenticated caller, create their ``users/{uid}`` doc;
on every subsequent call return the stored profile with a single read and no
write (Firestore free-tier discipline).
"""

import logging
from datetime import datetime, timezone

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.user import UserProfile

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"


def get_or_create_profile(repo: Repository, user: CurrentUser) -> UserProfile:
    existing = repo.get(USERS_COLLECTION, user.uid)
    if existing is not None:
        return UserProfile(**existing)

    profile = UserProfile(
        uid=user.uid,
        email=user.email,
        displayName=user.display_name,
        createdAt=datetime.now(timezone.utc).isoformat(),
        memberTripIds=[],
    )
    repo.set(USERS_COLLECTION, user.uid, profile.model_dump())
    logger.info("provisioned user profile", extra={"provisioned_uid": user.uid})
    return profile
