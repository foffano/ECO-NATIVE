from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.db.models import Job
from backend.app.db.store import store
from backend.app.services.job_runner import run_collect_job, run_image_job, run_listing_job, run_regenerate_image_job
from backend.app.services.makerworld_session import (
    close_login_session,
    get_login_session_status,
    open_login_session,
)

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


@router.get("")
def list_jobs() -> list[Job]:
    return sorted(store.load().jobs, key=lambda j: j.created_at, reverse=True)


@router.get("/makerworld-login")
def makerworld_login_status() -> dict[str, str | bool | None]:
    return get_login_session_status().__dict__


@router.post("/makerworld-login")
def open_makerworld_login() -> dict[str, str | bool | None]:
    return open_login_session().__dict__


@router.post("/makerworld-login/close")
def close_makerworld_login() -> dict[str, str | bool | None]:
    return close_login_session().__dict__


@router.post("/collect")
def collect_products(payload: CollectRequest) -> Job:
    job = Job(type="collect_products", project_id=payload.project_id)
    store.upsert_job(job)
    return run_collect_job(job, payload)


@router.post("/listing")
def generate_listing(payload: ProductJobRequest) -> Job:
    state = store.load()
    product = next((p for p in state.products if p.id == payload.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    job = Job(type="generate_listing", project_id=product.project_id, product_id=product.id)
    store.upsert_job(job)
    return run_listing_job(job, product)


@router.post("/images")
def generate_images(payload: ProductJobRequest) -> Job:
    state = store.load()
    product = next((p for p in state.products if p.id == payload.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    job = Job(type="generate_images", project_id=product.project_id, product_id=product.id)
    store.upsert_job(job)
    return run_image_job(job, product, payload.color_variations, payload.generate_base_images)


@router.post("/image-regenerate")
def regenerate_image(payload: RegenerateImageRequest) -> Job:
    state = store.load()
    product = next((p for p in state.products if p.id == payload.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    job = Job(type="regenerate_image", project_id=product.project_id, product_id=product.id)
    store.upsert_job(job)
    return run_regenerate_image_job(job, product, payload.prompt_key, payload.extra_prompt)
