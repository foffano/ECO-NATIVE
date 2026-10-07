from fastapi.testclient import TestClient

from backend.app.db.models import (
    Asset,
    BlockedSourceUrl,
    Job,
    Product,
    Project,
    StoreProfile,
)
from backend.app.db.store import store
from backend.app.services.product_paths import product_assets_dir
from backend.app.services.store_catalog import unify_store_projects


def _product_with_file(project: Project, sku: str) -> Product:
    folder = product_assets_dir(project.id, sku)
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / f"{sku}_capa_produto.jpg"
    image.write_bytes(b"jpg")
    product = Product(project_id=project.id, name=sku, metadata={"sku": sku, "image_versions": {"x": [str(image)]}})
    product.assets.append(Asset(product_id=product.id, kind="cover_image", path=str(image)))
    return store.upsert_product(product)


def test_unify_merges_a_stores_projects_into_one_catalog():
    shop = store.upsert_store_profile(StoreProfile(name="Luma"))
    other_shop = store.upsert_store_profile(StoreProfile(name="Outra"))
    big = store.upsert_project(Project(name="Grande", store_profile_id=shop.id))
    small = store.upsert_project(Project(name="Pequeno", store_profile_id=shop.id))
    empty = store.upsert_project(Project(name="Vazio", store_profile_id=shop.id))
    untouched = store.upsert_project(Project(name="Só um", store_profile_id=other_shop.id))
    _product_with_file(big, "LUMA-A-0001")
    _product_with_file(big, "LUMA-B-0002")
    moved = _product_with_file(small, "LUMA-C-0003")
    store.mutate(lambda state: state.blocked_source_urls.extend([
        BlockedSourceUrl(project_id=big.id, url="https://a"),
        BlockedSourceUrl(project_id=small.id, url="https://a"),
        BlockedSourceUrl(project_id=small.id, url="https://b"),
    ]))
    store.upsert_job(Job(type="generate_images", project_id=small.id, product_id=moved.id))

    assert unify_store_projects() == 1

    state = store.load()
    assert {project.id for project in state.projects} == {big.id, untouched.id}
    assert all(product.project_id == big.id for product in state.products)
    product = next(item for item in state.products if item.id == moved.id)
    new_path = product_assets_dir(big.id, "LUMA-C-0003") / "LUMA-C-0003_capa_produto.jpg"
    assert product.assets[0].path == str(new_path)
    assert product.metadata["image_versions"]["x"] == [str(new_path)]
    assert new_path.read_bytes() == b"jpg"
    assert not product_assets_dir(small.id, "LUMA-C-0003").exists()
    assert sorted(entry.url for entry in state.blocked_source_urls) == ["https://a", "https://b"]
    assert all(entry.project_id == big.id for entry in state.blocked_source_urls)
    assert state.jobs[0].project_id == big.id
    assert empty.id not in {project.id for project in state.projects}
    # Running it again changes nothing.
    assert unify_store_projects() == 0


def test_products_and_collections_use_the_store_catalog_without_projects():
    from unittest.mock import patch

    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session

    shop = store.upsert_store_profile(StoreProfile(name="Nova"))
    create_initial_users(("admin", "password123"), [("nova", "password123", shop.id)])
    with patch("backend.app.api.routes_jobs.run_collect_job"), TestClient(app) as client:
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "nova")))
        created = client.post("/api/products", json={"name": "Vaso"})
        assert created.status_code == 200
        collect = client.post("/api/jobs/collect", json={"keyword": "vaso"})
        assert collect.status_code == 202
        assert client.get("/api/projects").status_code in {404, 405}
        assert client.get("/api/blocked-urls").json() == []

    catalogs = [project for project in store.load().projects if project.store_profile_id == shop.id]
    assert len(catalogs) == 1
    assert created.json()["project_id"] == catalogs[0].id
    assert collect.json()["project_id"] == catalogs[0].id
