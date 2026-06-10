from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid4().hex


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class ProductStatus(StrEnum):
    imported = "imported"
    scraped = "scraped"
    ai_approved = "ai_approved"
    assets_downloaded = "assets_downloaded"
    images_generated = "images_generated"
    listing_generated = "listing_generated"
    needs_review = "needs_review"
    approved = "approved"
    exported = "exported"
    failed = "failed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Marketplace(StrEnum):
    shopee = "shopee"
    tiktok_shop = "tiktok_shop"
    kwai_shop = "kwai_shop"
    mercado_livre = "mercado_livre"


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    store: str = "Loja principal"
    store_profile_id: str | None = None
    marketplace: Marketplace = Marketplace.shopee
    niche: str = "Utilidades para casa"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class AiProfile(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    prompt: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class StoreProfile(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    marketplace: Marketplace = Marketplace.shopee
    niche: str = "Utilidades para casa"
    logo_path: str | None = None
    ai_profile_id: str | None = None
    search_prompt: str = "Buscar produtos funcionais, uteis e com potencial comercial."
    curation_prompt: str = "Aprovar apenas produtos com bom potencial comercial para a loja."
    listing_prompt: str = "Gerar anuncios profissionais para e-commerce em portugues do Brasil."
    image_prompt: str = "Gerar imagens limpas de produto para marketplace, preservando formato e detalhes."
    image_prompts: dict[str, str] = Field(default_factory=dict)
    color_variation_prompt: str = (
        "Strictly maintain the original object's physical texture, geometry, layer lines, and surface details. "
        "Do NOT change the texture pattern. Only modify the color and surface finish (glossiness/matte) "
        "to update the material to: {color_description}. "
        "The lighting, angle, and background must remain identical to the source image. "
        "{extra_prompt}"
    )
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Asset(BaseModel):
    id: str = Field(default_factory=new_id)
    product_id: str
    kind: str
    path: str
    public_url: str | None = None
    created_at: str = Field(default_factory=now_iso)


class Listing(BaseModel):
    title: str = ""
    description: str = ""
    category: str = ""
    price: str = ""
    stock: int = 10
    weight: str = ""
    parcel_size: str = ""
    keywords: list[str] = Field(default_factory=list)


class Product(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    name: str
    source_url: str | None = None
    status: ProductStatus = ProductStatus.imported
    tags: list[str] = Field(default_factory=list)
    ai_score: str | None = None
    listing: Listing = Field(default_factory=Listing)
    assets: list[Asset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Job(BaseModel):
    id: str = Field(default_factory=new_id)
    type: str
    status: JobStatus = JobStatus.queued
    project_id: str | None = None
    product_id: str | None = None
    progress: int = 0
    message: str = "Na fila"
    logs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class StudioState(BaseModel):
    projects: list[Project] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)
    ai_profiles: list[AiProfile] = Field(default_factory=list)
    store_profiles: list[StoreProfile] = Field(default_factory=list)
