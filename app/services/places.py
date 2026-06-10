from __future__ import annotations

from typing import Protocol

import requests
from fastapi import HTTPException

from app.core.config import get_settings
from app.models.places import DestinationSearchResult


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DESTINATION_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
    ]
)


class DestinationSearcher(Protocol):
    def search(self, query: str, limit: int = 5) -> list[DestinationSearchResult]:
        ...


class GooglePlacesDestinationSearcher:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key.strip() if api_key else None

    def search(self, query: str, limit: int = 5) -> list[DestinationSearchResult]:
        if not self.api_key:
            raise HTTPException(
                status_code=503,
                detail="Google Places API key is not configured",
            )

        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return []

        result_limit = max(1, min(limit, 5))
        try:
            response = requests.post(
                TEXT_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": DESTINATION_FIELD_MASK,
                },
                json={
                    "textQuery": normalized_query,
                    "maxResultCount": result_limit,
                    "languageCode": "en",
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (ValueError, requests.RequestException) as error:
            raise HTTPException(
                status_code=502,
                detail="Google Places destination search failed",
            ) from error

        results: list[DestinationSearchResult] = []
        for place in payload.get("places", []):
            location = place.get("location") or {}
            place_id = place.get("id")
            lat = location.get("latitude")
            lng = location.get("longitude")

            if not place_id or lat is None or lng is None:
                continue

            display_name = place.get("displayName") or {}
            text = place.get("formattedAddress") or display_name.get("text") or place_id
            results.append(
                DestinationSearchResult(
                    id=place_id,
                    text=text,
                    lat=lat,
                    lng=lng,
                    placeId=place_id,
                )
            )
            if len(results) >= result_limit:
                break

        return results


def get_destination_searcher() -> DestinationSearcher:
    return GooglePlacesDestinationSearcher(get_settings().google_maps_api_key)
