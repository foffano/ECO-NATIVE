from fastapi.testclient import TestClient

from backend.app.db.models import StoreProfile
from backend.app.db.store import store
from backend.app.services.auth import create_initial_users, update_store_access


def setup_stores(tmp_path):
    from backend.app.main import app
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"png")
    first = store.upsert_store_profile(StoreProfile(name="Luma", logo_path=str(logo)))
    second = store.upsert_store_profile(StoreProfile(name="Toffa"))
    hidden = store.upsert_store_profile(StoreProfile(name="Desativada"))
    create_initial_users(("admin", "admin-pass1"), [
        ("luma", "luma-pass1", first.id), ("toffa", "toffa-pass1", second.id), ("off", "off-pass11", hidden.id),
    ])
    update_store_access(hidden.id, enabled=False, quotas={})
    return TestClient(app), first, second


def test_login_page_lists_enabled_stores_without_their_logins(tmp_path):
    client, first, second = setup_stores(tmp_path)
    status = client.get("/api/auth/status").json()
    assert [item["name"] for item in status["stores"]] == ["Luma", "Toffa"]
    assert "luma" not in str(status["stores"])
    assert status["stores"][1]["photo_version"] is None
    assert client.get(f"/api/auth/stores/{first.id}/photo").content == b"png"  # before login
    assert client.get(f"/api/auth/stores/{second.id}/photo").status_code == 404


def test_store_signs_in_with_its_card_and_password(tmp_path):
    client, first, second = setup_stores(tmp_path)
    assert client.post("/api/auth/login", json={"store_profile_id": first.id, "password": "toffa-pass1"}).status_code == 401
    response = client.post("/api/auth/login", json={"store_profile_id": second.id, "password": "toffa-pass1"})
    assert response.status_code == 200 and response.json()["store"]["id"] == second.id
    admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass1"})
    assert admin.json()["is_admin"] is True


def test_wrong_passwords_lock_that_store_for_a_while(tmp_path):
    client, first, second = setup_stores(tmp_path)
    for _ in range(8):
        assert client.post("/api/auth/login", json={"store_profile_id": first.id, "password": "errada123"}).status_code == 401
    locked = client.post("/api/auth/login", json={"store_profile_id": first.id, "password": "luma-pass1"})
    assert locked.status_code == 429
    other = client.post("/api/auth/login", json={"store_profile_id": second.id, "password": "toffa-pass1"})
    assert other.status_code == 200  # only the attacked store is locked


def test_each_store_keeps_its_own_theme(tmp_path):
    from backend.app.services.auth import AuthenticatedStore, create_session
    client, first, second = setup_stores(tmp_path)
    client.cookies.set("eco_native_session", create_session(AuthenticatedStore(first.id, "luma")))

    saved = client.put(f"/api/store-profiles/{first.id}/theme", json={"id": "ocean"})
    assert saved.status_code == 200 and saved.json()["ui_theme"] == {"id": "ocean", "accent": None}
    assert client.put(f"/api/store-profiles/{first.id}/theme", json={"id": "custom", "accent": "azul"}).status_code == 422
    assert client.put(f"/api/store-profiles/{second.id}/theme", json={"id": "rose"}).status_code == 404  # other store

    # Saving the profile editor never brings back an older theme.
    profile = client.get("/api/store-profiles").json()[0]
    client.patch(f"/api/store-profiles/{first.id}", json={**profile, "niche": "Casa", "ui_theme": None})
    stores = {item["id"]: item for item in TestClient(client.app).get("/api/auth/status").json()["stores"]}
    assert stores[first.id]["ui_theme"] == {"id": "ocean", "accent": None}
    assert stores[second.id]["ui_theme"] is None
