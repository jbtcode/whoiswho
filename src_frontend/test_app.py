import importlib
import io
import os


def test_profile_update_is_persisted_to_json(tmp_path, monkeypatch):
    monkeypatch.setenv("WHOISWHO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WHOISWHO_AUTH_MODE", "mock")

    import config
    import storage
    import app as app_module

    config = importlib.reload(config)
    storage = importlib.reload(storage)
    app_module = importlib.reload(app_module)

    storage.initialize_tables()
    client = app_module.app.test_client()

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
    monkeypatch.setenv("WHOISWHO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WHOISWHO_AVATAR_DIR", str(tmp_path / "avatars"))

    import storage
    import app as app_module

    storage = importlib.reload(storage)
    app_module = importlib.reload(app_module)

    client = app_module.app.test_client()

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
    assert "/uploads/" in html

    users = storage.load_table("Users")
    matching_user = next(
        user for user in users if user.get("RowKey") == "ada.lovelace@whoiswho.dev"
    )
    assert matching_user["avatar_path"].startswith("avatars/")
