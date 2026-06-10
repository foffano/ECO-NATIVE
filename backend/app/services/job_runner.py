from backend.app.db.models import Asset, Job, JobStatus, Product, ProductStatus
from backend.app.db.store import store
from backend.app.services.cost_tracker import add_openrouter_cost
from backend.app.services.image_generation import (
    generate_color_variations_with_kie,
    generate_studio_images,
    regenerate_color_variation_with_kie,
    regenerate_studio_image,
)
from backend.app.services.listing_generator import generate_listing_with_openrouter
from backend.app.services.sku import ensure_color_skus, ensure_product_sku
from backend.app.services.store_profiles import get_store_profile
from backend.app.services.makerworld_scraper import (
    clean_makerworld_url,
    discover_model_urls,
    scrape_product_urls,
)


def _finish_job(job: Job, message: str) -> Job:
    job.status = JobStatus.completed
    job.progress = 100
    job.message = message
    job.logs.append(message)
    return store.upsert_job(job)


def _extend_unique_assets(product: Product, assets: list[Asset]) -> list[Asset]:
    existing = {(asset.kind, asset.path): asset for asset in product.assets}
    added: list[Asset] = []
    for asset in assets:
        key = (asset.kind, asset.path)
        if key in existing:
            if asset.public_url and asset.public_url != existing[key].public_url:
                existing[key].public_url = asset.public_url
                existing[key].created_at = asset.created_at
            continue
        product.assets.append(asset)
        existing[key] = asset
        added.append(asset)
    return added


def run_collect_job(job: Job, payload) -> Job:
    job.status = JobStatus.running
    job.progress = 20
    job.message = "Coletando produtos"
    manual_links = bool(payload.urls)
    job.logs.append("Job iniciado com scraper MakerWorld. Produtos serao coletados sem curadoria IA.")
    store.upsert_job(job)

    state = store.load()
    project = next((item for item in state.projects if item.id == payload.project_id), None)
    store_profile = get_store_profile(payload.store_profile_id or (project.store_profile_id if project else None))
    existing_urls = {
        clean_makerworld_url(product.source_url)
        for product in state.products
        if product.project_id == payload.project_id and product.source_url
    }

    try:
        urls = payload.urls
        if not urls:
            job.progress = 35
            job.message = "Buscando links no MakerWorld"
            job.logs.append(f"Busca por palavra-chave: {payload.keyword or 'tendencias'}")
            job.logs.append(f"Loja ativa: {store_profile.name} | nicho={store_profile.niche}")
            store.upsert_job(job)
            urls = discover_model_urls(
                keyword=payload.keyword,
                limit=payload.limit,
                scrolls=payload.scrolls,
                headless=not payload.visible_browser,
            )

        job.progress = 60
        job.message = "Lendo paginas de produtos"
        urls = [
            clean_makerworld_url(url)
            for url in urls[: payload.limit]
            if clean_makerworld_url(url) not in existing_urls
        ]
        job.logs.append(f"{len(urls)} link(s) novo(s) para extracao direta.")
        store.upsert_job(job)

        scraped_products = scrape_product_urls(
            project_id=payload.project_id,
            urls=urls,
            headless=not payload.visible_browser,
            download_cover=True,
            download_model=True,
        )
    except Exception as exc:
        job.status = JobStatus.failed
        job.progress = 100
        job.message = "Falha na coleta MakerWorld"
        job.logs.append(f"{exc.__class__.__name__}: {exc}")
        return store.upsert_job(job)

    created = 0
    sku_reference_products = list(state.products)
    for scraped in scraped_products:
        if scraped.source_url in existing_urls:
            job.logs.append(f"Duplicado ignorado: {scraped.source_url}")
            continue

        job.status = JobStatus.running
        job.progress = min(95, 75 + created)
        job.message = f"Salvando produto: {scraped.name[:50]}"
        store.upsert_job(job)

        product = Product(
            project_id=payload.project_id,
            name=scraped.name,
            source_url=scraped.source_url,
            status=ProductStatus.assets_downloaded,
            ai_score="coletado_sem_curadoria",
            tags=scraped.tags or (["link selecionado", "coleta"] if manual_links else ["coleta"]),
            metadata={
                "source": "makerworld",
                "description": scraped.description,
                "image_url": scraped.image_url,
                "curator_decision": "COLETADO_SEM_CURADORIA_IA",
                "manual_import": manual_links,
                "ai_curation_skipped": True,
                "model_download_error": scraped.model_error,
            },
        )
        ensure_product_sku(product, sku_reference_products, project, store_profile)
        sku_reference_products.append(product)
        if scraped.local_image_path:
            product.assets.append(
                Asset(
                    product_id=product.id,
                    kind="cover_image",
                    path=scraped.local_image_path,
                    public_url=scraped.image_url,
                )
            )
        if scraped.model_file_path:
            product.assets.append(
                Asset(
                    product_id=product.id,
                    kind="model_3mf",
                    path=scraped.model_file_path,
                )
            )
        if scraped.model_error:
            job.logs.append(f"Falha ao baixar 3MF de {scraped.name}: {scraped.model_error}")
        store.upsert_product(product)
        existing_urls.add(scraped.source_url)
        created += 1

    job.metadata["ai_cost_total_usd"] = 0
    job.metadata["ai_request_count"] = 0
    job.metadata["created_products"] = created
    job.metadata["rejected_products"] = 0
    job.metadata["manual_without_ai"] = True
    job.metadata["ai_curation_skipped"] = True
    return _finish_job(job, f"{created} produto(s) coletado(s) e adicionados para revisao.")


