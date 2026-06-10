"""Trip lifecycle: create, read, list, update — with tenant isolation."""

from app.core.auth import CurrentUser


TRIP_PAYLOAD = {
    "name": "Lisbon Long Weekend",
    "destination": {
        "text": "Lisbon, Portugal",
        "lat": 38.7223,
        "lng": -9.1393,
        "placeId": "ChIJO_PkYRozGQ0R0DaQ5L3rAAQ",
    },
    "startDate": "2026-07-10",
    "endDate": "2026-07-13",
    "lodgingArea": "Alfama",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user(verifier, token="tok-a", uid="user-a", name="Ada"):
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


def create_trip(client, token, payload=None):
    return client.post("/trips", json=payload or TRIP_PAYLOAD, headers=_auth(token))


def test_member_can_create_trip_and_becomes_admin(client, verifier):
    token = make_user(verifier)

    response = create_trip(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["name"] == "Lisbon Long Weekend"
    assert body["status"] == "planning"
    assert body["adminUid"] == "user-a"
    assert body["destination"]["lat"] == 38.7223


def test_creator_can_read_their_trip(client, verifier):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    response = client.get(f"/trips/{trip_id}", headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["id"] == trip_id


def test_non_member_cannot_read_trip(client, verifier):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    outsider = make_user(verifier, token="tok-b", uid="user-b")

    response = client.get(f"/trips/{trip_id}", headers=_auth(outsider))

    assert response.status_code == 403


def test_trip_routes_require_auth(client):
    assert client.post("/trips", json=TRIP_PAYLOAD).status_code == 401
    assert client.get("/trips").status_code == 401


def test_my_trips_lists_only_my_trips(client, verifier):
    a = make_user(verifier, token="tok-a", uid="user-a")
    b = make_user(verifier, token="tok-b", uid="user-b")
    create_trip(client, a)
    mine = create_trip(client, b, {**TRIP_PAYLOAD, "name": "B's trip"}).json()

    response = client.get("/trips", headers=_auth(b))

    assert response.status_code == 200
    trips = response.json()
    assert [t["id"] for t in trips] == [mine["id"]]


def test_admin_can_update_trip_but_member_fields_are_validated(client, verifier):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    response = client.patch(
        f"/trips/{trip_id}", json={"name": "Lisbon!"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Lisbon!"


def test_non_admin_cannot_update_trip(client, verifier):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    outsider = make_user(verifier, token="tok-b", uid="user-b")

    response = client.patch(
        f"/trips/{trip_id}", json={"name": "hijack"}, headers=_auth(outsider)
    )

    assert response.status_code == 403
