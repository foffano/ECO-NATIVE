import json
import re
import zipfile
from dataclasses import dataclass

from backend.app.db.models import Listing, Product
from backend.app.services.openrouter_client import OpenRouterResult, vision_completion_result
from backend.app.services.prompt_library import SHOPEE_LISTING_PROMPT


@dataclass
class ListingGenerationResult:
    listing: Listing
    usage: OpenRouterResult


def get_3mf_info(path: str) -> str:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if "Metadata/slice_info.config" not in archive.namelist():
                return "- Arquivo slice_info.config nao encontrado no 3MF."
            content = archive.read("Metadata/slice_info.config").decode("utf-8", errors="ignore")
            info = []
            weight = re.search(r'weight="([\d.]+)"', content)
            duration = re.search(r'time="([\d]+)"', content)
            if weight:
                info.append(f"- Peso estimado do filamento: {weight.group(1)} gramas")
            if duration:
                seconds = int(duration.group(1))
                info.append(f"- Tempo de impressao estimado: {seconds // 3600}h e {(seconds % 3600) // 60}m")
            return "\n".join(info) if info else content[:1000]
    except Exception as exc:
        return f"- Erro ao tentar ler o arquivo 3MF: {exc}"


def parse_json_response(text: str) -> dict[str, object]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def generate_listing_with_openrouter(product: Product, store_listing_prompt: str = "") -> ListingGenerationResult:
    image_asset = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    model_asset = next((asset for asset in product.assets if asset.kind == "model_3mf"), None)
    if not image_asset:
        raise RuntimeError("Produto sem imagem capturada para analise multimodal.")

    prompt = store_listing_prompt.strip() if store_listing_prompt else SHOPEE_LISTING_PROMPT
    context = "Analise a imagem do produto e gere o JSON solicitado pelo prompt."
    if model_asset:
        context += "\n\nContexto Extraido do Fatiador (use gramas para estimar Weight, onde 100g = 0.1kg):\n"
        context += get_3mf_info(model_asset.path)

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
