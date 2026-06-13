import json
import time
from pathlib import Path
from urllib.parse import quote

from backend.app.core.settings import get_settings
from backend.app.db.models import Asset, Product
from backend.app.services.cloudflare_r2 import upload_file_to_r2
from backend.app.services.cost_tracker import add_kie_image_cost
from backend.app.services.http_client import HttpResponseError, download as http_download, read_response_json, read_response_text, request as http_request
from backend.app.services.image_options import color_description_map
from backend.app.services.product_paths import (
    color_variation_filename,
    product_dir_for,
    studio_image_filename,
)
from backend.app.services.prompt_library import IMAGE_PROMPTS, render_color_variation_prompt


def product_output_dir(product: Product) -> Path:
    return product_dir_for(product)


def product_sku(product: Product) -> str:
    return str(product.metadata.get("sku") or "").strip().upper()


def r2_key_prefix(product: Product) -> str:
    return f"eco-native/{product.project_id}/{product.id}"


def asset_public_url(product: Product, asset: Asset) -> str:
    if asset.public_url:
        return asset.public_url
    metadata_url = product.metadata.get("image_url")
    if asset.kind == "cover_image" and isinstance(metadata_url, str) and metadata_url.startswith("http"):
        return metadata_url
    return upload_file_to_r2(asset.path, r2_key_prefix(product))


def existing_asset_public_url(product: Product, kind: str, path: Path) -> str | None:
    normalized_path = str(path)
    existing = next((asset for asset in product.assets if asset.kind == kind and asset.path == normalized_path), None)
    return existing.public_url if existing and existing.public_url else None


def create_kie_task(prompt: str, image_url: str, api_key: str, model: str = "qwen/image-edit") -> str:
    response = http_request(
        "POST",
        "https://api.kie.ai/api/v1/jobs/createTask",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "input": {
                "prompt": prompt,
                "image_url": image_url,
                "acceleration": "none",
                "image_size": "square",
                "num_inference_steps": 25,
                "guidance_scale": 4,
                "sync_mode": False,
                "enable_safety_checker": True,
                "output_format": "png",
                "negative_prompt": "blurry, ugly",
            },
        },
        timeout=40,
    )
    try:
        data = read_response_json(response)
    except HttpResponseError as exc:
        raise RuntimeError(f"Falha ao criar task Kie.ai: {exc}") from exc
    task_id = data.get("data", {}).get("taskId")
    if response.status_code == 200 and data.get("code") == 200 and task_id:
        return task_id
    raise RuntimeError(f"Falha ao criar task Kie.ai: {read_response_text(response, limit=300)}")


def poll_kie_task(task_id: str, api_key: str, max_wait_seconds: int = 300) -> str:
    started_at = time.time()
    while time.time() - started_at < max_wait_seconds:
        response = http_request(
            "GET",
            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={quote(task_id)}",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=40,
        )
        try:
            data = read_response_json(response)
        except HttpResponseError as exc:
            raise RuntimeError(f"Falha ao consultar task Kie.ai: {exc}") from exc
        record = data.get("data", {})
        state = record.get("state")
        if data.get("code") == 200 and state == "success":
            result = json.loads(record.get("resultJson") or "{}")
            urls = result.get("resultUrls") or []
            if urls:
                return urls[0]
            raise RuntimeError("Task Kie.ai concluiu sem resultUrls.")
        if state == "fail":
            raise RuntimeError(f"Task Kie.ai falhou: {record.get('failMsg') or record.get('failCode')}")
        time.sleep(3)
    raise RuntimeError("Timeout aguardando task Kie.ai.")


def download_url(url: str, output_path: Path) -> None:
    try:
        http_download(url, output_path, timeout=60)
    except HttpResponseError as exc:
        raise RuntimeError(f"Falha ao baixar imagem gerada: {exc}") from exc


def generate_studio_images(
    product: Product,
    extra_prompt: str = "",
    image_prompts: dict[str, str] | None = None,
) -> list[Asset]:
    settings = get_settings()
    if not settings.kie_api_key:
        raise RuntimeError("KIE_API_KEY nao configurada.")
    kie_model = settings.kie_image_model or "qwen/image-edit"
    cover = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    if not cover:
        raise RuntimeError("Produto sem imagem base capturada.")

    sku = product_sku(product)
    if not sku:
        raise RuntimeError("Produto sem SKU. Gere o SKU antes de criar imagens.")
    output_dir = product_output_dir(product)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_url = asset_public_url(product, cover)
    created_assets: list[Asset] = []

    prompts = image_prompts or IMAGE_PROMPTS
    for prompt_key, prompt in prompts.items():
        kind = f"generated_{prompt_key}"
        output_path = output_dir / studio_image_filename(sku, prompt_key)
        if output_path.exists():
            public_url = existing_asset_public_url(product, kind, output_path) or upload_file_to_r2(output_path, r2_key_prefix(product))
            created_assets.append(
                Asset(
                    product_id=product.id,
                    kind=kind,
                    path=str(output_path),
                    public_url=public_url,
                )
            )
            continue
        task_id = create_kie_task(f"{prompt} {extra_prompt}".strip(), source_url, settings.kie_api_key, kie_model)
        add_kie_image_cost(product, f"Imagem base: {prompt_key}", model=kie_model)
        result_url = poll_kie_task(task_id, settings.kie_api_key)
        download_url(result_url, output_path)
        public_url = upload_file_to_r2(output_path, r2_key_prefix(product))
        created_assets.append(Asset(product_id=product.id, kind=kind, path=str(output_path), public_url=public_url))
        time.sleep(3)

    return created_assets


