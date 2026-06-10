"""Invite email delivery.

The sender is pluggable behind :class:`InviteEmailSender` — Gmail (the
owner's account, OAuth refresh token) for the MVP; a transactional provider
is a drop-in replacement at scale. Delivery failures are reported, never
raised: invite creation must succeed even when email does not.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Protocol

logger = logging.getLogger(__name__)


class InviteEmailSender(Protocol):
    def send_invite(
        self, to: str, html: str, subject: str
    ) -> bool:  # pragma: no cover - protocol
        """Send the invite email. Returns True on success, False on failure."""
        ...


def render_invite_email(trip_name: str, inviter_name: str, invite_url: str) -> str:
    inviter = inviter_name or "A friend"
    return f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto">
  <h2>{inviter} invited you to join "{trip_name}"</h2>
  <p>Plan the trip together — add what you want to eat, see, and do,
     and let the group's AI build the itinerary.</p>
  <p style="margin:24px 0">
    <a href="{invite_url}"
       style="background:#e0673c;color:#fff;padding:12px 20px;
              border-radius:8px;text-decoration:none">Join the trip</a>
  </p>
  <p style="color:#888;font-size:12px">Or open this link: {invite_url}</p>
</div>
"""


class GmailInviteSender:
    """Sends from the owner's Gmail via the Gmail API.

    Credentials are minted from a long-lived OAuth refresh token. Limits that
    are acceptable for the MVP and documented in the architecture handoff:
    ~500 sends/day, and testing-mode refresh tokens expire every 7 days.
    """

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token

    def _service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=self._refresh_token,
            client_id=self._client_id,
            client_secret=self._client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def send_invite(self, to: str, html: str, subject: str) -> bool:
        try:
            message = MIMEText(html, "html")
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            self._service().users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            return True
        except Exception:  # noqa: BLE001 — delivery failure is non-fatal by design
            logger.warning("invite email send failed", exc_info=True)
            return False


class DisabledInviteSender:
    """Used when Gmail credentials are not configured; link-only invites."""

    def send_invite(self, to: str, html: str, subject: str) -> bool:
        logger.warning("invite email skipped: Gmail sender not configured")
        return False


def get_invite_sender() -> InviteEmailSender:
    from app.core.config import get_settings

    settings = get_settings()
    if (
        settings.gmail_client_id
        and settings.gmail_client_secret
        and settings.gmail_refresh_token
    ):
        return GmailInviteSender(
            settings.gmail_client_id,
            settings.gmail_client_secret,
            settings.gmail_refresh_token,
        )
    return DisabledInviteSender()
