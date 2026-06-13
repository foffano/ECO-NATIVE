import json
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.db.models import Listing, Product
from backend.app.services.openrouter_client import OpenRouterResult, OpenRouterUnavailable, vision_completion_result
from backend.app.services.product_paths import is_model_asset_kind
from backend.app.services.prompt_library import SHOPEE_LISTING_PROMPT
from backend.app.services.slice_info import read_3mf_slice_info, slice_info_to_prompt_text


@dataclass
class ListingGenerationResult:
    listing: Listing
    usage: OpenRouterResult


def get_3mf_info(path: str) -> str:
    return slice_info_to_prompt_text(read_3mf_slice_info(path))


def parse_json_response(text: str) -> dict[str, object]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def generate_listing_with_openrouter(product: Product, store_listing_prompt: str = "") -> ListingGenerationResult:
    image_asset = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    model_assets = [asset for asset in product.assets if is_model_asset_kind(asset.kind)]
    if not image_asset:
        raise RuntimeError("Produto sem imagem capturada para analise multimodal.")
    if not image_asset.path or not Path(image_asset.path).is_file():
        raise RuntimeError("Capa do produto nao encontrada no disco. Refaca a coleta ou envie a imagem novamente.")

    prompt = store_listing_prompt.strip() if store_listing_prompt else SHOPEE_LISTING_PROMPT
    context = "Analise a imagem do produto e gere o JSON solicitado pelo prompt."
    if model_assets:
        context += "\n\nContexto Extraido do Fatiador (use gramas para estimar Weight, onde 100g = 0.1kg):\n"
        for index, model_asset in enumerate(model_assets, start=1):
            if not model_asset.path or not Path(model_asset.path).is_file():
                continue
            label = "Modelo principal" if model_asset.kind == "model_3mf" else f"Modelo adicional {index}"
            context += f"\n{label}:\n{get_3mf_info(model_asset.path)}\n"

    result = vision_completion_result(prompt, context, image_asset.path)
    parsed = parse_json_response(result.text)

    return ListingGenerationResult(
        listing=Listing(
            title=parsed.get("Product Name", ""),
            description=parsed.get("Product Description", ""),
            category=parsed.get("Category Name", ""),
            price=str(parsed.get("Price", "")),
            stock=int(parsed.get("Stock", 10) or 10),
            weight=str(parsed.get("Weight", "")),
            parcel_size=parsed.get("Parcel Size", ""),
            keywords=[],
        ),
        usage=result,
    )
