from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.app.core.settings import get_settings
from backend.app.db.models import Product, StudioState, now_iso
from backend.app.db.store import store
from backend.app.services import mercadolivre as ml
from backend.app.services.authorization import current_store_id, require_product
from backend.app.services.cloudflare_r2 import r2_configured
from backend.app.services.exporter import color_display_name, color_image_map, gallery_image_urls, ordered_variation_colors
from backend.app.services.sku import ensure_color_skus
from backend.app.services.store_profiles import get_store_profile

router = APIRouter()
# OAuth redirects arrive from mercadolivre.com.br; the strict session cookie is
# not sent on that cross-site navigation, so the callback is public and trusts
# only the one-time state it issued.
callback_router = APIRouter()
CALLBACK_PATH = "/api/auth/mercado-livre/callback"


class PublishRequest(BaseModel):
    category_id: str
    listing_type_id: str = "gold_special"
    family_name: str
    price: str
    quantity: int = Field(default=10, ge=1, le=99999)
    warranty_time: str = ml.DEFAULT_WARRANTY_TIME
    attributes: dict[str, str] = Field(default_factory=dict)
    publish_colors: bool = True


def _redirect_uri(request: Request) -> str:
    configured = get_settings().mercadolivre_redirect_uri
    if configured:
        return configured.strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",", 1)[0].strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",", 1)[0].strip()
    return f"{proto}://{host}{CALLBACK_PATH}"


def _ml_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=502 if isinstance(exc, ml.MercadoLivreError) else 400, detail=str(exc))


def _color_assets(product: Product) -> list[str]:
    colors: list[str] = []
    for asset in product.assets:
        color_id = asset.kind[len("color_"):] if asset.kind.startswith("color_") else ""
        if color_id and color_id not in colors:
            colors.append(color_id)
    return colors


def _image_count(product: Product) -> int:
    return sum(1 for asset in product.assets if asset.kind == "cover_image" or asset.kind.startswith("generated_"))


@router.get("/status")
def status(request: Request) -> dict:
    payload = ml.connection_status(current_store_id(request))
    payload["redirect_uri"] = _redirect_uri(request)
    return payload


@router.post("/connect")
def connect(request: Request) -> dict:
    try:
        return {"url": ml.authorization_url(current_store_id(request), _redirect_uri(request))}
    except ml.MercadoLivreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/connection", status_code=204)
def disconnect(request: Request) -> None:
    ml.disconnect(current_store_id(request))


@callback_router.get("/callback")
def oauth_callback(state: str = "", code: str = "", error: str = "") -> RedirectResponse:
    if error or not code:
        return RedirectResponse("/?mercadolivre=denied", status_code=303)
    try:
        ml.complete_authorization(state, code)
    except ml.MercadoLivreError:
        return RedirectResponse("/?mercadolivre=error", status_code=303)
    return RedirectResponse("/?mercadolivre=connected", status_code=303)


@router.get("/products/{product_id}/draft")
def publish_draft(product_id: str, request: Request, category_id: str | None = None, q: str | None = None) -> dict:
    store_id = current_store_id(request)
    state = store.load()
    product = require_product(state, product_id, store_id)
    try:
        token, connection = ml.access_token(store_id)
        query = (q or product.listing.title or product.name).strip()
        suggestions = ml.predict_categories(token, query)
        remembered = ml.remembered_category(store_id, product.listing.category)
        if remembered and not q:
            suggestions = [
                {**remembered, "attributes": [], "remembered": True},
                *(item for item in suggestions if item["category_id"] != remembered["category_id"]),
            ]
        saved = product.metadata.get("mercado_livre") or {}
        chosen = (category_id or saved.get("category_id") or (suggestions[0]["category_id"] if suggestions else "")).strip()
        details = ml.category_details(token, chosen) if chosen else None
    except ml.MercadoLivreError as exc:
        raise _ml_error(exc) from exc

    values: dict[str, str] = {}
    missing: list[str] = []
    if details:
        predicted = next((item["attributes"] for item in suggestions if item["category_id"] == details["category_id"]), [])
        profile = get_store_profile(next((p.store_profile_id for p in state.projects if p.id == product.project_id), None))
        values = ml.default_attribute_values(
            details,
            brand=profile.name,
            model=product.name,
            weight_kg=product.listing.weight,
            parcel_size=product.listing.parcel_size,
            predicted=predicted,
        )
        if saved.get("category_id") == details["category_id"]:
            values.update({key: value for key, value in (saved.get("attributes") or {}).items() if value})
        missing = ml.missing_required(details, values)

    return {
        "connection": {"nickname": connection.get("nickname"), "user_product_seller": bool(connection.get("user_product_seller"))},
        "query": query,
        "suggestions": suggestions,
        "category": {**details, "attributes": ml.form_attributes(details)} if details else None,
        "values": values,
        "missing_required": missing,
        "family_name": saved.get("family_name") or product.listing.title or product.name,
        "price": product.listing.price,
        "quantity": product.listing.stock or 10,
        "listing_type_id": saved.get("listing_type_id") or "gold_special",
        "listing_types": ml.LISTING_TYPES,
        "warranty_time": saved.get("warranty_time") or ml.DEFAULT_WARRANTY_TIME,
        "colors": [color_display_name(color) for color in _color_assets(product)],
        "image_count": _image_count(product),
        "r2_configured": r2_configured(),
        "published": saved.get("items") or [],
    }


