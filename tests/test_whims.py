"""Right Now whim suggestions: synchronous, uid-scoped, metric-recorded."""

from app.core.auth import CurrentUser
from tests.test_trips import create_trip


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(verifier, token="tok-a", uid="user-a", name="Ada") -> str:
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


class ScriptedWhimRunner:
    def __init__(self) -> None:
        self.calls = []

    def suggest(
        self,
        *,
        whim_text,
        location_context,
        trip,
        group_preferences,
        exclude_place_ids,
        trace_id,
    ):
        self.calls.append(
            {
                "whimText": whim_text,
                "locationContext": location_context,
                "tripId": trip.id if trip else None,
                "excludePlaceIds": exclude_place_ids,
            }
        )
        return {
            "suggestion": {
                "placeId": "places/gelato",
                "name": "Gelato Lisboa",
                "address": "Rua Doce 1, Lisbon",
                "lat": 38.71,
                "lng": -9.14,
                "category": "food_drink",
                "whyThis": "A quick sweet stop nearby.",
                "openNow": "Not available",
                "mapsUri": "https://maps.example/gelato",
            },
            "metrics": {
                "totalTokens": 12,
                "promptTokens": 8,
                "outputTokens": 4,
                "latencyMs": 40,
                "estCostUsd": 0.00001,
                "llmCalls": 1,
                "toolCalls": 1,
                "tokensPerSecond": 300.0,
                "billingTier": "free",
            },
        }


def test_post_whim_with_coordinates_returns_suggestion_and_persists_doc(
    client, verifier, repo
):
    from app.services.whims import get_whim_runner

    runner = ScriptedWhimRunner()
    client.app.dependency_overrides[get_whim_runner] = lambda: runner
    token = _user(verifier)

    response = client.post(
        "/whims",
        json={
            "whimText": "something sweet",
            "location": {"lat": 38.7223, "lng": -9.1393},
            "excludePlaceIds": ["places/old"],
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["whimId"]
    assert body["suggestion"]["placeId"] == "places/gelato"
    assert runner.calls == [
        {
            "whimText": "something sweet",
            "locationContext": {
                "kind": "coordinates",
                "lat": 38.7223,
                "lng": -9.1393,
            },
            "tripId": None,
            "excludePlaceIds": ["places/old"],
        }
    ]

    stored = repo.get("whims", body["whimId"])
    assert stored["uid"] == "user-a"
    assert stored["whimText"] == "something sweet"
    assert stored["suggestion"]["placeId"] == "places/gelato"
    assert stored["metrics"]["latencyMs"] == 40
    assert stored["createdAt"]


def test_whim_location_validation_and_trip_membership(client, verifier):
    from app.services.whims import get_whim_runner

    runner = ScriptedWhimRunner()
    client.app.dependency_overrides[get_whim_runner] = lambda: runner
    owner = _user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    outsider = _user(verifier, token="tok-b", uid="user-b")

    missing_location = client.post(
        "/whims",
        json={"whimText": ""},
        headers=_auth(owner),
    )
    non_member_trip = client.post(
        "/whims",
        json={"whimText": "coffee", "tripId": trip_id},
        headers=_auth(outsider),
    )
    coordinates_with_trip = client.post(
        "/whims",
        json={
            "whimText": "coffee",
            "tripId": trip_id,
            "location": {"lat": 45.5017, "lng": -73.5673},
        },
        headers=_auth(owner),
    )

    assert missing_location.status_code == 422
    assert "location.lat/lng" in missing_location.json()["detail"]
    assert non_member_trip.status_code == 403
    assert coordinates_with_trip.status_code == 200
    assert runner.calls[-1]["tripId"] == trip_id
    assert runner.calls[-1]["locationContext"] == {
        "kind": "coordinates",
        "lat": 45.5017,
        "lng": -73.5673,
    }


def test_basic_whim_runner_filters_places_before_backend_random_pick(
    client, verifier, monkeypatch
):
    token = _user(verifier)

    def fake_search(query, max_result_count):
        return [
            {
                "id": "places/excluded",
                "name": "Already Seen",
                "address": "Rua A",
                "latitude": 38.7,
                "longitude": -9.1,
                "rating": 4.8,
                "business_status": "OPERATIONAL",
                "types": ["cafe"],
                "google_maps_uri": "https://maps.example/excluded",
            },
            {
                "id": "places/closed",
                "name": "Closed Cafe",
                "address": "Rua B",
                "latitude": 38.7,
                "longitude": -9.1,
                "rating": 4.6,
                "business_status": "CLOSED_TEMPORARILY",
                "types": ["cafe"],
                "google_maps_uri": "https://maps.example/closed",
            },
            {
                "id": "places/unrated",
                "name": "Mystery Cafe",
                "address": "Rua C",
                "latitude": 38.7,
                "longitude": -9.1,
                "rating": None,
                "business_status": "OPERATIONAL",
                "types": ["cafe"],
                "google_maps_uri": "https://maps.example/unrated",
            },
            {
                "id": "places/good",
                "name": "Good Cafe",
                "address": "Rua D",
                "latitude": 38.7,
                "longitude": -9.1,
                "rating": 4.5,
                "business_status": "OPERATIONAL",
                "types": ["cafe"],
                "google_maps_uri": "https://maps.example/good",
            },
        ]

    monkeypatch.setattr("app.services.whims.search_places_text", fake_search)
    monkeypatch.setattr("app.services.whims.random.choice", lambda candidates: candidates[0])

    response = client.post(
        "/whims",
        json={
            "whimText": "coffee",
            "location": {"city": "Lisbon"},
            "excludePlaceIds": ["places/excluded"],
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["placeId"] == "places/good"
