import base64
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from backend.app.core.settings import get_settings

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.5-flash-02-23"


class OpenRouterUnavailable(RuntimeError):
    pass


@dataclass
class OpenRouterResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    cost_source: str = "unavailable"
    generation_id: str | None = None


def configured_model() -> str:
    settings = get_settings()
    return settings.openrouter_model or DEFAULT_OPENROUTER_MODEL


def require_api_key() -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterUnavailable("OPENROUTER_API_KEY nao configurada.")
    return settings.openrouter_api_key


def image_to_data_url(path: str) -> str:
    image_path = Path(path)
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _usage_int(usage: dict, key: str) -> int:
    try:
        return int(usage.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _usage_cost(usage: dict) -> float | None:
    for key in ("cost", "total_cost", "total_cost_usd"):
        try:
            value = usage.get(key)
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def fetch_generation_cost(generation_id: str | None, api_key: str) -> float | None:
    if not generation_id:
        return None
    time.sleep(1.5)
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/generation",
            params={"id": generation_id},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        if not response.ok:
            return None
        data = response.json().get("data", {})
        for key in ("total_cost", "cost"):
            value = data.get(key)
            if value is not None:
                return float(value)
    except Exception:
        return None
    return None


def chat_completion_result(
    messages: list[dict[str, object]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> OpenRouterResult:
    api_key = require_api_key()
    selected_model = model or configured_model()
    response = requests.post(
        OPENROUTER_CHAT_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:5173",
            "X-Title": "ECO Native Studio",
        },
        json={
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise OpenRouterUnavailable(f"Erro OpenRouter: {response.text[:600]}") from exc

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterUnavailable(f"Resposta OpenRouter inesperada: {data}") from exc

    if isinstance(content, list):
        text = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict)).strip()
    else:
        text = str(content or "").strip()

    usage = data.get("usage") or {}
    generation_id = data.get("id")
    cost = _usage_cost(usage)
    cost_source = "openrouter_usage" if cost is not None else "unavailable"
    if cost is None:
        generation_cost = fetch_generation_cost(generation_id, api_key)
        if generation_cost is not None:
            cost = generation_cost
            cost_source = "openrouter_generation"

    return OpenRouterResult(
        text=text,
        model=selected_model,
        prompt_tokens=_usage_int(usage, "prompt_tokens"),
        completion_tokens=_usage_int(usage, "completion_tokens"),
        total_tokens=_usage_int(usage, "total_tokens"),
        cost_usd=cost,
        cost_source=cost_source,
        generation_id=generation_id,
    )


def chat_completion(
    messages: list[dict[str, object]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> str:
    return chat_completion_result(messages, model=model, temperature=temperature, max_tokens=max_tokens).text


def text_completion(system_prompt: str, user_prompt: str, *, max_tokens: int = 3000) -> str:
    return text_completion_result(system_prompt, user_prompt, max_tokens=max_tokens).text


def text_completion_result(system_prompt: str, user_prompt: str, *, max_tokens: int = 3000) -> OpenRouterResult:
    return chat_completion_result(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
    )


def vision_completion(system_prompt: str, user_prompt: str, image_path: str, *, max_tokens: int = 4000) -> str:
    return vision_completion_result(system_prompt, user_prompt, image_path, max_tokens=max_tokens).text


def vision_completion_result(system_prompt: str, user_prompt: str, image_path: str, *, max_tokens: int = 4000) -> OpenRouterResult:
    return chat_completion_result(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                ],
            },
        ],
        max_tokens=max_tokens,
    )
