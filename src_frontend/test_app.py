import io

from whoiswho import auth, config, storage
from whoiswho import avatar_storage as avatar_storage_module
from whoiswho import create_app


def _configure_app(monkeypatch, tmp_path, auth_mode="mock", secret_key=None, allowed_groups=""):
    """Build a fresh app instance against isolated storage, without touching real env vars.

    config.py/storage.py/avatar_storage.py read their settings as module-level attributes
    at call time, so patching those attributes directly is equivalent to (and simpler than)
    monkeypatch.setenv + importlib.reload.
    """
    data_dir = tmp_path / "data"
    avatar_dir = data_dir / "avatars"
    data_dir.mkdir(parents=True, exist_ok=True)
    avatar_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "AUTH_MODE", auth_mode)
    monkeypatch.setattr(config, "SECRET_KEY", secret_key or ("whoiswho-dev-secret" if auth_mode == "mock" else None))
    monkeypatch.setattr(
        config,
        "ENTRA_ALLOWED_GROUPS",
        [group_id.strip() for group_id in allowed_groups.split(",") if group_id.strip()],
    )

    monkeypatch.setattr(storage, "TABLE_FILES", {
        "Users": data_dir / "users.json",
        "Employees": data_dir / "employees.json",
    })
    monkeypatch.setattr(avatar_storage_module, "LOCAL_UPLOAD_DIR", avatar_dir)

    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    return app


def test_profile_update_is_persisted_to_json(tmp_path, monkeypatch):
    app = _configure_app(monkeypatch, tmp_path)
    client = app.test_client()

    response = client.post(
        "/login",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    update_response = client.post(
        "/home",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
            "address": "42 New Street",
            "hobbies": "Cycling, Reading",
        },
        follow_redirects=False,
    )

    assert update_response.status_code == 302

    users = storage.load_table("Users")
    matching_user = next(
        user for user in users if user.get("RowKey") == "ada.lovelace@whoiswho.dev"
    )
    assert matching_user["address"] == "42 New Street"
    assert matching_user["hobbies"] == "Cycling, Reading"


def test_profile_picture_upload_uses_web_safe_avatar_path(tmp_path, monkeypatch):
    app = _configure_app(monkeypatch, tmp_path)
    client = app.test_client()

    client.post(
        "/login",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
        },
        follow_redirects=False,
    )

    response = client.post(
        "/home",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
            "profile_picture": (io.BytesIO(b"fake-image-data"), "avatar.png"),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "/avatars/" in html

    users = storage.load_table("Users")
    matching_user = next(
        user for user in users if user.get("RowKey") == "ada.lovelace@whoiswho.dev"
    )
    assert matching_user["avatar_path"].startswith("avatars/")


def test_game_page_renders_for_authenticated_user(tmp_path, monkeypatch):
    app = _configure_app(monkeypatch, tmp_path)
    client = app.test_client()
    client.post(
        "/login",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
        },
        follow_redirects=False,
    )

    response = client.get("/game")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Get to know your colleagues" in html
    assert "Daily challenge" in html


def test_game_page_includes_enriched_employee_data_and_game_mounts(tmp_path, monkeypatch):
    app = _configure_app(monkeypatch, tmp_path)
    client = app.test_client()
    client.post(
        "/login",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
        },
        follow_redirects=False,
    )

    response = client.get("/game")
    html = response.get_data(as_text=True)

    for mode in ("photo-match", "two-truths", "hobby-guess", "guess-department"):
        assert f'data-game="{mode}"' in html

    employees = storage.load_table("Employees")
    assert employees, "expected seeded demo employees"
    for row in employees:
        assert row.get("hobbies"), f"{row.get('name')} is missing hobbies for the game data"
        two_truths = row.get("two_truths") or {}
        assert len(two_truths.get("statements", [])) == 3
        assert 0 <= two_truths.get("lie_index", -1) <= 2


