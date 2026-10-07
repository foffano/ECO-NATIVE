"""Bounded job execution; interrupted work is never retried implicitly.

Jobs run in lanes, one worker each, so a slow kind of job never holds up the
others: a listing does not wait for minutes of image generation, and image
generation does not wait for a collection. Jobs in the same lane run in order.
"""
import logging
import os
import queue
import threading
from collections.abc import Callable

from fastapi import HTTPException

from backend.app.db.models import Job, JobStatus, now_iso
from backend.app.db.store import store
from backend.app.core.maintenance import maintenance_requested

logger = logging.getLogger(__name__)
# Serializes quota checks and admission across all job endpoints.
admission_lock = threading.RLock()


# Collection drives a browser and image generation waits on the image API for
# minutes; everything else (listing text) is quick.
LANES = ("collect", "images", "text")


def lane_for(job_type: str) -> str:
    if job_type == "collect_products":
        return "collect"
    if job_type in {"generate_images", "regenerate_image"}:
        return "images"
    return "text"


class JobQueue:
    def __init__(self, capacity: int = 32):
        self._queues = {lane: queue.Queue(maxsize=capacity) for lane in LANES}
        self._stop = threading.Event()
        self._threads: dict[str, threading.Thread] = {}

    def start(self):
        with admission_lock:
            if any(thread.is_alive() for thread in self._threads.values()):
                raise RuntimeError("Fila já iniciada")
            for lane_queue in self._queues.values():
                while True:
                    try:
                        lane_queue.get_nowait()
                        lane_queue.task_done()
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
            self._threads = {
                lane: threading.Thread(target=self._run, args=(lane_queue,), name=f"eco-jobs-{lane}", daemon=True)
                for lane, lane_queue in self._queues.items()
            }
            for thread in self._threads.values():
                thread.start()

    def submit(self, job: Job, action: Callable[[], Job]) -> Job:
        with admission_lock:
            if maintenance_requested():
                raise HTTPException(503, "Atualização do servidor em preparação. Tente novamente em instantes.")
            lane = lane_for(job.type)
            thread = self._threads.get(lane)
            if self._stop.is_set() or not thread or not thread.is_alive():
                raise HTTPException(503, "Servidor encerrando ou fila indisponível")
            lane_queue = self._queues[lane]
            if lane_queue.full():
                raise HTTPException(429, "Fila cheia. Aguarde os trabalhos atuais terminarem.")
            response = job.model_copy(deep=True)
            store.upsert_job(job)
            lane_queue.put_nowait((job, action))
            return response

    def _run(self, lane_queue: queue.Queue):
        while not self._stop.is_set():
            try:
                job, action = lane_queue.get(timeout=0.2)
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
                lane_queue.task_done()

    def stop(self):
        with admission_lock:
            self._stop.set()
        for thread in self._threads.values():
            thread.join(timeout=20)
        # Remaining jobs are reconciled at the next startup. No automatic retry
        # can duplicate downloads or paid AI requests after an abrupt shutdown.


# Per lane. A batch of products queues one job each; the image API rate limiter,
# not this bound, sets the actual pace.
job_queue = JobQueue(max(1, int(os.getenv("ECO_NATIVE_JOB_QUEUE_SIZE", "200"))))
