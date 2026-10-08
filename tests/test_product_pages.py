from fastapi.testclient import TestClient

from backend.app.db.models import Asset, Job, Listing, Product, ProductStatus, Project, StoreProfile
from backend.app.db.store import store


def client_for(*shops):
    """Client logged in to the first shop; every shop gets a login."""
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session
    create_initial_users(("admin", "password123"), [(f"shop{index}", "password123", shop.id) for index, shop in enumerate(shops)])
    clients = []
    for index, shop in enumerate(shops):
        client = TestClient(app)
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, f"shop{index}")))
        clients.append(client)
    return clients[0] if len(clients) == 1 else clients


def setup_catalog(count=25):
    shop = store.upsert_store_profile(StoreProfile(name="Eco Loja"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    for index in range(count):
        store.upsert_product(Product(
            project_id=project.id,
            name=f"Produto {index:02d}",
            created_at=f"2026-01-01T00:00:{index:02d}Z",
            listing=Listing(title="Título" if index % 2 else "", description="Desc" if index % 4 == 0 else ""),
            assets=[Asset(product_id="x", kind="cover_image", path="/capa.png")] if index % 3 == 0 else [],
            metadata={"sku": f"ECO-{index:03d}", "listed": index == 7,
                      "cost_events": [{"provider": "openrouter", "cost_usd": 0.5}, {"provider": "kie.ai", "cost_usd": 1}]},
        ))
    return shop, project


def test_cursor_pages_cover_the_catalog_once_newest_first():
    shop, _ = setup_catalog()
    client = client_for(shop)
    names, cursor = [], None
    while True:
        params = {"limit": 10, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/products/page", params=params).json()
        assert page["total"] == 25 and page["store_total"] == 25
        names += [item["name"] for item in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert names == [f"Produto {index:02d}" for index in range(24, -1, -1)]


def test_new_products_do_not_shift_the_next_page():
    shop, project = setup_catalog(5)
    client = client_for(shop)
    first = client.get("/api/products/page", params={"limit": 2}).json()
    store.upsert_product(Product(project_id=project.id, name="Novo", created_at="2026-02-01T00:00:00Z"))
    second = client.get("/api/products/page", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert [item["name"] for item in second["items"]] == ["Produto 02", "Produto 01"]


def test_filters_run_on_the_server():
    shop, _ = setup_catalog()
    client = client_for(shop)

    def names(**params):
        return [item["name"] for item in client.get("/api/products/page", params={"limit": 200, **params}).json()["items"]]

    assert names(q="eco-007") == ["Produto 07"]
    assert names(q="à venda", characteristic="listed") == ["Produto 07"]
    assert len(names(characteristic="with_image")) == 9
    assert len(names(characteristic="without_listing")) == 6
    assert names(status="exported") == []
    # Odd indexes have only a title, multiples of 4 only a description.
    assert len(names(characteristic="draft_listing")) == 12 + 7
    assert len(names(characteristic="without_ai_images")) == 25
    page = client.get("/api/products/page", params={"characteristic": "with_listing"}).json()
    assert page["total"] == 19 and page["with_title"] == 12
    assert client.get("/api/products/page", params={"characteristic": "nada"}).status_code == 422
    assert client.get("/api/products/page", params={"cursor": "%%%"}).status_code == 422


def test_publication_tabs_split_the_other_filters():
    shop, _ = setup_catalog()
    client = client_for(shop)
    listed = client.get("/api/products/page", params={"publication": "listed"}).json()
    assert [item["name"] for item in listed["items"]] == ["Produto 07"]
    assert listed["total"] == 1
    assert (listed["listed_total"], listed["not_listed_total"]) == (1, 24)
    pending = client.get("/api/products/page", params={"publication": "not_listed", "characteristic": "with_image"}).json()
    assert pending["total"] == 9
    assert (pending["listed_total"], pending["not_listed_total"]) == (0, 9)
    assert client.get("/api/products/page", params={"publication": "nada"}).status_code == 422


def test_stats_and_detail():
    shop, project = setup_catalog(4)
    other = store.upsert_store_profile(StoreProfile(name="Outra"))
    client, other_client = client_for(shop, other)
    stats = client.get("/api/products/stats").json()
    assert stats["total"] == 4
    assert stats["stages"] == {"collected": 4, "in_edit": 0, "ready": 0, "exported": 0, "listed": 0}
    # 0: description only; 1 and 3: title only; 2: nothing.
    assert stats["attention"]["without_listing"] == 1
    assert stats["attention"]["draft_listing"] == 3
    assert stats["attention"]["without_ai_images"] == 4
    assert stats["ai_cost_products"] == 4
    assert stats["ai_cost_by_provider"] == {"openrouter": 2.0, "kie": 4.0, "other": 0.0}
    assert stats["ai_cost_usd"] == 6.0

    product = store.snapshot().products[0]
    detail = client.get(f"/api/products/{product.id}").json()
    assert detail["metadata"]["cost_events"]

    assert other_client.get(f"/api/products/{product.id}").status_code == 404
    assert other_client.get("/api/products/page").json()["total"] == 0


def test_stats_stages_follow_the_board():
    shop, _ = setup_catalog(8)
    products = store.snapshot().products
    store.mutate(lambda state: [setattr(product, "status", ProductStatus.ready) for product in state.products[:3]])
    client = client_for(shop)
    stats = client.get("/api/products/stats").json()
    listed = sum(1 for product in products if product.metadata.get("listed"))
    assert stats["stages"]["listed"] == listed == 1
    assert sum(stats["stages"].values()) == 8


def test_jobs_since_returns_only_recent_changes():
    shop, project = setup_catalog(1)
    old = Job(type="listing", project_id=project.id)
    store.upsert_job(old)
    store.mutate(lambda state: setattr(state.jobs[0], "updated_at", "2026-01-01T00:00:00Z"))
    recent = store.upsert_job(Job(type="images", project_id=project.id))
    client = client_for(shop)
    assert {job["id"] for job in client.get("/api/jobs").json()} == {old.id, recent.id}
    since = client.get("/api/jobs", params={"since": "2026-06-01T00:00:00Z"}).json()
    assert [job["id"] for job in since] == [recent.id]


def test_batch_delete_is_one_write_and_skips_other_stores(monkeypatch):
    from backend.app.services import product_cleanup
    shop, project = setup_catalog(5)
    other = store.upsert_store_profile(StoreProfile(name="Outra"))
    other_project = store.upsert_project(Project(name="O", store_profile_id=other.id))
    foreign = store.upsert_product(Product(project_id=other_project.id, name="Alheio"))
    ours = [p for p in store.load().products if p.project_id == project.id]
    ours[0].source_url = "https://makerworld.com/pt/models/77"
    store.upsert_product(ours[0])
    store.upsert_job(Job(type="generate_listing", project_id=project.id, product_id=ours[0].id))
    purged, backups = [], []
    monkeypatch.setattr(product_cleanup, "purge_product_data", lambda product, **kw: purged.append(product.id) or {"errors": []})
    original_backup = store._backup_current_unlocked
    monkeypatch.setattr(store, "_backup_current_unlocked", lambda label="auto": backups.append(label) or original_backup(label))
    client = client_for(shop, other)[0]

    targets = [p.id for p in ours[:3]]
    response = client.post("/api/products/delete-batch", json={"product_ids": [*targets, foreign.id, "missing"]})

    assert response.status_code == 200
    assert sorted(response.json()["product_ids"]) == sorted(targets)
    assert sorted(purged) == sorted(targets)
    assert backups == ["before_shrink"]  # one safety backup for the whole batch
    state = store.load()
    remaining = {p.id for p in state.products}
    assert not remaining & set(targets) and foreign.id in remaining and len(remaining) == 3
    assert not state.jobs
    assert [entry.url for entry in state.blocked_source_urls] == ["https://makerworld.com/pt/models/77"]
    assert not state.pending_cleanups  # cleaned after the response


def test_single_delete_answers_before_cleaning_files(monkeypatch):
    from backend.app.services import product_cleanup
    shop, project = setup_catalog(2)
    purged = []
    monkeypatch.setattr(product_cleanup, "purge_product_data", lambda product, **kw: purged.append(product.id) or {"errors": []})
    client = client_for(shop)
    target = store.load().products[0].id
    assert client.delete(f"/api/products/{target}").json()["status"] == "deleted"
    assert purged == [target]
    assert client.delete(f"/api/products/{target}").status_code == 404
