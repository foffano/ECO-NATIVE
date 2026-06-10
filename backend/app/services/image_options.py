from __future__ import annotations

import json
import re

from backend.app.core.paths import DATA_DIR
from backend.app.services.prompt_library import FILAMENT_COLORS

COLOR_OPTIONS_PATH = DATA_DIR / "image_color_options.json"


def normalize_color_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")
    return cleaned or "Custom_Color"


def default_colors() -> list[dict[str, str]]:
    return [{"id": name, "description": description} for name, description in FILAMENT_COLORS]


def read_color_options() -> list[dict[str, str]]:
    if not COLOR_OPTIONS_PATH.exists():
        return default_colors()
    try:
        data = json.loads(COLOR_OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_colors()
    if not isinstance(data, list):
        return default_colors()
    colors: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        color_id = normalize_color_id(str(item.get("id") or ""))
        description = str(item.get("description") or "").strip()
        if color_id and description:
            colors.append({"id": color_id, "description": description})
    return colors or default_colors()


def save_color_options(colors: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in colors:
        color_id = normalize_color_id(str(item.get("id") or ""))
        description = str(item.get("description") or "").strip()
        if not color_id or not description or color_id in seen:
            continue
        seen.add(color_id)
        normalized.append({"id": color_id, "description": description})
    if not normalized:
        normalized = default_colors()
    COLOR_OPTIONS_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def color_description_map() -> dict[str, str]:
    return {item["id"]: item["description"] for item in read_color_options()}