def run_listing_job(job: Job, product: Product) -> Job:
    job.status = JobStatus.running
    job.progress = 50
    job.message = "Gerando anuncio com IA"
    state = store.load()
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    job.logs.append(f"Usando perfil de loja: {store_profile.name}")
    store.upsert_job(job)

    try:
        result = generate_listing_with_openrouter(product, store_profile.listing_prompt)
        product.listing = result.listing
        event = add_openrouter_cost(product, "Geração de anúncio", result.usage)
        job.logs.append(f"Custo IA registrado: OpenRouter ${event['cost_usd']:.6f} ({event['source']})")
    except Exception as exc:
        job.status = JobStatus.failed
        job.progress = 100
        job.message = "Falha ao gerar anuncio com IA"
        job.logs.append(f"{exc.__class__.__name__}: {exc}")
        return store.upsert_job(job)

    product.status = ProductStatus.listing_generated
    product.metadata["listing_prompt"] = store_profile.listing_prompt
    product.metadata["store_profile_id"] = store_profile.id
    store.upsert_product(product)
    return _finish_job(job, "Anuncio gerado e salvo para revisao")


def run_image_job(
    job: Job,
    product: Product,
    selected_colors: list[str] | None = None,
    generate_base_images: bool = True,
) -> Job:
    job.status = JobStatus.running
    job.progress = 25
    job.message = "Gerando imagens de estúdio" if generate_base_images else "Gerando variações de cor"
    job.logs.append("Usando prompts detalhados do image_generator.py.")
    store.upsert_job(job)

    state = store.load()
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)

    color_count = 0
    try:
        studio_assets: list[Asset] = []
        if generate_base_images:
            studio_assets = generate_studio_images(
                product,
                extra_prompt=store_profile.image_prompt,
                image_prompts=store_profile.image_prompts,
            )
            _extend_unique_assets(product, studio_assets)
            store.upsert_product(product)

        if selected_colors:
            job.progress = 70
            job.message = "Gerando variações de cor selecionadas"
            job.logs.append("Usando prompt de variacao de cor do exemplo, executado via Kie.ai/Qwen.")
            store.upsert_job(job)

            source_asset = next((asset for asset in studio_assets if "studio_classic" in asset.kind), None)
            if not source_asset and studio_assets:
                source_asset = studio_assets[0]
            if not source_asset:
                source_asset = next((asset for asset in product.assets if "generated_studio_classic" in asset.kind), None)
            if not source_asset:
                source_asset = next((asset for asset in product.assets if asset.kind.startswith("generated_")), None)
            if source_asset:
                ensure_product_sku(product, state.products, project, store_profile)
                product.metadata["color_skus"] = ensure_color_skus(product, selected_colors)
                color_assets = generate_color_variations_with_kie(
                    product,
                    source_asset,
                    selected_colors,
                    store_profile.color_variation_prompt,
                    extra_prompt=store_profile.image_prompt,
                )
                _extend_unique_assets(product, color_assets)
                color_count = len(color_assets)
            else:
                raise RuntimeError("Gere as imagens base antes de criar variações de cor.")
    except Exception as exc:
        job.status = JobStatus.failed
        job.progress = 100
        job.message = "Falha ao gerar imagens"
        job.logs.append(f"{exc.__class__.__name__}: {exc}")
        return store.upsert_job(job)

    product.status = ProductStatus.images_generated
    product.metadata["image_prompt"] = store_profile.image_prompt
    product.metadata["image_prompts"] = store_profile.image_prompts
    product.metadata["color_variation_prompt"] = store_profile.color_variation_prompt
    product.metadata["generated_image_count"] = len([asset for asset in product.assets if asset.kind.startswith("generated_")])
    product.metadata["color_variation_count"] = len([asset for asset in product.assets if asset.kind.startswith("color_")])
    store.upsert_product(product)
    if color_count:
        if generate_base_images:
            return _finish_job(job, f"Imagens principais e {color_count} variações de cor prontas")
        return _finish_job(job, f"{color_count} variações de cor prontas")
    return _finish_job(job, "Imagens principais geradas")