def test_legacy_home_visit_game_redirects_to_game_page(tmp_path, monkeypatch):
    app = _configure_app(monkeypatch, tmp_path)
    client = app.test_client()
    client.post(
        "/login",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada.lovelace@whoiswho.dev",
        },
        follow_redirects=False,
    )

    response = client.get("/home/visit/game", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/game"


class _FakeMsalApp:
    """Stands in for msal.ConfidentialClientApplication so EntraProvider can be
    exercised without a real Entra ID tenant."""

    def __init__(self, token_result):
        self._token_result = token_result

    def initiate_auth_code_flow(self, scopes, redirect_uri):
        return {"auth_uri": "https://login.microsoftonline.com/fake-authorize", "state": "fake-state"}

    def acquire_token_by_auth_code_flow(self, flow, args):
        return self._token_result


def _entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups=""):
    app = _configure_app(
        monkeypatch,
        tmp_path,
        auth_mode="entra",
        secret_key="test-secret-key",
        allowed_groups=allowed_groups,
    )
    monkeypatch.setattr(auth.EntraProvider, "_msal_app", lambda self: _FakeMsalApp(token_result))

    return app.test_client(), storage


def test_entra_mode_never_accepts_the_mock_login_post(tmp_path, monkeypatch):
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result={})
    response = client.post(
        "/login",
        data={"first_name": "x", "last_name": "y", "email": "attacker@example.com"},
    )
    assert response.status_code == 404


def test_entra_mode_login_get_redirects_straight_to_microsoft(tmp_path, monkeypatch):
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result={})
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "https://login.microsoftonline.com/fake-authorize"


def test_entra_callback_without_a_pending_login_is_rejected(tmp_path, monkeypatch):
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result={})
    response = client.get("/auth/callback")
    assert response.status_code == 400


def test_entra_callback_rejects_a_failed_token_exchange(tmp_path, monkeypatch):
    token_result = {"error": "invalid_grant", "error_description": "AADSTS70008: expired code"}
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result)

    client.get("/login", follow_redirects=False)
    response = client.get("/auth/callback")
    assert response.status_code == 401


def test_entra_callback_rejects_group_overage(tmp_path, monkeypatch):
    token_result = {
        "id_token_claims": {
            "preferred_username": "someone@whoiswho.dev",
            "_claim_names": {"groups": "src1"},
        }
    }
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups="allowed-group-id")

    client.get("/login", follow_redirects=False)
    response = client.get("/auth/callback")
    assert response.status_code == 403


def test_entra_callback_rejects_user_outside_allowed_group(tmp_path, monkeypatch):
    token_result = {
        "id_token_claims": {
            "preferred_username": "someone@whoiswho.dev",
            "given_name": "Someone",
            "family_name": "Else",
            "groups": ["other-group-id"],
        }
    }
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups="allowed-group-id")

    client.get("/login", follow_redirects=False)
    response = client.get("/auth/callback")
    assert response.status_code == 403


def test_entra_callback_grants_access_and_creates_session_for_allowed_group(tmp_path, monkeypatch):
    token_result = {
        "id_token_claims": {
            "preferred_username": "grace.hopper@whoiswho.dev",
            "given_name": "Grace",
            "family_name": "Hopper",
            "groups": ["allowed-group-id"],
        }
    }
    client, storage_module = _entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups="allowed-group-id")

    client.get("/login", follow_redirects=False)
    response = client.get("/auth/callback", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/home")

    home_response = client.get("/home")
    assert home_response.status_code == 200

    users = storage_module.load_table("Users")
    matching_user = next(
        user for user in users if user.get("RowKey") == "grace.hopper@whoiswho.dev"
    )
    assert matching_user["first_name"] == "Grace"


def test_entra_callback_allows_any_tenant_user_when_no_groups_are_configured(tmp_path, monkeypatch):
    token_result = {
        "id_token_claims": {
            "preferred_username": "someone@whoiswho.dev",
            "given_name": "Someone",
            "family_name": "Else",
        }
    }
    client, _ = _entra_test_client(tmp_path, monkeypatch, token_result, allowed_groups="")

    client.get("/login", follow_redirects=False)
    response = client.get("/auth/callback", follow_redirects=False)
    assert response.status_code == 302
