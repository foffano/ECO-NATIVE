from backend.app.db.models import StoreProfile
from backend.app.db.store import store
from backend.app.services.ai_profiles import ensure_default_profile
from backend.app.services.prompt_library import DEFAULT_COLOR_VARIATION_PROMPT, IMAGE_PROMPTS, SHOPEE_LISTING_PROMPT

DEFAULT_STORE_NAME = "Loja principal"


DEFAULT_CURATION_PROMPT = """
Voce e um curador especialista num negocio de impressao 3D e e-commerce.
A empresa busca produtos comercialmente viaveis para vender como produto fisico em marketplaces.

Priorize:
- Utilidades para casa, escritorio, cozinha, banheiro e organizacao
- Suportes, organizadores, acessorios funcionais, decoracao util, presentes simples
- Produtos com boa leitura visual e potencial de anuncio

Rejeite:
- Armas, pecas perigosas, cosplay complexo, action figures licenciadas, personagens famosos
- Modelos sem utilidade comercial clara
- Produtos que dependem de licenca comercial duvidosa quando a descricao indicar restricao
- Produtos que parecam dificeis de anunciar ou vender como item fisico comum

Responda EXATAMENTE apenas:
SIM
ou
NAO
""".strip()


def normalize_store_profile(profile: StoreProfile) -> StoreProfile:
    changed = False
    if (
        not profile.curation_prompt
        or "Responda em JSON" in profile.curation_prompt
        or profile.curation_prompt.strip() == "Aprovar apenas produtos com bom potencial comercial para a loja."
    ):
        profile.curation_prompt = DEFAULT_CURATION_PROMPT
        changed = True
    if not profile.listing_prompt or len(profile.listing_prompt) < 250:
        profile.listing_prompt = SHOPEE_LISTING_PROMPT.strip()
        changed = True
    if not profile.image_prompts:
        profile.image_prompts = dict(IMAGE_PROMPTS)
        changed = True
    else:
        for key, prompt in IMAGE_PROMPTS.items():
            if not profile.image_prompts.get(key):
                profile.image_prompts[key] = prompt
                changed = True
    if not profile.color_variation_prompt:
        profile.color_variation_prompt = DEFAULT_COLOR_VARIATION_PROMPT
        changed = True
    if changed:
        return store.upsert_store_profile(profile)
    return profile


def ensure_default_store_profile() -> StoreProfile:
    state = store.load()
    if state.store_profiles:
        return state.store_profiles[0]

    ai_profile = ensure_default_profile()
    profile = StoreProfile(
        name=DEFAULT_STORE_NAME,
        ai_profile_id=ai_profile.id,
        search_prompt="Buscar utilidades para casa, organizadores, suportes e produtos funcionais.",
        curation_prompt=DEFAULT_CURATION_PROMPT,
        listing_prompt=SHOPEE_LISTING_PROMPT.strip(),
        image_prompt=(
            "Criar imagens de produto limpas, com fundo suave, boa iluminacao e mantendo formato real do objeto."
        ),
        image_prompts=dict(IMAGE_PROMPTS),
        color_variation_prompt=DEFAULT_COLOR_VARIATION_PROMPT,
    )
    return store.upsert_store_profile(profile)


def list_store_profiles() -> list[StoreProfile]:
    ensure_default_store_profile()
    profiles = [normalize_store_profile(profile) for profile in store.load().store_profiles]
    return sorted(profiles, key=lambda profile: profile.created_at)


def get_store_profile(profile_id: str | None) -> StoreProfile:
    profiles = list_store_profiles()
    if profile_id:
        selected = next((profile for profile in profiles if profile.id == profile_id), None)
        if selected:
            return selected
    return profiles[0]