def regenerate_studio_image(
    product: Product,
    prompt_key: str,
    prompt: str,
    store_extra_prompt: str = "",
    specific_extra_prompt: str = "",
) -> Asset:
    settings = get_settings()
    if not settings.kie_api_key:
        raise RuntimeError("KIE_API_KEY nao configurada.")
    kie_model = settings.kie_image_model or "qwen/image-edit"
    cover = next((asset for asset in product.assets if asset.kind == "cover_image"), None)
    if not cover:
        raise RuntimeError("Produto sem imagem base capturada.")

    sku = product_sku(product)
    if not sku:
        raise RuntimeError("Produto sem SKU. Gere o SKU antes de recriar imagens.")
    output_dir = product_output_dir(product)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / studio_image_filename(sku, prompt_key)
    source_url = asset_public_url(product, cover)
    final_prompt = " ".join(part.strip() for part in [prompt, store_extra_prompt, specific_extra_prompt] if part.strip())

    task_id = create_kie_task(final_prompt, source_url, settings.kie_api_key, kie_model)
    add_kie_image_cost(product, f"Recriação de imagem: {prompt_key}", model=kie_model)
    result_url = poll_kie_task(task_id, settings.kie_api_key)
    download_url(result_url, output_path)
    public_url = upload_file_to_r2(output_path, r2_key_prefix(product), force=True)
    return Asset(product_id=product.id, kind=f"generated_{prompt_key}", path=str(output_path), public_url=public_url)


def regenerate_color_variation_with_kie(
    product: Product,
    source_asset: Asset,
    color_name: str,
    color_prompt_template: str,
    extra_prompt: str = "",
) -> Asset:
    settings = get_settings()
    if not settings.kie_api_key:
        raise RuntimeError("KIE_API_KEY nao configurada.")
    kie_model = settings.kie_image_model or "qwen/image-edit"

    color_desc = color_description_map().get(color_name)
    if not color_desc:
        raise RuntimeError(f"Cor nao encontrada: {color_name}")

    sku = product_sku(product)
    if not sku:
        raise RuntimeError("Produto sem SKU. Gere o SKU antes de recriar variacoes de cor.")
    source_prompt_key = source_asset.kind.replace("generated_", "", 1) or "studio_classic"
    output_dir = product_output_dir(product)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / color_variation_filename(sku, source_prompt_key, color_name)
    source_url = asset_public_url(product, source_asset)

    task_id = create_kie_task(
        render_color_variation_prompt(color_prompt_template, color_desc, extra_prompt),
        source_url,
        settings.kie_api_key,
        kie_model,
    )
    add_kie_image_cost(product, f"Recriação de variação de cor: {color_name}", model=kie_model)
    result_url = poll_kie_task(task_id, settings.kie_api_key)
    download_url(result_url, output_path)
    public_url = upload_file_to_r2(output_path, r2_key_prefix(product), force=True)
    return Asset(product_id=product.id, kind=f"color_{color_name}", path=str(output_path), public_url=public_url)


def generate_color_variations_with_kie(
    product: Product,
    source_asset: Asset,
    selected_colors: list[str],
    color_prompt_template: str,
    extra_prompt: str = "",
) -> list[Asset]:
    settings = get_settings()
    if not settings.kie_api_key:
        raise RuntimeError("KIE_API_KEY nao configurada.")
    kie_model = settings.kie_image_model or "qwen/image-edit"

    sku = product_sku(product)
    if not sku:
        raise RuntimeError("Produto sem SKU. Gere o SKU antes de criar variacoes de cor.")
    source_prompt_key = source_asset.kind.replace("generated_", "", 1) or "studio_classic"
    output_dir = product_output_dir(product)
    source_url = asset_public_url(product, source_asset)
    color_map = color_description_map()
    created_assets: list[Asset] = []

    for color_name in selected_colors:
        color_desc = color_map.get(color_name)
        if not color_desc:
            continue

        output_path = output_dir / color_variation_filename(sku, source_prompt_key, color_name)
        kind = f"color_{color_name}"
        if output_path.exists():
            public_url = existing_asset_public_url(product, kind, output_path) or upload_file_to_r2(output_path, r2_key_prefix(product))
            created_assets.append(
                Asset(
                    product_id=product.id,
                    kind=kind,
                    path=str(output_path),
                    public_url=public_url,
                )
            )
            continue

        task_id = create_kie_task(
            render_color_variation_prompt(color_prompt_template, color_desc, extra_prompt),
            source_url,
            settings.kie_api_key,
            kie_model,
        )
        add_kie_image_cost(product, f"Variação de cor: {color_name}", model=kie_model)
        result_url = poll_kie_task(task_id, settings.kie_api_key)
        download_url(result_url, output_path)
        public_url = upload_file_to_r2(output_path, r2_key_prefix(product))
        created_assets.append(Asset(product_id=product.id, kind=kind, path=str(output_path), public_url=public_url))
        time.sleep(3)

    return created_assets