def run_regenerate_image_job(job: Job, product: Product, prompt_key: str, extra_prompt: str = "") -> Job:
    job.status = JobStatus.running
    job.progress = 40
    job.message = f"Recriando imagem {prompt_key}"
    store.upsert_job(job)

    state = store.load()
    project = next((item for item in state.projects if item.id == product.project_id), None)
    store_profile = get_store_profile(project.store_profile_id if project else None)
    if prompt_key.startswith("color_"):
        color_name = prompt_key.replace("color_", "", 1)
        source_asset = next((asset for asset in product.assets if asset.kind.startswith("generated_")), None)
        if not source_asset:
            job.status = JobStatus.failed
            job.progress = 100
            job.message = "Imagem base IA nao encontrada"
            job.logs.append("Gere uma imagem base antes de recriar variacoes de cor.")
            return store.upsert_job(job)
        try:
            ensure_product_sku(product, state.products, project, store_profile)
            product.metadata["color_skus"] = ensure_color_skus(product, [color_name])
            asset = regenerate_color_variation_with_kie(
                product,
                source_asset,
                color_name,
                store_profile.color_variation_prompt,
                extra_prompt=extra_prompt,
            )
            product.assets = [item for item in product.assets if item.kind != asset.kind]
            product.assets.append(asset)
        except Exception as exc:
            job.status = JobStatus.failed
            job.progress = 100
            job.message = "Falha ao recriar variacao de cor"
            job.logs.append(f"{exc.__class__.__name__}: {exc}")
            return store.upsert_job(job)

        product.status = ProductStatus.images_generated
        product.metadata["last_regenerated_image"] = prompt_key
        product.metadata["last_regenerated_image_extra_prompt"] = extra_prompt
        store.upsert_product(product)
        return _finish_job(job, f"VariaÃ§Ã£o {color_name} recriada")

    prompt = store_profile.image_prompts.get(prompt_key)
    if not prompt:
        job.status = JobStatus.failed
        job.progress = 100
        job.message = "Prompt de imagem não encontrado"
        job.logs.append(f"Prompt ausente: {prompt_key}")
        return store.upsert_job(job)

    try:
        asset = regenerate_studio_image(
            product,
            prompt_key,
            prompt,
            store_extra_prompt=store_profile.image_prompt,
            specific_extra_prompt=extra_prompt,
        )
        product.assets = [item for item in product.assets if item.kind != asset.kind]
        product.assets.append(asset)
    except Exception as exc:
        job.status = JobStatus.failed
        job.progress = 100
        job.message = "Falha ao recriar imagem"
        job.logs.append(f"{exc.__class__.__name__}: {exc}")
        return store.upsert_job(job)

    product.status = ProductStatus.images_generated
    product.metadata["last_regenerated_image"] = prompt_key
    product.metadata["last_regenerated_image_extra_prompt"] = extra_prompt
    store.upsert_product(product)
    return _finish_job(job, f"Imagem {prompt_key} recriada")
