import json
import sqlite3

import pytest

from backend.app.db.models import Asset, Job, Product, Project, StudioState
from backend.app.db.store import COLLECTIONS, StudioStore


@pytest.fixture
def studio(tmp_path):
    instance = StudioStore(tmp_path / "studio.db", legacy_json_path=tmp_path / "studio.json")
    yield instance
    instance.close()


def reopen(studio: StudioStore) -> StudioStore:
    studio.close()
    return StudioStore(studio.path, legacy_json_path=None)


def count_writes(studio: StudioStore) -> list[str]:
    statements: list[str] = []
    studio.snapshot()
    studio._conn.set_trace_callback(
        lambda sql: statements.append(sql) if sql.startswith(("INSERT", "UPDATE", "DELETE")) else None
    )
    return statements


def test_every_state_list_has_a_table():
    assert {collection.attr for collection in COLLECTIONS} == set(StudioState.model_fields)


def test_first_open_imports_studio_json_and_leaves_it_untouched(tmp_path):
    legacy = tmp_path / "studio.json"
    product = Product(project_id="p", name="Legado", assets=[Asset(product_id="p", kind="cover_image", path="/x/capa.png")])
    payload = json.loads(StudioState(projects=[Project(id="p", name="P")], products=[product]).model_dump_json())
    payload["products"][0]["status"] = "scraped"
    legacy.write_text(json.dumps(payload))
    original = legacy.read_bytes()

    studio = StudioStore(tmp_path / "studio.db", legacy_json_path=legacy)
    state = studio.load()
    assert [item.name for item in state.products] == ["Legado"]
    assert state.products[0].status == "collected"
    assert legacy.read_bytes() == original
    with sqlite3.connect(studio.path) as conn:
        assert conn.execute("SELECT product_id, kind FROM assets").fetchall() == [(product.id, "cover_image")]
        assert conn.execute("SELECT project_id, status FROM products").fetchall() == [("p", "collected")]
    studio.close()

    # Already migrated: later changes to the JSON file are not imported again.
    legacy.write_text(json.dumps({"products": []}))
    again = StudioStore(tmp_path / "studio.db", legacy_json_path=legacy)
    assert len(again.load().products) == 1
    again.close()


def test_failed_import_leaves_no_half_migrated_database(tmp_path):
    (tmp_path / "studio.json").write_text('{"products": [{"name": "sem projeto"}]}')
    studio = StudioStore(tmp_path / "studio.db", legacy_json_path=tmp_path / "studio.json")
    with pytest.raises(ValueError):
        studio.load()
    with sqlite3.connect(tmp_path / "studio.db") as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        assert conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == []


def test_mutate_writes_only_the_rows_that_changed(studio):
    studio.replace(StudioState(products=[Product(project_id="p", name=f"P{index}") for index in range(50)]))
    writes = count_writes(studio)

    studio.mutate(lambda state: setattr(state.products[10], "name", "Renomeado"))

    product_writes = [sql for sql in writes if "products" in sql]
    assert len(product_writes) == 1
    assert reopen(studio).load().products[10].name == "Renomeado"


def test_upsert_writes_one_row_and_moves_it_to_the_end(studio):
    studio.replace(StudioState(projects=[Project(name=name) for name in ("A", "B", "C")]))
    project = studio.load().projects[0]
    writes = count_writes(studio)

    project.name = "A2"
    studio.upsert_project(project)

    assert len([sql for sql in writes if "projects" in sql]) == 1
    assert [item.name for item in studio.snapshot().projects] == ["B", "C", "A2"]
    assert [item.name for item in reopen(studio).load().projects] == ["B", "C", "A2"]


def test_order_survives_inserts_in_the_middle(studio):
    studio.replace(StudioState(projects=[Project(name=name) for name in ("A", "C")]))
    studio.mutate(lambda state: state.projects.insert(1, Project(name="B")))
    assert [item.name for item in studio.snapshot().projects] == ["A", "B", "C"]
    assert [item.name for item in reopen(studio).load().projects] == ["A", "B", "C"]


def test_products_and_jobs_are_only_removed_on_purpose(studio, tmp_path, monkeypatch):
    from backend.app.db import store as store_module

    monkeypatch.setattr(store_module, "STORE_SNAPSHOTS_DIR", tmp_path / "snapshots")
    first, second = Product(project_id="p", name="1"), Product(project_id="p", name="2")
    studio.replace(StudioState(products=[first, second], jobs=[Job(type="collect")]))

    def drop_everything(state):
        state.products.clear()
        state.jobs.clear()

    studio.mutate(drop_everything)
    assert len(studio.snapshot().products) == 2
    assert len(studio.snapshot().jobs) == 1

    studio.mutate(lambda state: state.products.pop(0), allow_product_shrink=True)
    assert [item.id for item in reopen(studio).load().products] == [second.id]
    [snapshot] = (tmp_path / "snapshots").glob("studio.before_shrink_*.json")
    assert len(json.loads(snapshot.read_text())["products"]) == 2


def test_failed_mutation_changes_nothing(studio):
    studio.replace(StudioState(projects=[Project(name="A")]))

    def fail(state):
        state.projects[0].name = "B"
        raise RuntimeError("falhou")

    with pytest.raises(RuntimeError):
        studio.mutate(fail)
    assert studio.snapshot().projects[0].name == "A"
    assert reopen(studio).load().projects[0].name == "A"


def test_deleting_a_product_removes_its_assets(studio):
    product = Product(project_id="p", name="P", assets=[Asset(product_id="p", kind="cover_image", path="/capa.png")])
    studio.replace(StudioState(products=[product]))
    studio.mutate(lambda state: state.products.clear(), allow_product_shrink=True)
    with sqlite3.connect(studio.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
