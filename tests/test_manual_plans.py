"""Trip manual plans: admin-authored commitments for coordinator generation."""

from tests.test_trips import _auth, create_trip, make_user


MANUAL_PLAN = {
    "category": "food_drink",
    "activity": "Dinner at Time Out Market",
    "timeOfDay": "evening",
    "date": "2026-07-11",
    "placeId": "places/time-out-market",
    "address": "Av. 24 de Julho 49, Lisbon",
    "notes": "Reservation is already booked.",
}


def test_admin_can_create_and_member_can_list_manual_plans(
    client, verifier, sender
):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = make_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{invite_token}/accept", headers=_auth(member))

    created = client.post(
        f"/trips/{trip_id}/manual-plans",
        json=MANUAL_PLAN,
        headers=_auth(owner),
    )

    assert created.status_code == 201
    body = created.json()
    assert body["id"]
    assert body["category"] == "food_drink"
    assert body["activity"] == "Dinner at Time Out Market"
    assert body["timeOfDay"] == "evening"
    assert body["date"] == "2026-07-11"
    assert body["placeId"] == "places/time-out-market"
    assert body["createdByUid"] == "user-a"
    assert body["createdAt"]
    assert body["updatedAt"]

    listed = client.get(f"/trips/{trip_id}/manual-plans", headers=_auth(member))

    assert listed.status_code == 200
    assert listed.json() == [body]


def test_manual_plan_writes_are_admin_only_and_date_must_be_in_trip(
    client, verifier, sender
):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = make_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{invite_token}/accept", headers=_auth(member))

    non_admin_create = client.post(
        f"/trips/{trip_id}/manual-plans",
        json=MANUAL_PLAN,
        headers=_auth(member),
    )
    invalid_date = client.post(
        f"/trips/{trip_id}/manual-plans",
        json={**MANUAL_PLAN, "date": "2026-08-01"},
        headers=_auth(owner),
    )
    created = client.post(
        f"/trips/{trip_id}/manual-plans",
        json=MANUAL_PLAN,
        headers=_auth(owner),
    ).json()
    non_admin_patch = client.patch(
        f"/trips/{trip_id}/manual-plans/{created['id']}",
        json={"activity": "Changed"},
        headers=_auth(member),
    )
    non_admin_delete = client.delete(
        f"/trips/{trip_id}/manual-plans/{created['id']}",
        headers=_auth(member),
    )

    assert non_admin_create.status_code == 403
    assert invalid_date.status_code == 422
    assert "inside the trip date range" in invalid_date.json()["detail"]
    assert non_admin_patch.status_code == 403
    assert non_admin_delete.status_code == 403


def test_admin_can_update_and_delete_manual_plan(client, verifier, repo):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    created = client.post(
        f"/trips/{trip_id}/manual-plans",
        json=MANUAL_PLAN,
        headers=_auth(owner),
    ).json()

    updated = client.patch(
        f"/trips/{trip_id}/manual-plans/{created['id']}",
        json={"activity": "Late dinner at Time Out Market", "date": None},
        headers=_auth(owner),
    )
    deleted = client.delete(
        f"/trips/{trip_id}/manual-plans/{created['id']}",
        headers=_auth(owner),
    )
    listed = client.get(f"/trips/{trip_id}/manual-plans", headers=_auth(owner))

    assert updated.status_code == 200
    assert updated.json()["activity"] == "Late dinner at Time Out Market"
    assert updated.json()["date"] is None
    assert updated.json()["updatedAt"] != created["updatedAt"]
    assert deleted.status_code == 204
    assert listed.json() == []
    assert repo.get(f"trips/{trip_id}/manualPlans", created["id"]) is None
