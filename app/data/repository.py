"""Firestore data layer.

All collection access goes through the :class:`Repository` interface. Routers
and services depend on this abstraction (never on a raw Firestore client), so
tests substitute an in-memory fake implementing the same narrow interface.
"""

from __future__ import annotations

import abc
from typing import Optional


class Repository(abc.ABC):
    """Narrow document store interface, scoped by caller-supplied keys."""

    @abc.abstractmethod
    def get(self, collection: str, doc_id: str) -> Optional[dict]:
        """Return the document data, or ``None`` if it does not exist."""

    @abc.abstractmethod
    def set(self, collection: str, doc_id: str, data: dict) -> None:
        """Create or overwrite the document."""

    @abc.abstractmethod
    def update(self, collection: str, doc_id: str, data: dict) -> None:
        """Merge fields into a document (other fields untouched)."""

    @abc.abstractmethod
    def delete(self, collection: str, doc_id: str) -> None:
        """Delete the document if it exists."""

    @abc.abstractmethod
    def list(self, collection: str) -> list[tuple[str, dict]]:
        """Return ``(doc_id, data)`` pairs for every document in a collection.

        Collection paths may address subcollections, e.g.
        ``trips/{trip_id}/memberships``.
        """


class FirestoreRepository(Repository):
    """Repository backed by a single ``google-cloud-firestore`` client."""

    def __init__(self, client) -> None:
        self._client = client

    def get(self, collection: str, doc_id: str) -> Optional[dict]:
        snapshot = self._client.collection(collection).document(doc_id).get()
        if not snapshot.exists:
            return None
        return snapshot.to_dict()

    def set(self, collection: str, doc_id: str, data: dict) -> None:
        self._client.collection(collection).document(doc_id).set(data)

    def update(self, collection: str, doc_id: str, data: dict) -> None:
        self._client.collection(collection).document(doc_id).set(data, merge=True)

    def delete(self, collection: str, doc_id: str) -> None:
        self._client.collection(collection).document(doc_id).delete()

    def list(self, collection: str) -> list[tuple[str, dict]]:
        return [
            (snapshot.id, snapshot.to_dict())
            for snapshot in self._client.collection(collection).stream()
        ]


_repository: Optional[Repository] = None


def get_repository() -> Repository:
    """Provide the process-wide Firestore-backed repository.

    Constructed lazily so importing this module never opens a client; tests
    override this dependency with an in-memory fake.
    """
    global _repository
    if _repository is None:
        from app.data.firestore_client import build_client

        _repository = FirestoreRepository(build_client())
    return _repository
