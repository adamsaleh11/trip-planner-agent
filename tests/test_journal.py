"""Trip journal and anonymous collective memory behavior."""

from app.core.auth import CurrentUser
from tests.test_trips import _auth, create_trip, make_user


def _add_user(verifier, token: str, uid: str, name: str) -> str:
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


def _seed_generation(repo, trip_id: str) -> str:
    generation_id = "gen-complete"
    repo.update(
        f"trips/{trip_id}/generations",
        generation_id,
        {
            "status": "complete",
            "itinerary": {
                "days": [
                    {
                        "date": "2026-07-10",
                        "blocks": [
                            {
                                "period": "morning",
                                "stops": [
                                    {
                                        "time": "09:30",
                                        "placeId": "places/cafe-lisboa",
                                        "name": "Cafe Lisboa",
                                        "address": "Rua A, Lisbon",
                                        "lat": 38.71,
                                        "lng": -9.14,
                                        "category": "food_drink",
                                        "transport": {
                                            "mode": "walk",
                                            "durationText": "10 mins",
                                        },
                                        "whyItFits": "Starts the day with coffee.",
                                        "suggested": False,
                                        "source": "participant_preference",
                                    },
                                    {
                                        "time": "20:00",
                                        "placeId": "places/time-out-market",
                                        "name": "Dinner at Time Out Market",
                                        "address": "Av. 24 de Julho 49, Lisbon",
                                        "lat": None,
                                        "lng": None,
                                        "category": "food_drink",
                                        "transport": {
                                            "mode": "walk",
                                            "durationText": "Not available",
                                        },
                                        "whyItFits": "User-added manual plan.",
                                        "suggested": False,
                                        "source": "manual_plan",
                                        "manualPlanId": "plan-1",
                                    },
                                ],
                            }
                        ],
                    }
                ]
            },
        },
    )
    repo.update("trips", trip_id, {"status": "generated", "latestGenerationId": generation_id})
    return generation_id


