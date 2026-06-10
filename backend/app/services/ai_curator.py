from dataclasses import dataclass

from backend.app.services.openrouter_client import OpenRouterResult, OpenRouterUnavailable, text_completion_result

DEFAULT_CURATOR_PROMPT = """
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
"""


@dataclass
class CuratorDecision:
    approved: bool
    raw_response: str
    usage: OpenRouterResult | None = None


class AiCuratorUnavailable(RuntimeError):
    pass


def evaluate_product(
    product_title: str,
    tags: list[str] | None = None,
    description: str = "",
    custom_prompt: str | None = None,
) -> CuratorDecision:
    instruction = custom_prompt or DEFAULT_CURATOR_PROMPT

    context = f"""
Avalie o seguinte produto do MakerWorld:

TITULO: {product_title}
TAGS: {", ".join(tags or []) or "N/A"}
DESCRICAO: {description[:2500] or "N/A"}

Decida se este produto deve entrar no pipeline de anuncios.
"""

    try:
        result = text_completion_result(instruction, context, max_tokens=20)
        raw = result.text.strip().upper()
    except OpenRouterUnavailable as exc:
        raise AiCuratorUnavailable(f"{exc} A coleta com curadoria IA foi bloqueada.") from exc

    if "SIM" in raw and "NAO" not in raw:
        return CuratorDecision(approved=True, raw_response=raw, usage=result)
    return CuratorDecision(approved=False, raw_response=raw, usage=result)
