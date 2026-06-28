"""Geracao/edicao de imagens usando o Codex CLI.

Diferente do caminho da Kie.ai (que recebe uma URL publica), o Codex CLI roda
localmente e aceita a imagem base como arquivo no disco (flag --image). Por isso
aqui trabalhamos sempre com caminhos locais: a imagem de origem e o destino sao
arquivos no proprio computador do usuario, sem necessidade de subir nada para o
Cloudflare R2 antes de gerar.

O Codex usa a assinatura ChatGPT (login OAuth) para a skill `imagegen` /
ferramenta `image_gen`, entao no modo padrao nao e necessaria a OPENAI_API_KEY.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

from backend.app.core.settings import get_settings

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class CodexImageError(RuntimeError):
    """Erro ao gerar/editar imagem via Codex CLI."""


def _resolve_codex_bin() -> str:
    settings = get_settings()
    candidate = (settings.codex_bin or "").strip() or "codex"

    found = shutil.which(candidate)
    if found:
        return found

    # No Windows o executavel costuma vir como codex.cmd / codex.exe.
    if os.name == "nt":
        for ext in (".cmd", ".exe", ".bat"):
            found = shutil.which(candidate + ext)
            if found:
                return found

    # Deixa o subprocess levantar FileNotFoundError com a mensagem original.
    return candidate


def _find_generated_image(search_dirs: list[Path], modified_after: float) -> Path | None:
    """Procura o arquivo de imagem mais recente criado depois de modified_after."""
    newest: tuple[float, Path] | None = None
    for directory in search_dirs:
        if not directory or not directory.is_dir():
            continue
        for entry in directory.rglob("*"):
            if not entry.is_file() or entry.suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime < modified_after - 1:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, entry)
    return newest[1] if newest else None


def edit_image_with_codex(
    source_path: Path,
    prompt: str,
    output_path: Path,
    timeout_seconds: int = 600,
) -> Path:
    """Edita source_path aplicando prompt e grava o resultado em output_path.

    Retorna o caminho final gerado. Levanta CodexImageError em caso de falha.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.is_file():
        raise CodexImageError(f"Imagem base nao encontrada: {source_path}")

    work_dir = output_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass

    codex_bin = _resolve_codex_bin()
    instruction = (
        "Use the built-in image_gen tool (imagegen skill) to edit the attached image. "
        f"Apply exactly this change: {prompt.strip()}. "
        "Use quality=high, size=1024x1024. "
        f"Save the final result as a single PNG file named '{output_path.name}' "
        "in the current working directory, overwriting it if it already exists. "
        "Do not create or modify any other file, and do not write any code."
    )

    cmd = [
        codex_bin,
        "exec",
        "--cd",
        str(work_dir),
        "--sandbox",
        "workspace-write",
        "--image",
        str(source_path),
        instruction,
    ]

    started_at = time.time()
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(work_dir),
        )
    except FileNotFoundError as exc:
        raise CodexImageError(
            "Codex CLI nao encontrado. Instale o Codex CLI e/ou ajuste o caminho do "
            "executavel no campo CODEX_BIN das integracoes."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CodexImageError("Timeout aguardando o Codex CLI gerar a imagem.") from exc

    if output_path.is_file():
        return output_path

    # Fallback: o Codex pode ter salvo a imagem com outro nome / em outra pasta
    # (por exemplo ~/.codex/generated_images). Tenta localizar o arquivo mais
    # recente e move para o destino esperado.
    candidate = _find_generated_image(
        [work_dir, Path.home() / ".codex" / "generated_images"],
        modified_after=started_at,
    )
    if candidate and candidate.resolve() != output_path.resolve():
        try:
            shutil.copyfile(candidate, output_path)
            return output_path
        except OSError as exc:
            raise CodexImageError(f"Falha ao mover imagem gerada pelo Codex: {exc}") from exc
    if candidate:
        return candidate

    stdout_tail = (completed.stdout or "")[-800:]
    stderr_tail = (completed.stderr or "")[-800:]
    raise CodexImageError(
        "Codex CLI finalizou mas a imagem esperada nao foi gerada.\n"
        f"Codigo de saida: {completed.returncode}\n"
        f"stdout: {stdout_tail}\n"
        f"stderr: {stderr_tail}"
    )
