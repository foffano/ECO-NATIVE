from backend.app.db.models import Product, Project
from backend.app.db.store import store
from backend.app.services import product_cleanup
from backend.app.services.product_paths import product_dir_for


def queue(*products):
    store.mutate(lambda state: product_cleanup.queue_product_cleanup(state, list(products)))


def test_queued_cleanup_survives_a_restart_and_removes_the_folder():
    project = store.upsert_project(Project(name="P"))
    gone = Product(project_id=project.id, name="Gone", metadata={"sku": "ECO-GONE-0001"})
    folder = product_dir_for(gone)
    folder.mkdir(parents=True)
    (folder / "capa.jpg").write_bytes(b"x")
    queue(gone)  # recorded, then the server stopped before cleaning

    product_cleanup.run_pending_cleanups()  # as on startup

    assert not folder.exists()
    assert not store.load().pending_cleanups


def test_failed_cleanup_stays_queued_for_the_next_run(monkeypatch):
    queue(Product(project_id="p", name="Gone"))
    monkeypatch.setattr(product_cleanup, "purge_product_data", lambda product, **kw: {"errors": ["r2: sem conexão"]})
    product_cleanup.run_pending_cleanups()
    [entry] = store.load().pending_cleanups
    assert entry.attempts == 1 and "sem conexão" in entry.last_error

    monkeypatch.setattr(product_cleanup, "purge_product_data", lambda product, **kw: {"errors": []})
    product_cleanup.run_pending_cleanups()
    assert not store.load().pending_cleanups


def test_cleanup_never_touches_files_in_use():
    project = store.upsert_project(Project(name="P"))
    restored = store.upsert_product(Product(project_id=project.id, name="Back", metadata={"sku": "ECO-BACK-0001"}))
    reused_sku = Product(project_id=project.id, name="Old", metadata={"sku": "ECO-SAME-0001"})
    store.upsert_product(Product(project_id=project.id, name="New", metadata={"sku": "ECO-SAME-0001"}))
    for product in (restored, reused_sku):
        product_dir_for(product).mkdir(parents=True, exist_ok=True)
    queue(restored, reused_sku)

    product_cleanup.run_pending_cleanups()

    assert product_dir_for(restored).exists()  # brought back by a restore
    assert product_dir_for(reused_sku).exists()  # the new product now owns this folder
    assert not store.load().pending_cleanups
