from __future__ import annotations

from app.core.auth import CurrentUser
from app.models.places import DestinationSearchResult
from app.services.places import GooglePlacesDestinationSearcher, get_destination_searcher


class FakeDestinationSearcher:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 5) -> list[DestinationSearchResult]:
        self.queries.append(query)
        return [
            DestinationSearchResult(
                id="places/lisbon",
                text="Lisbon, Portugal",
                lat=38.7223,
                lng=-9.1393,
                placeId="places/lisbon",
            )
        ]


def test_destination_search_requires_auth(client):
    response = client.get("/places/search?query=Lisbon")

    assert response.status_code == 401


def test_destination_search_rejects_invalid_auth(client):
    response = client.get(
        "/places/search?query=Lisbon",
        headers={"Authorization": "Bearer unknown"},
    )

    assert response.status_code == 401


def test_destination_search_returns_coordinate_payload(client, verifier):
    searcher = FakeDestinationSearcher()
    client.app.dependency_overrides[get_destination_searcher] = lambda: searcher
    verifier.add(
        "token-a",
        CurrentUser(uid="u1", email="a@example.com", display_name="Ada"),
    )

    response = client.get(
        "/places/search?query=Lisbon",
        headers={"Authorization": "Bearer token-a"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "places/lisbon",
            "text": "Lisbon, Portugal",
            "lat": 38.7223,
            "lng": -9.1393,
            "placeId": "places/lisbon",
        }
    ]
    assert searcher.queries == ["Lisbon"]


def test_destination_search_query_validation(client, verifier):
    verifier.add(
        "token-a",
        CurrentUser(uid="u1", email="a@example.com", display_name="Ada"),
    )

    too_short = client.get(
        "/places/search?query=L",
        headers={"Authorization": "Bearer token-a"},
    )
    too_long = client.get(
        f"/places/search?query={'x' * 121}",
        headers={"Authorization": "Bearer token-a"},
    )

    assert too_short.status_code == 422
    assert too_long.status_code == 422


def test_destination_search_options_uses_existing_cors_config(client):
    response = client.options(
        "/places/search?query=Lisbon",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


class FakeGoogleResponse:
    def __init__(self, payload: dict, status_error: Exception | None = None) -> None:
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def json(self) -> dict:
        return self.payload


def test_google_places_searcher_maps_results_and_limits_to_five(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeGoogleResponse(
            {
                "places": [
                    {
                        "id": f"places/{index}",
                        "displayName": {"text": f"City {index}"},
                        "formattedAddress": f"City {index}, Country",
                        "location": {"latitude": index, "longitude": -index},
                    }
                    for index in range(1, 8)
                ]
            }
        )

    monkeypatch.setattr("app.services.places.requests.post", fake_post)

    results = GooglePlacesDestinationSearcher("secret").search(" Lisbon ", limit=9)

    assert [result.id for result in results] == [
        "places/1",
        "places/2",
        "places/3",
        "places/4",
        "places/5",
    ]
    assert results[0].text == "City 1, Country"
    assert results[0].lat == 1
    assert results[0].lng == -1
    assert results[0].placeId == "places/1"
    assert calls[0]["headers"]["X-Goog-Api-Key"] == "secret"
    assert calls[0]["json"] == {
        "textQuery": "Lisbon",
        "maxResultCount": 5,
        "languageCode": "en",
    }


def test_google_places_searcher_returns_empty_for_no_results(monkeypatch):
    monkeypatch.setattr(
        "app.services.places.requests.post",
        lambda *args, **kwargs: FakeGoogleResponse({"places": []}),
    )

    assert GooglePlacesDestinationSearcher("secret").search("zz") == []


def test_google_places_searcher_returns_empty_for_blank_normalized_query():
    assert GooglePlacesDestinationSearcher("secret").search("  ") == []


def test_google_places_searcher_missing_key_returns_503():
    try:
        GooglePlacesDestinationSearcher(" ").search("Lisbon")
    except Exception as error:
        assert error.status_code == 503
        assert error.detail == "Google Places API key is not configured"
    else:
        raise AssertionError("Expected missing API key to raise")


def test_google_places_searcher_google_failure_returns_502(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("app.services.places.requests.post", fake_post)

    try:
        GooglePlacesDestinationSearcher("secret").search("Lisbon")
    except Exception as error:
        assert error.status_code == 502
        assert error.detail == "Google Places destination search failed"
    else:
        raise AssertionError("Expected Google failure to raise")
