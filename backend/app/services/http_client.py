"""HTTP helpers that avoid urllib3/requests auto-decompression bugs on Windows."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class HttpResponseError(RuntimeError):
    pass


_COMPRESSION_ERROR_MESSAGE = (
    "Falha ao ler resposta HTTP (compressao invalida). "
    "Atualize para a versao mais recente ou tente novamente."
)


@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    _body: bytes = b""

    def close(self) -> None:
        return None


def merge_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = {
        "Accept-Encoding": "identity",
        "User-Agent": "ECO-Native-Studio/1.0",
    }
    if headers:
        merged.update(headers)
    return merged


def compression_error_message() -> str:
    return _COMPRESSION_ERROR_MESSAGE


def is_compression_error(exc: BaseException) -> bool:
    if isinstance(exc, zlib.error):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, zlib.error)


def _append_query_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.extend((key, str(value)) for key, value in params.items())
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _raise_for_fetch_error(exc: urllib.error.URLError) -> None:
    if is_compression_error(exc):
        raise HttpResponseError(_COMPRESSION_ERROR_MESSAGE) from exc
    raise HttpResponseError(f"Falha de rede HTTP: {exc}") from exc


def _urllib_fetch(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 120,
) -> HttpResponse:
    merged = merge_headers(headers)
    req = urllib.request.Request(url, data=body, method=method.upper())
    for key, value in merged.items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            response_headers = {key.lower(): value for key, value in resp.headers.items()}
            return HttpResponse(status_code=resp.status, headers=response_headers, _body=data)
    except urllib.error.HTTPError as exc:
        try:
            data = exc.read()
        except (zlib.error, OSError):
            data = b""
        response_headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        return HttpResponse(status_code=exc.code, headers=response_headers, _body=data)
    except urllib.error.URLError as exc:
        _raise_for_fetch_error(exc)
    except zlib.error as exc:
        raise HttpResponseError(_COMPRESSION_ERROR_MESSAGE) from exc

    raise HttpResponseError("Falha de rede HTTP desconhecida.")


def read_response_body(response: HttpResponse) -> bytes:
    if not response._body:
        raise HttpResponseError("Resposta HTTP vazia.")
    return response._body


def read_response_text(response: HttpResponse, *, limit: int = 600) -> str:
    return read_response_body(response)[:limit].decode("utf-8", errors="ignore")


def read_response_json(response: HttpResponse) -> dict[str, Any]:
    body = read_response_body(response)
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        preview = body[:600].decode("utf-8", errors="ignore")
        raise HttpResponseError(f"Resposta HTTP invalida: {preview}") from exc
    if not isinstance(parsed, dict):
        raise HttpResponseError("Resposta HTTP JSON deve ser um objeto.")
    return parsed


def request(method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs) -> HttpResponse:
    timeout = int(kwargs.pop("timeout", 120))
    params = kwargs.pop("params", None)
    json_payload = kwargs.pop("json", None)
    data = kwargs.pop("data", None)
    if kwargs:
        raise TypeError(f"Parametros HTTP nao suportados: {', '.join(sorted(kwargs))}")

    target_url = _append_query_params(url, params)
    body: bytes | None = None
    merged_headers = dict(headers or {})
    if json_payload is not None:
        body = json.dumps(json_payload).encode("utf-8")
        merged_headers.setdefault("Content-Type", "application/json")
    elif data is not None:
        body = data if isinstance(data, bytes) else str(data).encode("utf-8")

    if method.upper() == "GET":
        body = None

    return _urllib_fetch(method, target_url, headers=merged_headers, body=body, timeout=timeout)


def download(url: str, output_path: str | Path, *, headers: dict[str, str] | None = None, timeout: int = 60) -> None:
    response = _urllib_fetch("GET", url, headers=headers, timeout=timeout)
    body = read_response_body(response)
    if response.status_code >= 400:
        raise HttpResponseError(
            f"Download falhou ({response.status_code}): {body[:600].decode('utf-8', errors='ignore')}"
        )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
