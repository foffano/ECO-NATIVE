"""Mercado Livre integration: per-store OAuth, category prediction and publishing.

Tokens live outside studio.json (which is sent to clients and exported in
backups) in DATA_DIR/mercadolivre.json, keyed by store profile id. The same file
remembers which Mercado Livre category each store chose for an AI category text,
so the next product with that category is suggested correctly.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
import unicodedata
import urllib.parse
from threading import Lock
from typing import Any

from backend.app.core.atomic_files import atomic_write_text
from backend.app.core.paths import DATA_DIR
from backend.app.core.settings import get_settings
from backend.app.services import http_client

API_URL = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
SITE_ID = "MLB"
TOKENS_PATH = DATA_DIR / "mercadolivre.json"
STATE_TTL_SECONDS = 15 * 60
LISTING_TYPES = {"gold_special": "Clássico", "gold_pro": "Premium"}
DEFAULT_WARRANTY_TIME = "90 dias"
# Shown in the publish form even when the category does not require them.
RECOMMENDED_ATTRIBUTES = ("BRAND", "MODEL", "MATERIAL")
PACKAGE_ATTRIBUTES = ("SELLER_PACKAGE_LENGTH", "SELLER_PACKAGE_WIDTH", "SELLER_PACKAGE_HEIGHT", "SELLER_PACKAGE_WEIGHT")
# Filled per published item, never in the shared form.
ITEM_LEVEL_ATTRIBUTES = {"SELLER_SKU", "ITEM_CONDITION", "COLOR"}

_lock = Lock()
# OAuth attempts in flight: nonce -> (store id, PKCE verifier, redirect uri, expiry).
# The app runs a single worker, so process memory is enough; after a restart the
# user only has to click "Conectar" again.
_pending: dict[str, tuple[str, str, str, float]] = {}


class MercadoLivreError(RuntimeError):
    pass


def configured() -> bool:
    settings = get_settings()
    return bool(settings.mercadolivre_app_id and settings.mercadolivre_client_secret)


# --------------------------------------------------------------------------- storage


def _read_file() -> dict[str, Any]:
    if not TOKENS_PATH.exists():
        return {}
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_file(data: dict[str, Any]) -> None:
    atomic_write_text(TOKENS_PATH, json.dumps(data, ensure_ascii=False, indent=2))
    try:
        TOKENS_PATH.chmod(0o600)
    except OSError:
        pass


def get_connection(store_id: str) -> dict[str, Any] | None:
    with _lock:
        return _read_file().get("connections", {}).get(store_id)


def _save_connection(store_id: str, connection: dict[str, Any] | None) -> None:
    with _lock:
        data = _read_file()
        connections = data.setdefault("connections", {})
        if connection is None:
            connections.pop(store_id, None)
        else:
            connections[store_id] = connection
        _write_file(data)


def disconnect(store_id: str) -> None:
    _save_connection(store_id, None)


def _category_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", normalized.lower()).strip()


def remembered_category(store_id: str, listing_category: str) -> dict[str, Any] | None:
    key = _category_key(listing_category)
    if not key:
        return None
    with _lock:
        return _read_file().get("category_map", {}).get(store_id, {}).get(key)


def remember_category(store_id: str, listing_category: str, category: dict[str, Any]) -> None:
    key = _category_key(listing_category)
    if not key:
        return
    with _lock:
        data = _read_file()
        data.setdefault("category_map", {}).setdefault(store_id, {})[key] = category
        _write_file(data)


# --------------------------------------------------------------------------- HTTP


def _error_message(payload: Any, status: int) -> str:
    if isinstance(payload, dict):
        causes = [
            str(cause.get("message"))
            for cause in payload.get("cause") or []
            if isinstance(cause, dict) and cause.get("message") and cause.get("type", "error") == "error"
        ]
        if causes:
            return "; ".join(causes)
        for key in ("message", "error_description", "error"):
            if payload.get(key):
                return str(payload[key])
    return f"Mercado Livre respondeu HTTP {status}"


def _call(method: str, path: str, *, token: str | None = None, headers: dict[str, str] | None = None, **kwargs) -> Any:
    merged = {"Accept": "application/json", **(headers or {})}
    if token:
        merged["Authorization"] = f"Bearer {token}"
    response = http_client.request(method, f"{API_URL}{path}", headers=merged, timeout=60, **kwargs)
    payload: Any = None
    if response._body:
        try:
            payload = json.loads(response._body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
    if response.status_code >= 400:
        raise MercadoLivreError(_error_message(payload, response.status_code))
    return payload


def _oauth_token(form: dict[str, str]) -> dict[str, Any]:
    settings = get_settings()
    body = urllib.parse.urlencode(
        {"client_id": settings.mercadolivre_app_id or "", "client_secret": settings.mercadolivre_client_secret or "", **form}
    )
    try:
        payload = _call(
            "POST",
            "/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=body.encode("utf-8"),
        )
    except MercadoLivreError as exc:
        raise MercadoLivreError(f"Falha ao autorizar no Mercado Livre: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise MercadoLivreError("Mercado Livre não devolveu um token de acesso.")
    return payload


# --------------------------------------------------------------------------- OAuth


def authorization_url(store_id: str, redirect_uri: str) -> str:
    if not configured():
        raise MercadoLivreError("Integração com Mercado Livre não configurada pelo administrador.")
    now = time.time()
    for nonce in [key for key, value in _pending.items() if value[3] < now]:
        _pending.pop(nonce, None)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    _pending[nonce] = (store_id, verifier, redirect_uri, now + STATE_TTL_SECONDS)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": get_settings().mercadolivre_app_id,
            "redirect_uri": redirect_uri,
            "state": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTH_URL}?{query}"


def complete_authorization(state: str, code: str) -> str:
    """Exchange the OAuth code and store the tokens. Returns the store id."""
    pending = _pending.pop(state, None)
    if not pending or pending[3] < time.time():
        raise MercadoLivreError("Autorização expirada. Clique em Conectar novamente.")
    store_id, verifier, redirect_uri, _ = pending
    token = _oauth_token(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri, "code_verifier": verifier}
    )
    user = _call("GET", "/users/me", token=token["access_token"])
    _save_connection(store_id, _connection_from_token(token, user))
    return store_id


def _connection_from_token(token: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user.get("id") or token.get("user_id"),
        "nickname": user.get("nickname"),
        "user_product_seller": "user_product_seller" in (user.get("tags") or []),
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "expires_at": int(time.time()) + int(token.get("expires_in") or 21600),
        "connected_at": int(time.time()),
    }


def access_token(store_id: str) -> tuple[str, dict[str, Any]]:
    """Valid access token for the store, refreshing it when close to expiry."""
    connection = get_connection(store_id)
    if not connection:
        raise MercadoLivreError("Conecte a conta do Mercado Livre em Ajustes > Loja e prompts.")
    if connection.get("expires_at", 0) - 300 > time.time():
        return connection["access_token"], connection
    if not connection.get("refresh_token"):
        raise MercadoLivreError("A conexão com o Mercado Livre expirou. Conecte a conta novamente.")
    # Refresh tokens are single use: the new pair must be stored before anything else.
    token = _oauth_token({"grant_type": "refresh_token", "refresh_token": connection["refresh_token"]})
    user = _call("GET", "/users/me", token=token["access_token"])
    connection = {**_connection_from_token(token, user), "connected_at": connection.get("connected_at")}
    _save_connection(store_id, connection)
    return connection["access_token"], connection


def connection_status(store_id: str) -> dict[str, Any]:
    connection = get_connection(store_id)
    return {
        "configured": configured(),
        "connected": bool(connection),
        "nickname": connection.get("nickname") if connection else None,
        "user_id": connection.get("user_id") if connection else None,
        "user_product_seller": bool(connection and connection.get("user_product_seller")),
    }


# --------------------------------------------------------------------------- categories


def predict_categories(token: str, query: str, limit: int = 6) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    result = _call("GET", f"/sites/{SITE_ID}/domain_discovery/search", token=token, params={"q": query[:120], "limit": limit})
    suggestions: list[dict[str, Any]] = []
    for item in result or []:
        if not isinstance(item, dict) or not item.get("category_id"):
            continue
        if any(existing["category_id"] == item["category_id"] for existing in suggestions):
            continue
        suggestions.append(
            {
                "category_id": item["category_id"],
                "category_name": item.get("category_name") or "",
                "domain_name": item.get("domain_name") or "",
                "attributes": [
                    {"id": attr.get("id"), "value_id": attr.get("value_id"), "value_name": attr.get("value_name")}
                    for attr in item.get("attributes") or []
                    if isinstance(attr, dict) and attr.get("id")
                ],
            }
        )
    return suggestions


def _attribute_tags(attribute: dict[str, Any]) -> dict[str, Any]:
    tags = attribute.get("tags") or {}
    if isinstance(tags, list):  # older payloads send a list of flags
        return {tag: True for tag in tags}
    return tags


def category_details(token: str, category_id: str) -> dict[str, Any]:
    category = _call("GET", f"/categories/{category_id}", token=token)
    raw_attributes = _call("GET", f"/categories/{category_id}/attributes", token=token) or []
    settings = category.get("settings") or {}
    attributes: list[dict[str, Any]] = []
    for attribute in raw_attributes:
        tags = _attribute_tags(attribute)
        if tags.get("read_only") or tags.get("hidden") or tags.get("fixed"):
            continue
        attribute_id = attribute.get("id")
        required = bool(tags.get("required") or tags.get("catalog_required"))
        attributes.append(
            {
                "id": attribute_id,
                "name": attribute.get("name") or attribute_id,
                "value_type": attribute.get("value_type") or "string",
                "values": [
                    {"id": value.get("id"), "name": value.get("name")}
                    for value in (attribute.get("values") or [])[:300]
                    if value.get("name")
                ],
                "allowed_units": [unit.get("id") for unit in attribute.get("allowed_units") or [] if unit.get("id")],
                "default_unit": attribute.get("default_unit"),
                "required": required,
                "conditional_required": bool(tags.get("conditional_required")),
                "hint": attribute.get("hint") or attribute.get("tooltip") or "",
                "item_level": attribute_id in ITEM_LEVEL_ATTRIBUTES,
            }
        )
    return {
        "category_id": category.get("id") or category_id,
        "category_name": category.get("name") or "",
        "path": " > ".join(node.get("name", "") for node in category.get("path_from_root") or []),
        "listing_allowed": bool(settings.get("listing_allowed", True)) and settings.get("status", "enabled") == "enabled",
        "max_title_length": int(settings.get("max_title_length") or 60),
        "attributes": attributes,
    }


def form_attributes(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Attributes the seller fills in: required, recommended and package dimensions."""
    present = {attribute["id"] for attribute in details["attributes"]}
    wanted = set(RECOMMENDED_ATTRIBUTES) | set(PACKAGE_ATTRIBUTES)
    if "GTIN" in present and "EMPTY_GTIN_REASON" in present:
        wanted.add("EMPTY_GTIN_REASON")
    return [
        attribute
        for attribute in details["attributes"]
        if not attribute["item_level"] and (attribute["required"] or attribute["id"] in wanted)
    ]


