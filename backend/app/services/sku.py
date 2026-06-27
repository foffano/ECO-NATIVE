from __future__ import annotations

import re

from backend.app.db.models import Product, Project, StoreProfile

COLOR_CODES = {
    "PLA_Yellow": "YEL",
    "PLA_Black": "BLK",
    "PLA_GreyMetallic": "GRM",
    "PLA_TiffanyBlue": "TFB",
    "PLA_Red": "RED",
    "PLA_Green": "GRN",
    "PLA_BlueMetallic": "BLM",
    "PLA_Blue": "BLU",
    "PLA_Purple": "PUR",
    "PLA_BabyPink": "BPK",
    "PLA_NeonPink": "NPK",
    "PLA_BabyBlue": "BBL",
    "PLA_Magenta": "MAG",
    "Velvet_White": "VWT",
}


def code_from_text(value: str, length: int = 4) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.upper())
    if not words:
        return "ITEM"[:length]
    if len(words) == 1:
        return words[0][:length].ljust(length, "X")
    code = "".join(word[0] for word in words[:length])
    return code[:length].ljust(length, "X")


def product_sequence(existing_products: list[Product], project_id: str) -> int:
    return 1 + sum(1 for product in existing_products if product.project_id == project_id and product.metadata.get("sku"))


def generate_product_sku(
    product_name: str,
    existing_products: list[Product],
    project: Project | None,
    store_profile: StoreProfile,
) -> str:
    store_code = code_from_text(store_profile.name, 4)
    product_code = code_from_text(product_name, 4)
    sequence = product_sequence(existing_products, project.id if project else "")
    sku = f"{store_code}-{product_code}-{sequence:04d}"
    used = {str(product.metadata.get("sku") or "") for product in existing_products}
    while sku in used:
        sequence += 1
        sku = f"{store_code}-{product_code}-{sequence:04d}"
    return sku


def ensure_product_sku(
    product: Product,
    existing_products: list[Product],
    project: Project | None,
    store_profile: StoreProfile,
) -> str:
    sku = str(product.metadata.get("sku") or "").strip().upper()
    if not sku:
        sku = generate_product_sku(product.name, existing_products, project, store_profile)
        product.metadata["sku"] = sku
    return sku


def color_sku(base_sku: str, color_name: str) -> str:
    color_code = COLOR_CODES.get(color_name) or code_from_text(color_name.replace("_", " "), 3)
    return f"{base_sku}-{color_code}"


def variation_sku(base_sku: str, attribute: str, value: str) -> str:
    attribute_code = code_from_text(attribute, 3)
    value_code = code_from_text(value, 3)
    return f"{base_sku}-{attribute_code}{value_code}"


def ensure_color_skus(product: Product, color_names: list[str]) -> dict[str, str]:
    base_sku = str(product.metadata.get("sku") or "").strip().upper()
    if not base_sku:
        base_sku = f"ITEM-{product.id[:8].upper()}"
        product.metadata["sku"] = base_sku

    current = product.metadata.get("color_skus")
    color_skus = dict(current) if isinstance(current, dict) else {}
    for color_name in color_names:
        color_skus[color_name] = color_skus.get(color_name) or color_sku(base_sku, color_name)
    product.metadata["color_skus"] = color_skus
    return color_skus
