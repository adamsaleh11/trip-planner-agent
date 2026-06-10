from app.core.auth import CurrentUser


def test_me_without_token_returns_401(client):
    response = client.get("/me")

    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    response = client.get("/me", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


def test_me_with_valid_token_returns_profile(client, verifier):
    verifier.add(
        "good", CurrentUser(uid="u1", email="a@b.com", display_name="Ada")
    )

    response = client.get("/me", headers={"Authorization": "Bearer good"})

    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "u1"
    assert body["email"] == "a@b.com"
    assert body["displayName"] == "Ada"
    assert body["memberTripIds"] == []
    assert body["createdAt"]


def test_me_provisions_user_doc_exactly_once(client, verifier, repo):
    verifier.add("good", CurrentUser(uid="u1", email="a@b.com"))

    first = client.get("/me", headers={"Authorization": "Bearer good"})
    second = client.get("/me", headers={"Authorization": "Bearer good"})

    assert first.json() == second.json()
    assert repo.set_calls == 1  # provisioned once, idempotent on repeat
    assert repo.get_calls == 2  # one read per call, no extra read after provisioning