@router.post("/products/{product_id}/publish")
def publish(product_id: str, payload: PublishRequest, request: Request) -> dict:
    store_id = current_store_id(request)
    state = store.load()
    product = require_product(state, product_id, store_id)
    saved = product.metadata.get("mercado_livre") or {}
    if saved.get("items"):
        raise HTTPException(status_code=409, detail="Este produto já foi publicado no Mercado Livre.")
    if payload.listing_type_id not in ml.LISTING_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de anúncio inválido.")
    price = ml.parse_price(payload.price)
    if not price:
        raise HTTPException(status_code=422, detail="Informe um preço válido.")
    if not payload.family_name.strip():
        raise HTTPException(status_code=422, detail="Informe o nome do anúncio.")
    if not r2_configured():
        raise HTTPException(status_code=400, detail="Configure o Cloudflare R2: o Mercado Livre baixa as imagens por URL pública.")

    try:
        token, connection = ml.access_token(store_id)
        details = ml.category_details(token, payload.category_id.strip())
    except ml.MercadoLivreError as exc:
        raise _ml_error(exc) from exc
    if not details["listing_allowed"]:
        raise HTTPException(status_code=422, detail=f"A categoria {details['path']} não aceita anúncios. Escolha uma categoria mais específica.")
    missing = ml.missing_required(details, payload.attributes)
    if missing:
        raise HTTPException(status_code=422, detail=f"Preencha os campos obrigatórios: {', '.join(missing)}")

    # Publishes current images to R2 (the marketplace downloads them by URL).
    gallery = gallery_image_urls(product)
    if not gallery:
        raise HTTPException(status_code=422, detail="O produto precisa de pelo menos uma imagem.")
    variants: list[dict[str, str]] = []
    if payload.publish_colors:
        color_urls = color_image_map(product)
        colors = [color for color in ordered_variation_colors(product, color_urls) if color in color_urls]
        color_skus = ensure_color_skus(product, colors) if colors else {}
        variants = [
            {"color": color_display_name(color), "image": color_urls[color], "sku": color_skus.get(color, "")}
            for color in colors
        ]

    bodies = ml.build_items(
        details=details,
        values=payload.attributes,
        name=payload.family_name.strip(),
        price=price,
        quantity=payload.quantity,
        listing_type_id=payload.listing_type_id,
        warranty_time=payload.warranty_time,
        gallery=gallery,
        sku=str(product.metadata.get("sku") or ""),
        variants=variants,
        user_product_seller=bool(connection.get("user_product_seller")),
    )
    # Validate every item before creating any, so a bad attribute does not
    # leave half of the colours published.
    try:
        for body in bodies:
            ml.validate_item(token, body)
    except ml.MercadoLivreError as exc:
        raise HTTPException(status_code=422, detail=f"O Mercado Livre recusou o anúncio: {exc}") from exc

    created: list[dict] = []
    warnings: list[str] = []
    failure: str | None = None
    for body, variant in zip(bodies, variants or [{}] * len(bodies)):
        try:
            item, warning = ml.create_item(token, body, product.listing.description)
        except ml.MercadoLivreError as exc:
            failure = str(exc)
            break
        if warning:
            warnings.append(warning)
        created.append(
            {
                "id": item.get("id"),
                "permalink": item.get("permalink"),
                "status": item.get("status"),
                "color": variant.get("color", "") if len(bodies) > 1 else "",
                "title": item.get("title"),
            }
        )

    record = {
        "category_id": details["category_id"],
        "category_name": details["category_name"],
        "category_path": details["path"],
        "listing_type_id": payload.listing_type_id,
        "family_name": payload.family_name.strip(),
        "warranty_time": payload.warranty_time,
        "attributes": payload.attributes,
        "items": created,
        "published_at": now_iso() if created else None,
        "seller_nickname": connection.get("nickname"),
    }
    public_urls = {asset.id: asset.public_url for asset in product.assets if asset.public_url}

    def apply(current: StudioState) -> None:
        target = next((item for item in current.products if item.id == product.id), None)
        if not target:
            return
        for asset in target.assets:
            if asset.id in public_urls:
                asset.public_url = public_urls[asset.id]
        if product.metadata.get("color_skus"):
            target.metadata["color_skus"] = product.metadata["color_skus"]
        target.metadata["mercado_livre"] = record
        if created:
            target.metadata["listed"] = True
            target.metadata.setdefault("listed_at", now_iso())
        target.updated_at = now_iso()

    store.mutate(apply)
    if created:
        ml.remember_category(
            store_id,
            product.listing.category,
            {"category_id": details["category_id"], "category_name": details["category_name"], "domain_name": details["path"]},
        )
    if failure:
        done = f" {len(created)} anúncio(s) já foram criados." if created else ""
        raise HTTPException(status_code=502, detail=f"Falha ao publicar no Mercado Livre: {failure}.{done}")
    return {"items": created, "warnings": warnings}
