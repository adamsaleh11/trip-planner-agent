"""Invite lifecycle.

The invite token doubles as the document ID, so uniqueness comes from the
store. Accept is idempotent for the accepting user and ordered so a crash
between writes leaves a retryable state (membership first, status last —
a pending invite with an existing membership simply re-converges on retry).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.invite import InviteCreated, InvitePreview
from app.services import trips as trips_service
from app.services.email import InviteEmailSender, render_invite_email
from app.services.users import USERS_COLLECTION

logger = logging.getLogger(__name__)

INVITES_COLLECTION = "invites"


def create_invite(
    repo: Repository,
    sender: InviteEmailSender,
    frontend_url: str,
    trip_id: str,
    admin: CurrentUser,
    email: str,
    participant_id: str | None = None,
) -> InviteCreated:
    trip = trips_service.require_admin(repo, trip_id, admin.uid)
    linked_participant = None
    if participant_id:
        linked_participant = trips_service.get_participant(repo, trip_id, participant_id)
    else:
        linked_participant = trips_service.find_unclaimed_participant_by_email(
            repo, trip_id, email
        )
    token = secrets.token_urlsafe(24)
    invite_url = f"{frontend_url.rstrip('/')}/invite/{token}"
    invite_doc = {
        "email": email.lower(),
        "tripId": trip_id,
        "invitedBy": admin.uid,
        "status": "pending",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if linked_participant is not None:
        invite_doc["participantId"] = linked_participant.id
    repo.set(
        INVITES_COLLECTION,
        token,
        invite_doc,
    )
    html = render_invite_email(trip.name, admin.display_name or "", invite_url)
    email_sent = sender.send_invite(
        to=email, html=html, subject=f"Join \"{trip.name}\" on Trip Journal"
    )
    logger.info(
        "invite created",
        extra={"trip_id": trip_id, "email_sent": email_sent},
    )
    return InviteCreated(
        inviteUrl=invite_url,
        emailSent=email_sent,
        participantId=linked_participant.id if linked_participant else None,
    )


def _get_invite_or_404(repo: Repository, token: str) -> dict:
    invite = repo.get(INVITES_COLLECTION, token)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return invite


def preview_invite(repo: Repository, token: str) -> InvitePreview:
    """Public lookup: only trip name, destination text, inviter, status."""
    invite = _get_invite_or_404(repo, token)
    trip = repo.get(trips_service.TRIPS_COLLECTION, invite["tripId"]) or {}
    inviter = repo.get(USERS_COLLECTION, invite["invitedBy"]) or {}
    return InvitePreview(
        tripName=trip.get("name", ""),
        destinationText=(trip.get("destination") or {}).get("text", ""),
        inviterName=inviter.get("displayName") or "",
        status=invite["status"],
    )


def accept_invite(repo: Repository, token: str, user: CurrentUser) -> dict:
    invite = _get_invite_or_404(repo, token)
    if invite["status"] == "accepted":
        if invite.get("acceptedBy") == user.uid:
            return {"tripId": invite["tripId"]}  # idempotent re-accept
        raise HTTPException(status_code=410, detail="Invite already used")

    participant = trips_service.add_member(
        repo,
        invite["tripId"],
        user,
        participant_id=invite.get("participantId"),
        invite_email=invite.get("email"),
    )
    repo.update(
        INVITES_COLLECTION,
        token,
        {"status": "accepted", "acceptedBy": user.uid},
    )
    logger.info("invite accepted", extra={"trip_id": invite["tripId"]})
    return {"tripId": invite["tripId"], "participantId": participant.id}
