from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.app.db.models import Job
from backend.app.db.store import store
from backend.app.services.job_runner import run_collect_job, run_image_job, run_listing_job, run_regenerate_image_job
from backend.app.services.makerworld_session import (
    close_login_session,
    get_login_session_status,
    get_login_session_frame,
    open_login_session,
    send_login_session_input,
)
from backend.app.services.authorization import current_store_id, require_product, require_project, store_project_ids
from backend.app.services.usage_limits import enforce_quota
from backend.app.services.job_queue import admission_lock, job_queue

router = APIRouter()


class CollectRequest(BaseModel):
    project_id: str
    store_profile_id: str | None = None
    keyword: str = ""
    urls: list[str] = []
    limit: int = 10
    scrolls: int = 8
    visible_browser: bool = True
    ai_profile: str = "Padrao"
    ai_profile_id: str | None = None
    skip_ai_curation: bool = False


class ProductJobRequest(BaseModel):
    product_id: str
    color_variations: list[str] = Field(default_factory=list)
    generate_base_images: bool = True


class RegenerateImageRequest(BaseModel):
    product_id: str
    prompt_key: str
    extra_prompt: str = ""


class RemoteBrowserInput(BaseModel):
    type: Literal["click", "move", "wheel", "text", "key", "select_page"]
    page_id: str | None = Field(default=None, max_length=32)
    x: float | None = Field(default=None, ge=0, le=1280)
    y: float | None = Field(default=None, ge=0, le=720)
    delta_x: float | None = Field(default=None, ge=-5000, le=5000)
    delta_y: float | None = Field(default=None, ge=-5000, le=5000)
    button: Literal["left", "right", "middle"] = "left"
    text: str | None = Field(default=None, max_length=2000)
    key: str | None = Field(default=None, max_length=80)


def _makerworld_status(request: Request) -> dict[str, Any]:
    status = get_login_session_status(current_store_id(request)).__dict__
    status["interactive_login_available"] = True
    status["remote_control"] = True
    return status


@router.get("")
def list_jobs(request: Request) -> list[Job]:
    state = store.load()
    allowed = store_project_ids(state, current_store_id(request))
    return sorted((job for job in state.jobs if job.project_id in allowed), key=lambda j: j.created_at, reverse=True)


@router.get("/makerworld-login")
def makerworld_login_status(request: Request) -> dict[str, Any]:
    return _makerworld_status(request)


@router.post("/makerworld-login")
def open_makerworld_login(request: Request) -> dict[str, Any]:
    result = open_login_session(current_store_id(request)).__dict__
    result["interactive_login_available"] = True
    result["remote_control"] = True
    return result


@router.post("/makerworld-login/close")
def close_makerworld_login(request: Request) -> dict[str, Any]:
    result = close_login_session(current_store_id(request)).__dict__
    result["interactive_login_available"] = True
    result["remote_control"] = True
    return result


@router.get("/makerworld-login/frame")
def makerworld_login_frame(request: Request) -> Response:
    frame = get_login_session_frame(current_store_id(request))
    if not frame:
        raise HTTPException(status_code=425, detail="Aguardando o primeiro quadro do navegador")
    return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store, max-age=0"})


@router.post("/makerworld-login/input", status_code=204)
def makerworld_login_input(payload: RemoteBrowserInput, request: Request) -> None:
    try:
        send_login_session_input(current_store_id(request), payload.model_dump(exclude_none=True))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/collect", status_code=202)
def collect_products(payload: CollectRequest, request: Request) -> Job:
    with admission_lock:
        state = store.load()
        store_id = current_store_id(request)
        enforce_quota(state, store_id, "collect_monthly")
        enforce_quota(state, store_id, "ai_cost_usd_monthly")
        project = require_project(state, payload.project_id, store_id)
        payload.store_profile_id = project.store_profile_id
        job = Job(type="collect_products", project_id=payload.project_id)
        return job_queue.submit(job, lambda: run_collect_job(job, payload))


@router.post("/listing", status_code=202)
def generate_listing(payload: ProductJobRequest, request: Request) -> Job:
    with admission_lock:
        state = store.load()
        store_id = current_store_id(request)
        enforce_quota(state, store_id, "listing_monthly")
        enforce_quota(state, store_id, "ai_cost_usd_monthly")
        product = require_product(state, payload.product_id, store_id)

        job = Job(type="generate_listing", project_id=product.project_id, product_id=product.id)
        return job_queue.submit(job, lambda: run_listing_job(job, product))


@router.post("/images", status_code=202)
def generate_images(payload: ProductJobRequest, request: Request) -> Job:
    with admission_lock:
        state = store.load()
        store_id = current_store_id(request)
        enforce_quota(state, store_id, "image_monthly")
        enforce_quota(state, store_id, "ai_cost_usd_monthly")
        product = require_product(state, payload.product_id, store_id)

        job = Job(type="generate_images", project_id=product.project_id, product_id=product.id)
        return job_queue.submit(job, lambda: run_image_job(job, product, payload.color_variations, payload.generate_base_images))


@router.post("/image-regenerate", status_code=202)
def regenerate_image(payload: RegenerateImageRequest, request: Request) -> Job:
    with admission_lock:
        state = store.load()
        store_id = current_store_id(request)
        enforce_quota(state, store_id, "image_monthly")
        enforce_quota(state, store_id, "ai_cost_usd_monthly")
        product = require_product(state, payload.product_id, store_id)

        job = Job(type="regenerate_image", project_id=product.project_id, product_id=product.id)
        return job_queue.submit(job, lambda: run_regenerate_image_job(job, product, payload.prompt_key, payload.extra_prompt))


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> Job:
    state = store.load()
    allowed = store_project_ids(state, current_store_id(request))
    job = next((item for item in state.jobs if item.id == job_id and item.project_id in allowed), None)
    if job is None:
        raise HTTPException(404, "Trabalho não encontrado")
    return job
