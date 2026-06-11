from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.core.observability import start_span
from app.data.repository import Repository
from app.models.preferences import GroupPreferencesEntry
from app.models.trip import Trip
from app.models.whim import WhimRequest, WhimResponse, WhimSuggestion
from app.services import preferences as prefs_service
from app.services import trips as trips_service
from travel_agent.tools.location_research import search_places_text


WHIMS_COLLECTION = "whims"


class WhimRunner(Protocol):
    def suggest(
        self,
        *,
        whim_text: str,
        location_context: dict[str, Any],
        trip: Trip | None,
        group_preferences: list[GroupPreferencesEntry],
        exclude_place_ids: list[str],
        trace_id: str,
    ) -> dict[str, Any]:
        ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_whim(
    repo: Repository,
    user: CurrentUser,
    payload: WhimRequest,
    runner: WhimRunner,
    memory_pipeline,
) -> WhimResponse:
    trace_id = uuid.uuid4().hex
    span = start_span(
        "whim.request",
        trace_id,
        {
            "traceId": trace_id,
            "tripId": payload.tripId or "",
        },
    )
    trip: Trip | None = None
    try:
        group_preferences: list[GroupPreferencesEntry] = []
        if payload.tripId:
            trip = trips_service.require_member(repo, payload.tripId, user.uid)
            group_preferences = prefs_service.get_group_preferences(
                repo, payload.tripId, user.uid
            )
        location_context = _resolve_location_context(payload, trip)
        output = runner.suggest(
            whim_text=payload.whimText,
            location_context=location_context,
            trip=trip,
            group_preferences=group_preferences,
            exclude_place_ids=payload.excludePlaceIds,
            trace_id=trace_id,
        )
        suggestion = WhimSuggestion(**output["suggestion"])
        if trip is not None:
            _attach_travelers_tip(
                repo,
                suggestion,
                trip.destination.text,
                payload.whimText or suggestion.name,
                memory_pipeline,
            )
        whim_id = uuid.uuid4().hex
        repo.set(
            WHIMS_COLLECTION,
            whim_id,
            {
                "id": whim_id,
                "uid": user.uid,
                "tripId": payload.tripId,
                "whimText": payload.whimText,
                "suggestion": suggestion.model_dump(),
                "metrics": output.get("metrics", _empty_metrics()),
                "traceId": trace_id,
                "createdAt": _now(),
            },
        )
        span.end()
        return WhimResponse(suggestion=suggestion, whimId=whim_id)
    except Exception as exc:
        span.end(exc)
        raise


def _attach_travelers_tip(
    repo: Repository,
    suggestion: WhimSuggestion,
    destination: str,
    query: str,
    memory_pipeline,
) -> None:
    from app.services.collective_memory import search_memory

    results = search_memory(
        repo,
        pipeline=memory_pipeline,
        destination=destination,
        category=suggestion.category,
        query=query,
        limit=5,
    )
    for result in results["results"]:
        if result.get("placeId") == suggestion.placeId:
            suggestion.travelersTip = result.get("text")
            return


def _resolve_location_context(payload: WhimRequest, trip: Trip | None) -> dict[str, Any]:
    location = payload.location
    if location and location.lat is not None and location.lng is not None:
        return {"kind": "coordinates", "lat": location.lat, "lng": location.lng}
    if trip is not None:
        return {
            "kind": "trip_destination",
            "text": trip.destination.text,
            "lat": trip.destination.lat,
            "lng": trip.destination.lng,
            "placeId": trip.destination.placeId,
        }
    if location and location.city:
        return {"kind": "city", "city": location.city}
    raise HTTPException(
        status_code=422,
        detail="Provide location.lat/lng, tripId, or location.city",
    )


class BasicWhimRunner:
    def suggest(
        self,
        *,
        whim_text: str,
        location_context: dict[str, Any],
        trip: Trip | None,
        group_preferences: list[GroupPreferencesEntry],
        exclude_place_ids: list[str],
        trace_id: str,
    ) -> dict[str, Any]:
        start = time.monotonic()
        query = _query_for_whim(whim_text, location_context)
        places = search_places_text(query, max_result_count=10)
        candidates = _qualified_candidates(places, exclude_place_ids)
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail="No nearby suggestions found for that whim. Try another mood.",
            )
        place = random.choice(candidates)
        metrics = _empty_metrics()
        metrics["latencyMs"] = int((time.monotonic() - start) * 1000)
        metrics["toolCalls"] = 1
        return {
            "suggestion": {
                "placeId": place["id"],
                "name": place.get("name") or "Not available",
                "address": place.get("address") or "Not available",
                "lat": place.get("latitude"),
                "lng": place.get("longitude"),
                "category": _category_for_place(place),
                "whyThis": _why_this(whim_text),
                "openNow": "Not available",
                "mapsUri": place.get("google_maps_uri") or "",
            },
            "metrics": metrics,
        }


def _query_for_whim(whim_text: str, location_context: dict[str, Any]) -> str:
    text = whim_text.strip() or "interesting cafe or scenic walk"
    if location_context["kind"] == "coordinates":
        return f"{text} near {location_context['lat']},{location_context['lng']}"
    if location_context["kind"] == "trip_destination":
        return f"{text} near {location_context['text']}"
    return f"{text} in {location_context['city']}"


def _qualified_candidates(
    places: list[dict[str, Any]], exclude_place_ids: list[str]
) -> list[dict[str, Any]]:
    excluded = set(exclude_place_ids)
    qualified = []
    for place in places:
        place_id = place.get("id")
        if not place_id or place_id in excluded:
            continue
        if place.get("business_status") not in {None, "OPERATIONAL"}:
            continue
        if place.get("rating") is None:
            continue
        qualified.append(place)
    return qualified


def _category_for_place(place: dict[str, Any]) -> str:
    types = set(place.get("types") or [])
    if {"restaurant", "cafe", "bakery", "bar"} & types:
        return "food_drink"
    if {"hair_care", "beauty_salon"} & types:
        return "logistics"
    if {"night_club", "bar"} & types:
        return "nightlife"
    if {"museum", "tourist_attraction"} & types:
        return "culture_local"
    return "outdoors_scenic"


def _why_this(whim_text: str) -> str:
    text = whim_text.strip()
    if not text:
        return "A spontaneous nearby pick for right now."
    return f"Matches your mood for {text}."


def _empty_metrics() -> dict[str, Any]:
    return {
        "totalTokens": 0,
        "promptTokens": 0,
        "outputTokens": 0,
        "latencyMs": 0,
        "estCostUsd": 0.0,
        "llmCalls": 0,
        "toolCalls": 0,
        "tokensPerSecond": 0.0,
        "billingTier": "free",
    }


_runner: WhimRunner | None = None


def get_whim_runner() -> WhimRunner:
    global _runner
    if _runner is None:
        _runner = BasicWhimRunner()
    return _runner
