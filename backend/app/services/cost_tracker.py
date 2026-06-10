import os
from typing import Any

from backend.app.db.models import Product, now_iso


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def kie_image_cost_usd() -> float:
    return _float_env("KIE_IMAGE_COST_USD", 0.01)


def estimate_openrouter_cost(prompt_tokens: int = 0, completion_tokens: int = 0) -> float:
    input_per_million = _float_env("OPENROUTER_EST_INPUT_USD_PER_1M", 0.065)
    output_per_million = _float_env("OPENROUTER_EST_OUTPUT_USD_PER_1M", 0.26)
    return (prompt_tokens / 1_000_000 * input_per_million) + (completion_tokens / 1_000_000 * output_per_million)


def add_cost_event(
    product: Product,
    *,
    provider: str,
    action: str,
    model: str,
    cost_usd: float,
    source: str,
    units: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "id": f"cost_{now_iso()}_{len(product.metadata.get('cost_events', [])) + 1}",
        "created_at": now_iso(),
        "provider": provider,
        "action": action,
        "model": model,
        "cost_usd": round(max(cost_usd, 0), 6),
        "currency": "USD",
        "source": source,
        "units": units,
        "metadata": metadata or {},
    }
    events = list(product.metadata.get("cost_events") or [])
    events.append(event)
    product.metadata["cost_events"] = events
    product.metadata["cost_total_usd"] = round(sum(float(item.get("cost_usd") or 0) for item in events), 6)
    return event


def add_openrouter_cost(product: Product, action: str, result) -> dict[str, Any]:
    cost = result.cost_usd
    source = result.cost_source
    if cost is None:
        cost = estimate_openrouter_cost(result.prompt_tokens, result.completion_tokens)
        source = "estimated_tokens"
    return add_cost_event(
        product,
        provider="OpenRouter",
        action=action,
        model=result.model,
        cost_usd=cost,
        source=source,
        units=1,
        metadata={
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "generation_id": result.generation_id,
        },
    )


def add_kie_image_cost(product: Product, action: str, model: str = "qwen/image-edit", units: int = 1) -> dict[str, Any]:
    return add_cost_event(
        product,
        provider="Kie.ai",
        action=action,
        model=model,
        cost_usd=kie_image_cost_usd() * units,
        source="estimated_env",
        units=units,
        metadata={"unit_cost_usd": kie_image_cost_usd(), "credits_per_image": 2, "usd_per_1000_credits": 5},
    )
