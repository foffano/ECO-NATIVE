import json
import os

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.db.models import Asset, Product, Project, StoreProfile
from backend.app.db.store import store


def setup_product(tmp_path, *, size=(1200, 900)):
    cover = tmp_path / "cover.png"
    Image.new("RGB", size, (200, 40, 40)).save(cover)
    shop = store.upsert_store_profile(StoreProfile(name="Eco Loja"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    product = store.upsert_product(Product(
        project_id=project.id,
        name="Organizador",
        assets=[Asset(product_id="x", kind="cover_image", path=str(cover))],
        metadata={"sku": "ECO-001", "image_prompts": {"a": "long prompt"}, "listing_prompt": "prompt", "cost_events": [{"cost_usd": 0.1}]},
    ))
    return shop, product


def client_for(shop):
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session
    create_initial_users(("admin", "password123"), [("shop", "password123", shop.id)])
    client = TestClient(app)
    client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop")))
    return client


def test_snapshot_is_cached_until_the_file_changes():
    store.upsert_project(Project(name="Primeiro"))
    first = store.snapshot()
    assert store.snapshot() is first

    # A write made outside this store (maintenance script, backup restore).
    data = json.loads(store.path.read_text(encoding="utf-8"))
    data["projects"][0]["name"] = "Editado fora"
    store.path.write_text(json.dumps(data), encoding="utf-8")
    stat = store.path.stat()
    os.utime(store.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert store.snapshot().projects[0].name == "Editado fora"


def test_load_returns_copies_that_do_not_leak_into_the_cache():
    store.upsert_project(Project(name="Original"))
    state = store.load()
    state.projects[0].name = "Rascunho"
    assert store.snapshot().projects[0].name == "Original"


def test_saved_objects_stay_detached_from_the_cache():
    project = store.upsert_project(Project(name="Salvo"))
    project.name = "Alterado depois de salvar"
    assert store.snapshot().projects[0].name == "Salvo"


def test_find_asset_follows_writes(tmp_path):
    _, product = setup_product(tmp_path)
    asset_id = product.assets[0].id
    assert store.find_asset(asset_id)[0].id == product.id

    store.mutate(lambda state: state.products[0].assets.clear())
    assert store.find_asset(asset_id) is None


def test_product_list_omits_reference_prompts_but_keeps_costs(tmp_path):
    shop, _ = setup_product(tmp_path)
    [listed] = client_for(shop).get("/api/products").json()
    assert "image_prompts" not in listed["metadata"]
    assert "listing_prompt" not in listed["metadata"]
    assert listed["metadata"]["cost_events"] == [{"cost_usd": 0.1}]
    assert listed["assets"][0]["path"] == "cover.png"
    # The stored product keeps everything.
    assert store.snapshot().products[0].metadata["image_prompts"] == {"a": "long prompt"}


def test_asset_thumbnail_is_resized_webp_and_revalidates(tmp_path):
    shop, product = setup_product(tmp_path)
    client = client_for(shop)
    asset_id = product.assets[0].id

    response = client.get(f"/api/assets/{asset_id}?v=1&w=160")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert "max-age" in response.headers["cache-control"]
    from io import BytesIO
    assert max(Image.open(BytesIO(response.content)).size) == 160

    cached = client.get(f"/api/assets/{asset_id}?w=160", headers={"If-None-Match": response.headers["etag"]})
    assert cached.status_code == 304

    original = client.get(f"/api/assets/{asset_id}")
    assert original.headers["content-type"] == "image/png"
    assert original.headers["cache-control"] == "private, no-cache"


def test_assets_of_other_stores_stay_hidden(tmp_path):
    _, product = setup_product(tmp_path)
    other = store.upsert_store_profile(StoreProfile(name="Outra loja"))
    response = client_for(other).get(f"/api/assets/{product.assets[0].id}?w=160")
    assert response.status_code == 404