def test_admin_completes_trip_and_members_can_read_journal_stubs(
    client, verifier, repo, sender
):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    _seed_generation(repo, trip_id)
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = _add_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{invite_token}/accept", headers=_auth(member))

    response = client.post(f"/trips/{trip_id}/complete", headers=_auth(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    journal = client.get(f"/trips/{trip_id}/journal", headers=_auth(member))
    assert journal.status_code == 200
    entries = journal.json()
    assert [entry["placeId"] for entry in entries] == [
        "places/cafe-lisboa",
        "places/time-out-market",
    ]
    assert entries[0]["name"] == "Cafe Lisboa"
    assert entries[0]["category"] == "food_drink"
    assert entries[0]["myEntry"] is None
    assert entries[1]["source"] == "manual_plan"
    assert entries[1]["manualPlanId"] == "plan-1"


def test_member_can_save_private_journal_note_without_exposing_it_to_other_members(
    client, verifier, repo, sender
):
    from tests.test_invites import invite

    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    _seed_generation(repo, trip_id)
    client.post(f"/trips/{trip_id}/complete", headers=_auth(owner))
    invite_token = invite(client, owner, trip_id).json()["inviteUrl"].rsplit("/", 1)[-1]
    member = _add_user(verifier, token="tok-b", uid="user-b", name="Bea")
    client.post(f"/invites/{invite_token}/accept", headers=_auth(member))

    saved = client.put(
        f"/trips/{trip_id}/journal/places%2Fcafe-lisboa",
        json={"rating": 5, "note": "Adam loved this place"},
        headers=_auth(owner),
    )

    assert saved.status_code == 200
    assert saved.json()["myEntry"]["rating"] == 5
    assert saved.json()["myEntry"]["note"] == "Adam loved this place"
    assert saved.json()["myEntry"]["shareAnonymously"] is False

    owner_entries = client.get(f"/trips/{trip_id}/journal", headers=_auth(owner)).json()
    member_entries = client.get(f"/trips/{trip_id}/journal", headers=_auth(member)).json()

    assert owner_entries[0]["myEntry"]["note"] == "Adam loved this place"
    assert member_entries[0]["myEntry"] is None


def test_shared_journal_note_writes_anonymized_collective_memory_payload(
    client, verifier, repo
):
    from app.services.collective_memory import SharePipeline, get_share_pipeline

    class FakePipeline(SharePipeline):
        def scrub(self, text, blocked_terms):
            assert "Ada" in blocked_terms
            return text.replace("Ada", "").replace("adam@example.com", "")

        def embed(self, text):
            return [1.0, 0.0, 0.0]

    client.app.dependency_overrides[get_share_pipeline] = lambda: FakePipeline()
    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    _seed_generation(repo, trip_id)
    client.post(f"/trips/{trip_id}/complete", headers=_auth(owner))

    saved = client.put(
        f"/trips/{trip_id}/journal/places%2Fcafe-lisboa",
        json={
            "rating": 5,
            "note": "Ada loved this place. Email adam@example.com @ada 555-123-4567",
            "shareAnonymously": True,
        },
        headers=_auth(owner),
    )

    assert saved.status_code == 200
    opaque_id = saved.json()["myEntry"]["sharedOpaqueId"]
    memory = repo.get("collectiveMemory", opaque_id)
    assert memory["destination"] == "lisbon"
    assert memory["category"] == "food_drink"
    assert memory["placeId"] == "places/cafe-lisboa"
    assert memory["venueName"] == "Cafe Lisboa"
    assert memory["rating"] == 5
    assert memory["embedding"] == [1.0, 0.0, 0.0]
    assert memory["groupSizeBucket"] == "solo"
    assert memory["monthVisited"] == 7
    assert "user-a" not in memory
    assert "tripId" not in memory
    assert "Ada" not in memory["scrubbedText"]
    assert "adam@example.com" not in memory["scrubbedText"]
    assert "@ada" not in memory["scrubbedText"]
    assert "555-123-4567" not in memory["scrubbedText"]

    share_map = repo.get(f"collectiveMemoryShares/user-a/items", opaque_id)
    assert share_map["opaqueId"] == opaque_id
    assert share_map["placeId"] == "places/cafe-lisboa"


def test_collective_memory_search_and_delete_removes_shared_tip(
    client, verifier, repo, monkeypatch
):
    from app.services.collective_memory import SharePipeline, get_share_pipeline
    import travel_agent.graph as graph

    class FakePipeline(SharePipeline):
        def scrub(self, text, blocked_terms):
            return text

        def embed(self, text):
            return [1.0, 0.0, 0.0]

    client.app.dependency_overrides[get_share_pipeline] = lambda: FakePipeline()
    monkeypatch.setattr(graph, "get_repository", lambda: repo)
    monkeypatch.setattr(graph, "get_share_pipeline", lambda: FakePipeline())
    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    _seed_generation(repo, trip_id)
    client.post(f"/trips/{trip_id}/complete", headers=_auth(owner))
    saved = client.put(
        f"/trips/{trip_id}/journal/places%2Fcafe-lisboa",
        json={
            "rating": 5,
            "note": "Order the pastel de nata before noon.",
            "shareAnonymously": True,
        },
        headers=_auth(owner),
    )
    opaque_id = saved.json()["myEntry"]["sharedOpaqueId"]

    before = graph.search_collective_memory(
        "Lisbon, Portugal", "food_drink", "coffee pastry"
    )
    deleted = client.delete(f"/me/shares/{opaque_id}", headers=_auth(owner))
    after = graph.search_collective_memory(
        "Lisbon, Portugal", "food_drink", "coffee pastry"
    )

    assert before["status"] == "ok"
    assert before["results"][0]["opaqueId"] == opaque_id
    assert before["results"][0]["text"] == "Order the pastel de nata before noon."
    assert deleted.status_code == 204
    assert after["results"] == []
    assert repo.get("collectiveMemory", opaque_id) is None
    assert repo.get("collectiveMemoryShares/user-a/items", opaque_id) is None


def test_toggling_shared_journal_entry_off_deletes_collective_memory(
    client, verifier, repo
):
    from app.services.collective_memory import SharePipeline, get_share_pipeline

    class FakePipeline(SharePipeline):
        def scrub(self, text, blocked_terms):
            return text

        def embed(self, text):
            return [1.0, 0.0, 0.0]

    client.app.dependency_overrides[get_share_pipeline] = lambda: FakePipeline()
    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    _seed_generation(repo, trip_id)
    client.post(f"/trips/{trip_id}/complete", headers=_auth(owner))
    shared = client.put(
        f"/trips/{trip_id}/journal/places%2Fcafe-lisboa",
        json={
            "rating": 5,
            "note": "Worth sharing.",
            "shareAnonymously": True,
        },
        headers=_auth(owner),
    )
    opaque_id = shared.json()["myEntry"]["sharedOpaqueId"]

    unshared = client.put(
        f"/trips/{trip_id}/journal/places%2Fcafe-lisboa",
        json={"rating": 4, "note": "Private update.", "shareAnonymously": False},
        headers=_auth(owner),
    )

    assert unshared.status_code == 200
    assert unshared.json()["myEntry"]["shareAnonymously"] is False
    assert unshared.json()["myEntry"]["sharedOpaqueId"] is None
    assert repo.get("collectiveMemory", opaque_id) is None
    assert repo.get("collectiveMemoryShares/user-a/items", opaque_id) is None


def test_whim_owner_can_save_trip_context_whim_to_journal(client, verifier, repo):
    from app.services.whims import get_whim_runner
    from tests.test_whims import ScriptedWhimRunner

    runner = ScriptedWhimRunner()
    client.app.dependency_overrides[get_whim_runner] = lambda: runner
    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    whim = client.post(
        "/whims",
        json={"whimText": "something sweet", "tripId": trip_id},
        headers=_auth(owner),
    ).json()

    saved = client.post(
        f"/trips/{trip_id}/journal/from-whim/{whim['whimId']}",
        headers=_auth(owner),
    )

    assert saved.status_code == 201
    assert saved.json()["placeId"] == "places/gelato"
    assert saved.json()["source"] == "whim"
    journal = client.get(f"/trips/{trip_id}/journal", headers=_auth(owner)).json()
    assert [entry["placeId"] for entry in journal] == ["places/gelato"]
    assert journal[0]["name"] == "Gelato Lisboa"


def test_trip_context_whim_response_includes_matching_travelers_tip(
    client, verifier, repo
):
    from app.services.collective_memory import SharePipeline, get_share_pipeline
    from app.services.whims import get_whim_runner
    from tests.test_whims import ScriptedWhimRunner

    class FakePipeline(SharePipeline):
        def scrub(self, text, blocked_terms):
            return text

        def embed(self, text):
            return [1.0, 0.0, 0.0]

    client.app.dependency_overrides[get_share_pipeline] = lambda: FakePipeline()
    client.app.dependency_overrides[get_whim_runner] = lambda: ScriptedWhimRunner()
    owner = make_user(verifier, token="tok-a", uid="user-a", name="Ada")
    trip_id = create_trip(client, owner).json()["id"]
    repo.set(
        "collectiveMemory",
        "tip-1",
        {
            "destination": "lisbon",
            "category": "food_drink",
            "placeId": "places/gelato",
            "venueName": "Gelato Lisboa",
            "rating": 5,
            "scrubbedText": "Travelers say the pistachio is the move.",
            "groupSizeBucket": "small",
            "monthVisited": 7,
            "embedding": [1.0, 0.0, 0.0],
        },
    )

    response = client.post(
        "/whims",
        json={"whimText": "something sweet", "tripId": trip_id},
        headers=_auth(owner),
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["travelersTip"] == (
        "Travelers say the pistachio is the move."
    )
