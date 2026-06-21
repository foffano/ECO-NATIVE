import base64
import time
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.settings import get_settings
from backend.app.services.cover_image import CoverImageError, mime_type_for_image, validate_cover_bytes
from backend.app.services.http_client import HttpResponseError, read_response_json, read_response_text, request
from backend.app.services.rate_limiter import openrouter_limiter

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


def _openrouter_headers(api_key: str, *, json_request: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://127.0.0.1:5173",
        "X-Title": "ECO Native Studio",
    }
    if json_request:
        headers["Content-Type"] = "application/json"
    return headers


def _request(method: str, url: str, *, api_key: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers = {**_openrouter_headers(api_key, json_request=method.upper() != "GET"), **headers}
    try:
        return request(method, url, headers=headers, **kwargs)
    except HttpResponseError as exc:
        raise OpenRouterUnavailable(str(exc)) from exc


def _validate_image_bytes(data: bytes, path: Path) -> None:
    try:
        validate_cover_bytes(data, path)
    except CoverImageError as exc:
        raise OpenRouterUnavailable(str(exc)) from exc


def image_to_data_url(path: str) -> str:
    image_path = Path(path)
    if not image_path.is_file():
        raise OpenRouterUnavailable(f"Imagem nao encontrada: {path}")
    data = image_path.read_bytes()
    _validate_image_bytes(data, image_path)
    mime_type = mime_type_for_image(data, image_path)
    encoded = base64.b64encode(data).decode("ascii")
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
        response = _request(
            "GET",
            "https://openrouter.ai/api/v1/generation",
            api_key=api_key,
            params={"id": generation_id},
            timeout=30,
        )
        if response.status_code >= 400:
            return None
        data = read_response_json(response).get("data", {})
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
    openrouter_limiter.acquire()
    response = _request(
        "POST",
        OPENROUTER_CHAT_URL,
        api_key=api_key,
        json={
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    if response.status_code >= 400:
        raise OpenRouterUnavailable(f"Erro OpenRouter: {read_response_text(response)}")

    try:
        data = read_response_json(response)
    except HttpResponseError as exc:
        raise OpenRouterUnavailable(str(exc)) from exc

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
