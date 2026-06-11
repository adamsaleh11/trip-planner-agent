from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.data.repository import Repository
from app.models.journal import (
    JournalContribution,
    JournalContributionUpdate,
    JournalEntry,
    JournalEntryView,
)
from app.models.trip import Trip
from app.services import collective_memory
from app.services import trips as trips_service
from app.services import whims as whims_service


def _collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/journalEntries"


def _contributions_collection(trip_id: str, entry_id: str) -> str:
    return f"{_collection(trip_id)}/{entry_id}/contributions"


def _generations_collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/generations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def journal_entry_id(place_id: str) -> str:
    return base64.urlsafe_b64encode(place_id.encode("utf-8")).decode("ascii").rstrip("=")


def complete_trip(repo: Repository, trip_id: str, uid: str) -> Trip:
    trip = trips_service.require_admin(repo, trip_id, uid)
    generation_id = getattr(trip, "latestGenerationId", None) or repo.get(
        trips_service.TRIPS_COLLECTION, trip_id
    ).get("latestGenerationId")
    if not generation_id:
        raise HTTPException(status_code=409, detail="Trip has no generated itinerary")
    generation = repo.get(_generations_collection(trip_id), generation_id)
    if generation is None or generation.get("status") != "complete":
        raise HTTPException(status_code=409, detail="Trip has no completed generation")
    _seed_journal_entries(repo, trip_id, generation.get("itinerary") or {})
    repo.update(trips_service.TRIPS_COLLECTION, trip_id, {"status": "completed"})
    return Trip(**{**trip.model_dump(), "status": "completed"})


def list_journal(repo: Repository, trip_id: str, uid: str) -> list[JournalEntryView]:
    trips_service.require_member(repo, trip_id, uid)
    views: list[JournalEntryView] = []
    for _, data in repo.list(_collection(trip_id)):
        entry = JournalEntry(**data)
        contribution = repo.get(_contributions_collection(trip_id, entry.id), uid)
        views.append(
            JournalEntryView(
                **entry.model_dump(),
                myEntry=contribution,
            )
        )
    return views


def update_journal_entry(
    repo: Repository,
    trip_id: str,
    place_id: str,
    uid: str,
    payload: JournalContributionUpdate,
    pipeline: collective_memory.SharePipeline,
) -> JournalEntryView:
    trip = trips_service.require_member(repo, trip_id, uid)
    entry_id = journal_entry_id(place_id)
    data = repo.get(_collection(trip_id), entry_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    entry = JournalEntry(**data)
    if payload.shareAnonymously and payload.rating is None:
        raise HTTPException(
            status_code=422,
            detail="Rating is required to share anonymously",
        )
    shared_opaque_id = None
    share_anonymously = payload.shareAnonymously
    share_error = None
    existing_contribution = repo.get(_contributions_collection(trip_id, entry_id), uid)
    if payload.shareAnonymously:
        try:
            shared_opaque_id = collective_memory.upsert_share(
                repo,
                trip=trip,
                uid=uid,
                entry=entry,
                payload=payload,
                pipeline=pipeline,
            )
        except Exception:
            share_anonymously = False
            share_error = "share_failed"
    elif existing_contribution and existing_contribution.get("sharedOpaqueId"):
        collective_memory.delete_share(
            repo, uid, existing_contribution["sharedOpaqueId"]
        )
    contribution = JournalContribution(
        rating=payload.rating,
        note=payload.note,
        shareAnonymously=share_anonymously,
        sharedOpaqueId=shared_opaque_id,
        shareError=share_error,
        updatedAt=_now(),
    )
    repo.set(
        _contributions_collection(trip_id, entry_id),
        uid,
        contribution.model_dump(),
    )
    return JournalEntryView(**entry.model_dump(), myEntry=contribution)


def create_entry_from_whim(
    repo: Repository,
    trip_id: str,
    whim_id: str,
    uid: str,
) -> JournalEntry:
    trips_service.require_member(repo, trip_id, uid)
    whim = repo.get(whims_service.WHIMS_COLLECTION, whim_id)
    if whim is None:
        raise HTTPException(status_code=404, detail="Whim not found")
    if whim.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Only the whim owner can save it")
    if whim.get("tripId") != trip_id:
        raise HTTPException(status_code=422, detail="Whim is not attached to this trip")
    suggestion = whim.get("suggestion") or {}
    place_id = suggestion.get("placeId")
    if not place_id:
        raise HTTPException(status_code=422, detail="Whim suggestion has no placeId")
    entry_id = journal_entry_id(place_id)
    existing = repo.get(_collection(trip_id), entry_id)
    if existing is not None:
        return JournalEntry(**existing)
    timestamp = _now()
    entry = JournalEntry(
        id=entry_id,
        placeId=place_id,
        name=suggestion.get("name") or "Not available",
        category=suggestion.get("category"),
        address=suggestion.get("address") or "Not available",
        lat=suggestion.get("lat"),
        lng=suggestion.get("lng"),
        source="whim",
        createdAt=timestamp,
        updatedAt=timestamp,
    )
    repo.set(_collection(trip_id), entry.id, entry.model_dump())
    return entry


def _seed_journal_entries(repo: Repository, trip_id: str, itinerary: dict[str, Any]) -> None:
    timestamp = _now()
    seen: set[str] = set()
    for stop in _iter_stops(itinerary):
        place_id = stop.get("placeId")
        if not place_id or place_id in seen:
            continue
        seen.add(place_id)
        entry_id = journal_entry_id(place_id)
        if repo.get(_collection(trip_id), entry_id) is not None:
            continue
        entry = JournalEntry(
            id=entry_id,
            placeId=place_id,
            name=stop.get("name") or "Not available",
            category=stop.get("category"),
            address=stop.get("address") or "Not available",
            lat=stop.get("lat"),
            lng=stop.get("lng"),
            source=stop.get("source") or "ai_suggestion",
            manualPlanId=stop.get("manualPlanId"),
            createdAt=timestamp,
            updatedAt=timestamp,
        )
        repo.set(_collection(trip_id), entry.id, entry.model_dump())


def _iter_stops(itinerary: dict[str, Any]):
    for day in itinerary.get("days") or []:
        for block in day.get("blocks") or []:
            for stop in block.get("stops") or []:
                yield stop