# --------------------------------------------------------------------------- defaults


def _parse_number(value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_price(value: str) -> float | None:
    text = re.sub(r"[^\d,.]", "", value or "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        price = float(text)
    except ValueError:
        return None
    return round(price, 2) if price > 0 else None


def parse_parcel(value: str) -> dict[str, float]:
    """Read "L:10 W:10 H:10" (or "10x10x10") in centimetres."""
    dims: dict[str, float] = {}
    for key, label in (("L", "length"), ("W", "width"), ("H", "height")):
        match = re.search(rf"\b{key}\s*[:=]\s*(\d+(?:[.,]\d+)?)", value or "", flags=re.IGNORECASE)
        if match:
            dims[label] = float(match.group(1).replace(",", "."))
    if not dims:
        numbers = re.findall(r"\d+(?:[.,]\d+)?", value or "")
        if len(numbers) >= 3:
            dims = dict(zip(("length", "width", "height"), (float(n.replace(",", ".")) for n in numbers[:3])))
    return dims


def _match_value(attribute: dict[str, Any], *candidates: str) -> str | None:
    names = [value["name"] for value in attribute.get("values") or []]
    for candidate in candidates:
        for name in names:
            if _category_key(name) == _category_key(candidate):
                return name
    return None


def default_attribute_values(
    details: dict[str, Any],
    *,
    brand: str,
    model: str,
    weight_kg: str,
    parcel_size: str,
    predicted: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    by_id = {attribute["id"]: attribute for attribute in form_attributes(details)}
    values: dict[str, str] = {}
    for attr in predicted or []:
        if attr.get("id") in by_id and attr.get("value_name"):
            values[attr["id"]] = attr["value_name"]
    if "BRAND" in by_id and "BRAND" not in values and brand:
        values["BRAND"] = brand
    if "MODEL" in by_id and "MODEL" not in values and model:
        values["MODEL"] = model[:60]
    if "MATERIAL" in by_id and "MATERIAL" not in values:
        material = _match_value(by_id["MATERIAL"], "PLA", "Plástico PLA", "Plástico")
        if material or not by_id["MATERIAL"]["values"]:
            values["MATERIAL"] = material or "PLA"
    if "EMPTY_GTIN_REASON" in by_id and "EMPTY_GTIN_REASON" not in values:
        options = [value["name"] for value in by_id["EMPTY_GTIN_REASON"]["values"]]
        values["EMPTY_GTIN_REASON"] = next((name for name in options if "não tem" in name.lower()), options[0] if options else "")
    if "UNITS_PER_PACK" in by_id and "UNITS_PER_PACK" not in values:
        values["UNITS_PER_PACK"] = "1"
    dims = parse_parcel(parcel_size)
    for attribute_id, label in (
        ("SELLER_PACKAGE_LENGTH", "length"),
        ("SELLER_PACKAGE_WIDTH", "width"),
        ("SELLER_PACKAGE_HEIGHT", "height"),
    ):
        if attribute_id in by_id and label in dims:
            values[attribute_id] = f"{dims[label]:g} cm"
    weight = _parse_number(weight_kg)
    if "SELLER_PACKAGE_WEIGHT" in by_id and weight:
        values["SELLER_PACKAGE_WEIGHT"] = f"{max(1, round(weight * 1000))} g"
    return {key: value for key, value in values.items() if value}


def missing_required(details: dict[str, Any], values: dict[str, str]) -> list[str]:
    missing = []
    for attribute in form_attributes(details):
        if not attribute["required"] or values.get(attribute["id"], "").strip():
            continue
        # GTIN may be replaced by the reason why the product has none.
        if attribute["id"] == "GTIN" and values.get("EMPTY_GTIN_REASON", "").strip():
            continue
        missing.append(attribute["name"])
    return missing


# --------------------------------------------------------------------------- publishing


def attribute_payload(details: dict[str, Any], values: dict[str, str]) -> list[dict[str, Any]]:
    by_id = {attribute["id"]: attribute for attribute in details["attributes"]}
    payload: list[dict[str, Any]] = []
    for attribute_id, raw in values.items():
        value = (raw or "").strip()
        attribute = by_id.get(attribute_id)
        if not value or not attribute or attribute["item_level"]:
            continue
        if attribute_id == "GTIN" and values.get("EMPTY_GTIN_REASON", "").strip():
            continue
        match = next((option for option in attribute["values"] if _category_key(option["name"]) == _category_key(value)), None)
        if match and match.get("id"):
            payload.append({"id": attribute_id, "value_id": str(match["id"])})
        else:
            payload.append({"id": attribute_id, "value_name": value})
    return payload


def build_items(
    *,
    details: dict[str, Any],
    values: dict[str, str],
    name: str,
    price: float,
    quantity: int,
    listing_type_id: str,
    warranty_time: str,
    gallery: list[str],
    sku: str,
    variants: list[dict[str, str]],
    user_product_seller: bool,
) -> list[dict[str, Any]]:
    """Request bodies for POST /items.

    User Products sellers (the default since 2025) publish one item per colour
    sharing the same family_name; the title is generated by Mercado Livre.
    Legacy sellers publish one item with a title and a variations array.
    """
    has_color = any(attribute["id"] == "COLOR" for attribute in details["attributes"])
    base = {
        "category_id": details["category_id"],
        "price": price,
        "currency_id": "BRL",
        "available_quantity": quantity,
        "buying_mode": "buy_it_now",
        "listing_type_id": listing_type_id,
        "condition": "new",
        "sale_terms": [
            {"id": "WARRANTY_TYPE", "value_name": "Garantia do vendedor"},
            {"id": "WARRANTY_TIME", "value_name": warranty_time or DEFAULT_WARRANTY_TIME},
        ],
    }
    shared = attribute_payload(details, values)
    title = name[: details["max_title_length"]].strip()

    def sku_attr(value: str) -> list[dict[str, Any]]:
        return [{"id": "SELLER_SKU", "value_name": value}] if value else []

    if user_product_seller:
        targets = variants or [{"color": "", "image": "", "sku": sku}]
        items = []
        for variant in targets:
            pictures = [url for url in [variant.get("image"), *gallery] if url]
            attributes = [*shared, *sku_attr(variant.get("sku") or sku)]
            if variant.get("color") and has_color:
                attributes.append({"id": "COLOR", "value_name": variant["color"]})
            items.append(
                {
                    **base,
                    "family_name": title,
                    "pictures": [{"source": url} for url in dict.fromkeys(pictures)][:10],
                    "attributes": attributes,
                }
            )
        return items

    pictures = list(dict.fromkeys([*gallery, *(variant["image"] for variant in variants if variant.get("image"))]))[:10]
    item: dict[str, Any] = {
        **base,
        "title": title,
        "pictures": [{"source": url} for url in pictures],
        "attributes": [*shared, *([] if variants and has_color else sku_attr(sku))],
    }
    if variants and has_color:
        item.pop("available_quantity")
        item["variations"] = [
            {
                "attribute_combinations": [{"id": "COLOR", "value_name": variant["color"]}],
                "price": price,
                "available_quantity": quantity,
                "picture_ids": [variant["image"]] if variant.get("image") in pictures else pictures[:1],
                "attributes": sku_attr(variant.get("sku") or sku),
            }
            for variant in variants
        ]
    return [item]


def validate_item(token: str, body: dict[str, Any]) -> None:
    _call("POST", "/items/validate", token=token, json=body)


def create_item(token: str, body: dict[str, Any], description: str) -> tuple[dict[str, Any], str | None]:
    item = _call("POST", "/items", token=token, json=body)
    warning = None
    if description.strip():
        try:
            _call("POST", f"/items/{item['id']}/description", token=token, json={"plain_text": description.strip()})
        except MercadoLivreError as exc:
            warning = f"Anúncio {item['id']} criado, mas a descrição falhou: {exc}"
    return item, warning
