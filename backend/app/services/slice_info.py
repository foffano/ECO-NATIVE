from __future__ import annotations

import re
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path


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


def _looks_like_zip(path: Path) -> bool:
    try:
        signature = path.read_bytes()[:4]
    except OSError:
        return False
    return signature in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}


def read_3mf_slice_info(path: str) -> SliceInfo:
    source = Path(path)
    if not source.is_file():
        return SliceInfo(raw_excerpt=f"Arquivo 3MF nao encontrado: {path}")
    if not _looks_like_zip(source):
        return SliceInfo(raw_excerpt=f"Arquivo 3MF invalido ou corrompido: {source.name}")

    try:
        with zipfile.ZipFile(source, "r") as archive:
            if "Metadata/slice_info.config" not in archive.namelist():
                return SliceInfo(raw_excerpt="slice_info.config não encontrado no 3MF.")
            content = archive.read("Metadata/slice_info.config").decode("utf-8", errors="ignore")
            return parse_slice_info(content)
    except (zipfile.BadZipFile, zlib.error, OSError, UnicodeDecodeError) as exc:
        return SliceInfo(raw_excerpt=f"Erro ao ler 3MF ({source.name}): {exc}")
    except Exception as exc:
        return SliceInfo(raw_excerpt=f"Erro ao ler 3MF ({source.name}): {exc}")


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
