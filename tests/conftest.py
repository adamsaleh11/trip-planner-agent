"""Shared test fakes and fixtures.

Tests exercise the service through the HTTP layer. Auth and the Firestore
data layer are swapped for in-memory fakes via ``app.dependency_overrides`` so
no network, emulator, or Docker is required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, InvalidTokenError, get_token_verifier
from app.data.repository import Repository, get_repository
from app.main import create_app


class FakeTokenVerifier:
    """Maps opaque test tokens to users. Unknown tokens are rejected."""

    def __init__(self) -> None:
        self._users: dict[str, CurrentUser] = {}

    def add(self, token: str, user: CurrentUser) -> None:
        self._users[token] = user

    def verify(self, token: str) -> CurrentUser:
        if token not in self._users:
            raise InvalidTokenError("unknown token")
        return self._users[token]


class FakeRepository(Repository):
    """In-memory Firestore stand-in implementing the repository interface."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}
        self.set_calls = 0
        self.get_calls = 0

    def _key(self, collection: str, doc_id: str) -> str:
        return f"{collection}/{doc_id}"

    def get(self, collection: str, doc_id: str) -> dict | None:
        self.get_calls += 1
        return self.store.get(self._key(collection, doc_id))

    def set(self, collection: str, doc_id: str, data: dict) -> None:
        self.set_calls += 1
        self.store[self._key(collection, doc_id)] = dict(data)

    def update(self, collection: str, doc_id: str, data: dict) -> None:
        key = self._key(collection, doc_id)
        self.store[key] = {**self.store.get(key, {}), **data}

    def delete(self, collection: str, doc_id: str) -> None:
        self.store.pop(self._key(collection, doc_id), None)

    def list(self, collection: str) -> list[tuple[str, dict]]:
        prefix = f"{collection}/"
        return [
            (key[len(prefix):], dict(data))
            for key, data in self.store.items()
            if key.startswith(prefix) and "/" not in key[len(prefix):]
        ]


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


class FakeEmailSender:
    """Records sends; flips to failure mode via ``fail = True``."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail = False

    def send_invite(self, to: str, html: str, subject: str) -> bool:
        if self.fail:
            return False
        self.sent.append({"to": to, "html": html, "subject": subject})
        return True


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def client(
    verifier: FakeTokenVerifier, repo: FakeRepository, sender: FakeEmailSender
) -> TestClient:
    from app.services.email import get_invite_sender

    app = create_app()
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_invite_sender] = lambda: sender
    return TestClient(app)
