"""Firebase ID-token authentication.

The auth dependency verifies an ``Authorization: Bearer <token>`` header and
exposes a :class:`CurrentUser` to handlers. Token verification is hidden behind
the :class:`TokenVerifier` interface so tests can substitute a fake.
"""

from __future__ import annotations

from typing import Optional, Protocol

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.context import set_uid


class CurrentUser(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None


class InvalidTokenError(Exception):
    """Raised by a verifier when a token is missing, invalid, or expired."""


class TokenVerifier(Protocol):
    def verify(self, token: str) -> CurrentUser:
        ...


class FirebaseTokenVerifier:
    """Verifies Firebase ID tokens with ``firebase-admin``.

    The Firebase app is initialized lazily on first use so importing this
    module never touches credentials or the network.
    """

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_app(self) -> None:
        if self._initialized:
            return
        import firebase_admin

        if not firebase_admin._apps:
            from app.core.config import get_settings

            creds_path = get_settings().firebase_credentials_path
            if creds_path:
                from firebase_admin import credentials

                firebase_admin.initialize_app(credentials.Certificate(creds_path))
            else:
                # Application Default Credentials (gcloud / metadata server).
                firebase_admin.initialize_app()
        self._initialized = True

    def verify(self, token: str) -> CurrentUser:
        from firebase_admin import auth as firebase_auth

        self._ensure_app()
        try:
            decoded = firebase_auth.verify_id_token(token)
        except Exception as exc:  # noqa: BLE001 — any failure is a rejected token
            raise InvalidTokenError(str(exc)) from exc
        return CurrentUser(
            uid=decoded["uid"],
            email=decoded.get("email"),
            display_name=decoded.get("name"),
        )


_verifier = FirebaseTokenVerifier()


def get_token_verifier() -> TokenVerifier:
    return _verifier


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer ") :]
    try:
        user = verifier.verify(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # contextvar feeds service-log lines; request.state feeds the access log
    # (set in the route's context, which the access middleware can read back
    # via the shared request scope).
    set_uid(user.uid)
    request.state.uid = user.uid
    return user
