"""HTTP helpers that avoid urllib3/requests auto-decompression bugs on Windows."""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

import requests
from requests import Response


class HttpResponseError(RuntimeError):
    pass


def merge_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = {
        "Accept-Encoding": "identity",
        "User-Agent": "ECO-Native-Studio/1.0",
    }
    if headers:
        merged.update(headers)
    return merged


def read_response_body(response: Response) -> bytes:
    raw = response.raw
    if raw is None:
        raise HttpResponseError("Resposta HTTP sem stream disponivel.")
    raw.decode_content = False
    try:
        data = raw.read()
    except zlib.error as exc:
        raise HttpResponseError(
            "Falha ao ler resposta HTTP (compressao invalida). "
            "Atualize para a versao mais recente ou tente novamente."
        ) from exc
    if not data:
        raise HttpResponseError("Resposta HTTP vazia.")
    return data


def read_response_text(response: Response, *, limit: int = 600) -> str:
    return read_response_body(response)[:limit].decode("utf-8", errors="ignore")


def read_response_json(response: Response) -> dict[str, Any]:
    body = read_response_body(response)
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HttpResponseError(f"Resposta HTTP invalida: {read_response_text(response)}") from exc
    if not isinstance(parsed, dict):
        raise HttpResponseError("Resposta HTTP JSON deve ser um objeto.")
    return parsed


def request(method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs) -> Response:
    kwargs.setdefault("timeout", 120)
    kwargs["stream"] = True
    try:
        return requests.request(method, url, headers=merge_headers(headers), **kwargs)
    except requests.RequestException as exc:
        raise HttpResponseError(f"Falha de rede HTTP: {exc}") from exc


def download(url: str, output_path: str | Path, *, headers: dict[str, str] | None = None, timeout: int = 60) -> None:
    response = request("GET", url, headers=headers, timeout=timeout)
    body = read_response_body(response)
    if response.status_code >= 400:
        raise HttpResponseError(
            f"Download falhou ({response.status_code}): {body[:600].decode('utf-8', errors='ignore')}"
        )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
