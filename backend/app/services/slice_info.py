from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass


@dataclass
class SliceInfo:
    weight_grams: float | None = None
    print_time_seconds: int | None = None
    filament_type: str | None = None
    raw_excerpt: str = ""


def parse_slice_info(content: str) -> SliceInfo:
    info = SliceInfo(raw_excerpt=content[:1000])
    weight = re.search(r'weight="([\d.]+)"', content)
    duration = re.search(r'time="([\d]+)"', content)
    filament = re.search(r'filament_type="([^"]+)"', content, flags=re.IGNORECASE)
    if weight:
        info.weight_grams = float(weight.group(1))
    if duration:
        info.print_time_seconds = int(duration.group(1))
    if filament:
        info.filament_type = filament.group(1).strip()
    return info


def format_print_time(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "—"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def read_3mf_slice_info(path: str) -> SliceInfo:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if "Metadata/slice_info.config" not in archive.namelist():
                return SliceInfo(raw_excerpt="slice_info.config não encontrado no 3MF.")
            content = archive.read("Metadata/slice_info.config").decode("utf-8", errors="ignore")
            return parse_slice_info(content)
    except Exception as exc:
        return SliceInfo(raw_excerpt=f"Erro ao ler 3MF: {exc}")


def slice_info_to_prompt_text(info: SliceInfo) -> str:
    lines: list[str] = []
    if info.weight_grams is not None:
        lines.append(f"- Peso estimado do filamento: {info.weight_grams:g} gramas")
    if info.print_time_seconds is not None:
        lines.append(f"- Tempo de impressão estimado: {format_print_time(info.print_time_seconds)}")
    if info.filament_type:
        lines.append(f"- Filamento no fatiador: {info.filament_type}")
    if lines:
        return "\n".join(lines)
    return info.raw_excerpt or "- Nenhum dado útil encontrado no slice_info.config."
