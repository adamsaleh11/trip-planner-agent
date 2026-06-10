"""Invite lifecycle: admin creates → email sent + copyable link → invitee accepts."""

from app.core.auth import CurrentUser
from tests.test_trips import TRIP_PAYLOAD, _auth, create_trip, make_user


def invite(client, token, trip_id, email="friend@example.com"):
    return client.post(
        f"/trips/{trip_id}/invites", json={"email": email}, headers=_auth(token)
    )


def test_admin_invite_sends_email_and_returns_link(client, verifier, sender):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    response = invite(client, token, trip_id)

    assert response.status_code == 201
    body = response.json()
    assert body["inviteUrl"].startswith("http")
    assert body["emailSent"] is True
    assert len(sender.sent) == 1
    assert sender.sent[0]["to"] == "friend@example.com"
    assert body["inviteUrl"] in sender.sent[0]["html"]
    assert TRIP_PAYLOAD["name"] in sender.sent[0]["html"]


def test_non_admin_cannot_invite(client, verifier):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    outsider = make_user(verifier, token="tok-b", uid="user-b")

    assert invite(client, outsider, trip_id).status_code == 403


def test_email_failure_still_returns_link(client, verifier, sender):
    sender.fail = True
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    response = invite(client, token, trip_id)

    assert response.status_code == 201
    assert response.json()["emailSent"] is False
    assert response.json()["inviteUrl"]


def test_invite_lookup_is_public_and_leaks_nothing(client, verifier, sender):
    token = make_user(verifier, name="Ada")
    trip_id = create_trip(client, token).json()["id"]
    invite_token = invite(client, token, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]

    response = client.get(f"/invites/{invite_token}")  # no auth header

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "tripName": TRIP_PAYLOAD["name"],
        "destinationText": TRIP_PAYLOAD["destination"]["text"],
        "inviterName": "Ada",
        "status": "pending",
    }


def test_unknown_invite_token_is_404(client):
    assert client.get("/invites/nope").status_code == 404


def test_accept_creates_membership_and_is_idempotent(client, verifier, sender):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    invitee = make_user(verifier, token="tok-b", uid="user-b", name="Bea")

    first = client.post(f"/invites/{invite_token}/accept", headers=_auth(invitee))
    second = client.post(f"/invites/{invite_token}/accept", headers=_auth(invitee))

    assert first.status_code == 200
    assert second.status_code == 200
    members = client.get(f"/trips/{trip_id}/members", headers=_auth(invitee)).json()
    roles = {m["uid"]: m["role"] for m in members}
    assert roles == {"user-a": "admin", "user-b": "member"}
    my_trips = client.get("/trips", headers=_auth(invitee)).json()
    assert [t["id"] for t in my_trips] == [trip_id]


def test_accept_requires_auth(client, verifier, sender):
    owner = make_user(verifier)
    trip_id = create_trip(client, owner).json()["id"]
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]

    assert client.post(f"/invites/{invite_token}/accept").status_code == 401


def test_invite_used_by_someone_else_is_410(client, verifier, sender):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    first_user = make_user(verifier, token="tok-b", uid="user-b")
    second_user = make_user(verifier, token="tok-c", uid="user-c")
    client.post(f"/invites/{invite_token}/accept", headers=_auth(first_user))

    response = client.post(f"/invites/{invite_token}/accept", headers=_auth(second_user))

    assert response.status_code == 410
