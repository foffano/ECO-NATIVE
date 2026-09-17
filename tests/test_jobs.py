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
