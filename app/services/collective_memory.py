from __future__ import annotations

import hashlib
import hmac
import math
import re
from datetime import date
from typing import Protocol

from fastapi import HTTPException

from app.core.config import get_settings
from app.data.repository import Repository
from app.models.journal import JournalContributionUpdate, JournalEntry
from app.models.trip import Trip
from app.services import trips as trips_service


COLLECTIVE_MEMORY_COLLECTION = "collectiveMemory"
SHARES_COLLECTION = "collectiveMemoryShares"


class SharePipeline(Protocol):
    def scrub(self, text: str, blocked_terms: list[str]) -> str:
        ...

    def embed(self, text: str) -> list[float]:
        ...


class LocalSharePipeline:
    def scrub(self, text: str, blocked_terms: list[str]) -> str:
        scrubbed = text
        for term in blocked_terms:
            if term:
                scrubbed = re.sub(re.escape(term), "", scrubbed, flags=re.IGNORECASE)
        return scrubbed

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [byte / 255 for byte in digest[:16]]


def get_share_pipeline() -> SharePipeline:
    return LocalSharePipeline()


def upsert_share(
    repo: Repository,
    *,
    trip: Trip,
    uid: str,
    entry: JournalEntry,
    payload: JournalContributionUpdate,
    pipeline: SharePipeline,
) -> str:
    secret = get_settings().server_hmac_secret
    if not secret:
        raise HTTPException(status_code=500, detail="SERVER_HMAC_SECRET is required")
    opaque_id = opaque_share_id(secret, uid, trip.id, entry.placeId)
    blocked_terms = _member_display_names(repo, trip.id)
    scrubbed = scrub_text(pipeline.scrub(payload.note, blocked_terms))
    embedding_input = " ".join(
        part
        for part in [
            scrubbed,
            entry.name,
            _destination_token(trip.destination.text),
            entry.category,
        ]
        if part
    )
    memory_doc = {
        "destination": _destination_token(trip.destination.text),
        "category": entry.category,
        "placeId": entry.placeId,
        "venueName": entry.name,
        "rating": payload.rating,
        "scrubbedText": scrubbed,
        "groupSizeBucket": _group_size_bucket(
            len(trips_service.list_participants_raw(repo, trip.id))
        ),
        "monthVisited": date.fromisoformat(trip.startDate).month,
        "embedding": pipeline.embed(embedding_input),
    }
    repo.set(COLLECTIVE_MEMORY_COLLECTION, opaque_id, memory_doc)
    repo.set(
        _share_items_collection(uid),
        opaque_id,
        {
            "opaqueId": opaque_id,
            "placeId": entry.placeId,
            "tripName": trip.name,
            "venueName": entry.name,
            "category": entry.category,
        },
    )
    return opaque_id


def delete_share(repo: Repository, uid: str, opaque_id: str) -> None:
    share = repo.get(_share_items_collection(uid), opaque_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    repo.delete(COLLECTIVE_MEMORY_COLLECTION, opaque_id)
    repo.delete(_share_items_collection(uid), opaque_id)


def list_shares(repo: Repository, uid: str) -> list[dict]:
    return [data for _, data in repo.list(_share_items_collection(uid))]


def search_memory(
    repo: Repository,
    *,
    pipeline: SharePipeline,
    destination: str,
    category: str,
    query: str = "",
    limit: int = 5,
) -> dict:
    destination_token = _destination_token(destination)
    query_embedding = pipeline.embed(query or f"{destination_token} {category}")
    scored = []
    for opaque_id, data in repo.list(COLLECTIVE_MEMORY_COLLECTION):
        if data.get("destination") != destination_token:
            continue
        if data.get("category") != category:
            continue
        score = cosine_similarity(query_embedding, data.get("embedding") or [])
        scored.append((score, opaque_id, data))
    scored.sort(key=lambda item: item[0], reverse=True)
    return {
        "destination": destination_token,
        "category": category,
        "query": query,
        "limit": limit,
        "status": "ok",
        "results": [
            {
                "opaqueId": opaque_id,
                "placeId": data.get("placeId"),
                "venueName": data.get("venueName"),
                "rating": data.get("rating"),
                "text": data.get("scrubbedText"),
                "groupSizeBucket": data.get("groupSizeBucket"),
                "monthVisited": data.get("monthVisited"),
                "score": score,
            }
            for score, opaque_id, data in scored[:limit]
        ],
    }


def opaque_share_id(secret: str, uid: str, trip_id: str, place_id: str) -> str:
    raw = f"{uid}:{trip_id}:{place_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def scrub_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\+?\d[\d .()-]{7,}\d", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _share_items_collection(uid: str) -> str:
    return f"{SHARES_COLLECTION}/{uid}/items"


def _member_display_names(repo: Repository, trip_id: str) -> list[str]:
    names = [
        data.get("displayName")
        for _, data in trips_service.list_members_raw(repo, trip_id)
    ]
    names.extend(
        data.get("displayName")
        for _, data in trips_service.list_participants_raw(repo, trip_id)
    )
    return [name for name in names if name]


def _destination_token(destination: str) -> str:
    city = destination.split(",", 1)[0].strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", city).strip("-")


def _group_size_bucket(count: int) -> str:
    if count <= 1:
        return "solo"
    if count <= 4:
        return "small"
    return "large"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
