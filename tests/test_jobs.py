import threading
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.db.models import Job, JobStatus, Project, StoreProfile
from backend.app.db.store import store
from backend.app.services.job_queue import JobQueue


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while not predicate():
        assert time.monotonic() < deadline, "worker did not finish"
        time.sleep(0.02)


def test_queue_capacity_recovery_and_failure():
    project = store.upsert_project(Project(name="test"))
    interrupted = Job(type="test", project_id=project.id, status=JobStatus.running)
    store.upsert_job(interrupted)
    worker = JobQueue(capacity=1)
    entered, release = threading.Event(), threading.Event()
    worker.start()
    try:
        assert store.load().jobs[0].status == JobStatus.failed
        def slow():
            entered.set()
            release.wait(3)
            raise ValueError("worker error")
        first = Job(type="test", project_id=project.id)
        assert worker.submit(first, slow).status == JobStatus.queued
        assert entered.wait(2)
        worker.submit(Job(type="test", project_id=project.id), lambda: None)
        with pytest.raises(HTTPException) as exc:
            worker.submit(Job(type="test", project_id=project.id), lambda: None)
        assert exc.value.status_code == 429
        release.set()
        wait_for(lambda: any(j.id == first.id and j.status == JobStatus.failed for j in store.load().jobs))
    finally:
        release.set()
        worker.stop()


def test_api_accepts_without_waiting_and_scopes_job_reads():
    from backend.app.main import app
    from backend.app.services.auth import create_initial_users, create_session
    from backend.app.services.auth import AuthenticatedStore
    shop = store.upsert_store_profile(StoreProfile(name="A"))
    other = store.upsert_store_profile(StoreProfile(name="B"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    create_initial_users(("admin", "password123"), [("shop-a", "password123", shop.id), ("shop-b", "password123", other.id)])
    entered, release = threading.Event(), threading.Event()
    def slow(job, payload):
        entered.set()
        release.wait(3)
        job.status = JobStatus.completed
        return store.upsert_job(job)
    with patch("backend.app.api.routes_jobs.run_collect_job", side_effect=slow), TestClient(app) as client:
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop-a")))
        try:
            response = client.post("/api/jobs/collect", json={"project_id": project.id})
            assert response.status_code == 202
            assert response.json()["status"] == "queued"
            assert entered.wait(2)
            job_id = response.json()["id"]
            assert client.get(f"/api/jobs/{job_id}").status_code == 200
            client.cookies.set("eco_native_session", create_session(AuthenticatedStore(other.id, "shop-b")))
            assert client.get(f"/api/jobs/{job_id}").status_code == 404
        finally:
            release.set()


def test_maintenance_blocks_new_work_and_reports_idle_state():
    from backend.app.core.paths import DATA_DIR
    from backend.app.main import app

    marker = DATA_DIR / ".maintenance"
    marker.touch()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["maintenance"] is True
        assert health.json()["active_jobs"] == 0
        response = client.post("/api/jobs/collect", json={"project_id": "missing"})
        assert response.status_code == 503


def test_lanes_run_listing_while_images_are_generating():
    project = store.upsert_project(Project(name="lanes"))
    worker = JobQueue(capacity=4)
    entered, release, listed = threading.Event(), threading.Event(), threading.Event()
    worker.start()
    try:
        def slow_images():
            entered.set()
            release.wait(3)
        worker.submit(Job(type="generate_images", project_id=project.id), slow_images)
        assert entered.wait(2)
        worker.submit(Job(type="generate_listing", project_id=project.id), listed.set)
        assert listed.wait(2), "listing waited behind image generation"
    finally:
        release.set()
        worker.stop()


def test_image_job_keeps_edits_saved_while_it_runs():
    from backend.app.db.models import Asset, Listing, Product
    from backend.app.services import job_runner

    project = store.upsert_project(Project(name="merge"))
    product = store.upsert_product(Product(project_id=project.id, name="Vaso"))

    def fake_generate(working, *, on_asset, **_):
        # The user edits the listing while the job is generating.
        current = next(item for item in store.load().products if item.id == working.id)
        current.listing = Listing(title="Editado durante a geração")
        current.name = "Vaso editado"
        store.upsert_product(current)
        asset = Asset(product_id=working.id, kind="generated_studio_classic", path="a.png")
        on_asset(asset)
        return [asset]

    job = Job(type="generate_images", project_id=project.id, product_id=product.id)
    with patch.object(job_runner, "generate_studio_images", side_effect=fake_generate):
        result = job_runner.run_image_job(job, product)

    assert result.status == JobStatus.completed, result.logs
    saved = next(item for item in store.load().products if item.id == product.id)
    assert saved.listing.title == "Editado durante a geração"
    assert saved.name == "Vaso editado"
    assert [asset.kind for asset in saved.assets] == ["generated_studio_classic"]
    assert saved.metadata["generated_image_count"] == 1


def test_job_does_not_bring_back_a_deleted_product():
    from backend.app.db.models import Asset, Product
    from backend.app.services import job_runner

    project = store.upsert_project(Project(name="deleted"))
    product = store.upsert_product(Product(project_id=project.id, name="Some"))

    def fake_generate(working, *, on_asset, **_):
        store.mutate(lambda state: setattr(state, "products", []), allow_product_shrink=True)
        asset = Asset(product_id=working.id, kind="generated_studio_classic", path="a.png")
        on_asset(asset)
        return [asset]

    job = Job(type="generate_images", project_id=project.id, product_id=product.id)
    with patch.object(job_runner, "generate_studio_images", side_effect=fake_generate):
        job_runner.run_image_job(job, product)

    assert not store.load().products


def test_merge_keeps_cost_events_from_concurrent_jobs():
    from backend.app.db.models import Product
    from backend.app.db.product_merge import merge_product
    from backend.app.services.cost_tracker import add_cost_event

    base = Product(project_id="p", name="x")
    mine = base.model_copy(deep=True)
    theirs = base.model_copy(deep=True)
    add_cost_event(mine, provider="Kie", action="img", model="m", cost_usd=0.5, source="s")
    add_cost_event(theirs, provider="OpenRouter", action="txt", model="m", cost_usd=0.25, source="s")
    merged = merge_product(base, mine, theirs)
    assert sorted(event["provider"] for event in merged.metadata["cost_events"]) == ["Kie", "OpenRouter"]
    assert merged.metadata["cost_total_usd"] == 0.75


def test_same_generation_for_a_product_is_not_queued_twice():
    from backend.app.db.models import Product
    from backend.app.main import app
    from backend.app.services.auth import AuthenticatedStore, create_initial_users, create_session

    shop = store.upsert_store_profile(StoreProfile(name="A"))
    project = store.upsert_project(Project(name="P", store_profile_id=shop.id))
    product = store.upsert_product(Product(project_id=project.id, name="Vaso"))
    create_initial_users(("admin", "password123"), [("shop-a", "password123", shop.id)])
    entered, release = threading.Event(), threading.Event()

    def slow(job, *_):
        entered.set()
        release.wait(3)
        job.status = JobStatus.completed
        return store.upsert_job(job)

    with patch("backend.app.api.routes_jobs.run_listing_job", side_effect=slow), TestClient(app) as client:
        client.cookies.set("eco_native_session", create_session(AuthenticatedStore(shop.id, "shop-a")))
        try:
            first = client.post("/api/jobs/listing", json={"product_id": product.id})
            assert first.status_code == 202
            assert first.json()["metadata"]["product_name"] == "Vaso"
            assert entered.wait(2)
            assert client.post("/api/jobs/listing", json={"product_id": product.id}).status_code == 409
        finally:
            release.set()
