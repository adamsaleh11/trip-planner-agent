"""Per-category preferences: save, read, group visibility, completion status."""

from tests.test_trips import _auth, create_trip, make_user

FOOD = {
    "freeText": "best gelato spots, a bar to watch the game 🙏",
    "dietaryRestrictions": ["vegetarian"],
    "cuisineInterests": ["local", "seafood"],
    "mealBudget": "$$",
    "drinkInterests": ["local_drinks", "coffee"],
    "sportsBarInterest": True,
}

LOGISTICS = {
    "freeText": "",
    "pace": "balanced",
    "wakeTime": "mid",
    "transport": ["walk", "transit"],
    "dailyBudget": "$$",
    "mobilityNotes": "",
}


def put_pref(client, token, trip_id, category, payload):
    return client.put(
        f"/trips/{trip_id}/preferences/{category}", json=payload, headers=_auth(token)
    )


def put_participant_pref(client, token, trip_id, participant_id, category, payload):
    return client.put(
        f"/trips/{trip_id}/preferences/participants/{participant_id}/{category}",
        json=payload,
        headers=_auth(token),
    )


def add_participant(client, token, trip_id, name="Mom"):
    return client.post(
        f"/trips/{trip_id}/participants",
        json={"displayName": name},
        headers=_auth(token),
    ).json()


def test_member_can_save_and_reload_category(client, verifier):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    saved = put_pref(client, token, trip_id, "food_drink", FOOD)
    assert saved.status_code == 200

    me = client.get(f"/trips/{trip_id}/preferences/me", headers=_auth(token))
    assert me.status_code == 200
    body = me.json()
    assert body["food_drink"]["freeText"].startswith("best gelato")
    assert body["food_drink"]["dietaryRestrictions"] == ["vegetarian"]
    assert body["outdoors_scenic"] is None  # unfilled categories are explicit nulls


def test_admin_can_save_preferences_for_manual_participant(client, verifier):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    participant = add_participant(client, owner, trip_id, "Mom")

    saved = put_participant_pref(
        client, owner, trip_id, participant["id"], "logistics", LOGISTICS
    )

    assert saved.status_code == 200
    response = client.get(f"/trips/{trip_id}/preferences", headers=_auth(owner))
    by_participant = {entry["participantId"]: entry for entry in response.json()}
    assert by_participant[participant["id"]]["displayName"] == "Mom"
    assert (
        by_participant[participant["id"]]["preferences"]["logistics"]["pace"]
        == "balanced"
    )


def test_non_admin_cannot_save_unclaimed_participant_preferences(
    client, verifier, sender
):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    participant = add_participant(client, owner, trip_id, "Mom")
    token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = make_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{token}/accept", headers=_auth(member))

    response = put_participant_pref(
        client, member, trip_id, participant["id"], "food_drink", FOOD
    )

    assert response.status_code == 403


def test_invalid_enum_rejected_with_422(client, verifier):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    response = put_pref(
        client, token, trip_id, "food_drink", {**FOOD, "mealBudget": "$$$$$"}
    )

    assert response.status_code == 422


def test_unknown_category_is_404(client, verifier):
    token = make_user(verifier)
    trip_id = create_trip(client, token).json()["id"]

    assert put_pref(client, token, trip_id, "spa_days", FOOD).status_code == 404


def test_non_member_gets_403_on_all_preference_routes(client, verifier):
    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    outsider = make_user(verifier, token="tok-b", uid="user-b")

    assert put_pref(client, outsider, trip_id, "food_drink", FOOD).status_code == 403
    assert (
        client.get(f"/trips/{trip_id}/preferences/me", headers=_auth(outsider)).status_code
        == 403
    )
    assert (
        client.get(f"/trips/{trip_id}/preferences", headers=_auth(outsider)).status_code
        == 403
    )


def test_group_preferences_visible_to_members(client, verifier, sender):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = make_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{token}/accept", headers=_auth(member))
    put_pref(client, owner, trip_id, "food_drink", FOOD)
    put_pref(client, member, trip_id, "logistics", LOGISTICS)

    response = client.get(f"/trips/{trip_id}/preferences", headers=_auth(member))

    assert response.status_code == 200
    by_claimed_uid = {entry["claimedByUid"]: entry for entry in response.json()}
    assert by_claimed_uid["user-a"]["preferences"]["food_drink"]["mealBudget"] == "$$"
    assert by_claimed_uid["user-b"]["preferences"]["logistics"]["pace"] == "balanced"


def test_completion_status_matrix(client, verifier, sender):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a")
    trip_id = create_trip(client, owner).json()["id"]
    token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = make_user(verifier, token="tok-b", uid="user-b")
    client.post(f"/invites/{token}/accept", headers=_auth(member))
    put_pref(client, owner, trip_id, "food_drink", FOOD)

    response = client.get(f"/trips/{trip_id}/preferences/status", headers=_auth(owner))

    assert response.status_code == 200
    matrix = {entry["claimedByUid"]: entry["filled"] for entry in response.json()}
    assert matrix["user-a"]["food_drink"] is True
    assert matrix["user-a"]["nightlife"] is False
    assert matrix["user-b"]["food_drink"] is False
