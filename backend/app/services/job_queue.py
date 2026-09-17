"""Bounded, single-worker execution; interrupted work is never retried implicitly."""
import logging
import os
import queue
import threading
from collections.abc import Callable

from fastapi import HTTPException

from backend.app.db.models import Job, JobStatus, now_iso
from backend.app.db.store import store

logger = logging.getLogger(__name__)
# Serializes quota checks and admission across all job endpoints.
admission_lock = threading.RLock()


class JobQueue:
    def __init__(self, capacity: int = 32):
        self._queue = queue.Queue(maxsize=capacity)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        with admission_lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("Fila já iniciada")
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
            def recover(state):
                for job in state.jobs:
                    if job.status in {JobStatus.queued, JobStatus.running}:
                        job.status = JobStatus.failed
                        job.message = "Interrompido pelo reinício do servidor. Revise o resultado antes de tentar novamente."
                        job.logs.append(job.message)
                        job.updated_at = now_iso()
            store.mutate(recover)
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="eco-jobs", daemon=True)
            self._thread.start()

    def submit(self, job: Job, action: Callable[[], Job]) -> Job:
        with admission_lock:
            if self._stop.is_set() or not self._thread or not self._thread.is_alive():
                raise HTTPException(503, "Servidor encerrando ou fila indisponível")
            if self._queue.full():
                raise HTTPException(429, "Fila cheia. Aguarde os trabalhos atuais terminarem.")
            response = job.model_copy(deep=True)
            store.upsert_job(job)
            self._queue.put_nowait((job, action))
            return response

    def _run(self):
        while not self._stop.is_set():
            try:
                job, action = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                state = store.load()
                project = next((project for project in state.projects if project.id == job.project_id), None)
                if project is None:
                    raise RuntimeError("Projeto removido antes da execução")
                if project.store_profile_id:
                    from backend.app.services.usage_limits import enforce_quota
                    # Cost/disabled access can change while a job waits. Operation
                    # quotas were already reserved by the queued record.
                    enforce_quota(state, project.store_profile_id, "ai_cost_usd_monthly")
                if job.product_id and not any(product.id == job.product_id for product in state.products):
                    raise RuntimeError("Produto removido antes da execução")
                action()
            except Exception as exc:
                logger.exception("Job %s failed", job.id)
                job.status = JobStatus.failed
                job.message = str(exc)
                job.logs.append(f"{type(exc).__name__}: {exc}")
                store.upsert_job(job)
            finally:
                self._queue.task_done()

    def stop(self):
        with admission_lock:
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=20)
        # Remaining jobs are reconciled at the next startup. No automatic retry
        # can duplicate downloads or paid AI requests after an abrupt shutdown.


job_queue = JobQueue(max(1, int(os.getenv("ECO_NATIVE_JOB_QUEUE_SIZE", "32"))))
