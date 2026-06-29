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
import tempfile
import time
import uuid
from pathlib import Path

from backend.app.core.settings import get_settings

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# Frases que o Codex CLI costuma imprimir (stdout/stderr) quando a conta atinge
# um limite de uso/cota ou e barrada por rate limit. Mantidas em minusculo para
# comparacao case-insensitive.
_CODEX_LIMIT_MARKERS = (
    "rate limit",
    "usage limit",
    "quota",
    "429",
    "too many requests",
    "try again",
    "reached your",
)


class CodexImageError(RuntimeError):
    """Erro ao gerar/editar imagem via Codex CLI."""


def _looks_like_usage_limit(*texts: str) -> bool:
    """True se alguma das saidas indicar limite de uso/cota/rate limit do Codex."""
    combined = " ".join(text for text in texts if text).lower()
    return any(marker in combined for marker in _CODEX_LIMIT_MARKERS)


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


def _newest_image_in(directory: Path) -> Path | None:
    """Retorna a imagem mais recente dentro de um diretorio (recursivo).

    Usado APENAS sobre o diretorio de trabalho exclusivo desta chamada, que
    nenhuma outra execucao concorrente enxerga, entao "mais recente" e seguro
    aqui (ao contrario de uma pasta compartilhada).
    """
    newest: tuple[float, Path] | None = None
    if not directory or not directory.is_dir():
        return None
    for entry in directory.rglob("*"):
        if not entry.is_file() or entry.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, entry)
    return newest[1] if newest else None


# Copia resiliente: no Windows, um arquivo recem-criado (pelo processo codex ou
# por um filho dele) costuma dar "Permission denied" (Errno 13) por alguns
# instantes — geralmente o antivirus/Windows Defender escaneando o arquivo novo
# em tempo real, ou um handle ainda nao liberado. E um lock TRANSIENTE, nao uma
# permissao permanentemente negada, entao re-tentar com um backoff curto resolve.
_COPY_MAX_ATTEMPTS = 8
_COPY_BACKOFF_SECONDS = 0.4


def _resilient_copy(source: Path, destination: Path) -> None:
    """Copia source -> destination tolerando locks transientes (AV/handle).

    Re-tenta em PermissionError/OSError com backoff curto. So levanta a ultima
    excecao apos esgotar todas as tentativas, preservando o texto do erro
    original para diagnostico.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    last_error: OSError | None = None
    for attempt in range(_COPY_MAX_ATTEMPTS):
        try:
            # Le os bytes da origem e escreve no destino. Ler tudo de uma vez
            # mantem o handle da origem aberto pelo menor tempo possivel, o que
            # ajuda quando o lock do antivirus e momentaneo.
            data = source.read_bytes()
            with open(destination, "wb") as out:
                out.write(data)
            return
        except OSError as exc:
            last_error = exc
            if attempt < _COPY_MAX_ATTEMPTS - 1:
                time.sleep(_COPY_BACKOFF_SECONDS)

    # Esgotou as tentativas: propaga a ultima falha (com seu texto original).
    assert last_error is not None
    raise last_error


def _find_by_exact_name(directory: Path, name: str) -> Path | None:
    """Procura um arquivo com nome EXATO dentro de directory (recursivo).

    Diferente de "imagem mais recente", casar pelo nome unico desta chamada e
    seguro mesmo em uma pasta compartilhada (~/.codex/generated_images) usada
    por varias execucoes concorrentes: nunca pegamos a imagem de outro produto.
    """
    if not directory or not directory.is_dir():
        return None
    for entry in directory.rglob(name):
        if entry.is_file() and entry.suffix.lower() in _IMAGE_SUFFIXES:
            return entry
    return None


def edit_image_with_codex(
    source_path: Path,
    prompt: str,
    output_path: Path,
    timeout_seconds: int = 600,
) -> Path:
    """Edita source_path aplicando prompt e grava o resultado em output_path.

    Retorna o caminho final gerado. Levanta CodexImageError em caso de falha.

    Concorrencia: cada chamada usa um diretorio de trabalho TEMPORARIO exclusivo
    e um nome de arquivo unico (UUID). Assim, mesmo quando varios produtos sao
    gerados em paralelo (o lote do frontend dispara todos de uma vez e o FastAPI
    roda cada rota sincrona em uma thread do pool), duas execucoes nunca enxergam
    o arquivo uma da outra -> nao ha como uma imagem cair no produto errado.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.is_file():
        raise CodexImageError(f"Imagem base nao encontrada: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass

    codex_bin = _resolve_codex_bin()

    # Diretorio de trabalho exclusivo desta chamada: isola execucoes concorrentes.
    work_dir = Path(tempfile.mkdtemp(prefix="codex_imggen_"))
    # Nome unico desta chamada: permite casar o arquivo por nome exato (e nao por
    # "mais recente") mesmo se o Codex salvar em ~/.codex/generated_images.
    unique_name = f"ecogen_{uuid.uuid4().hex}.png"
    expected_in_work = work_dir / unique_name

    instruction = (
        "Use the built-in image_gen tool (imagegen skill) to edit the attached image. "
        f"Apply exactly this change: {prompt.strip()}. "
        "Use quality=high, size=1024x1024. "
        f"Save the final result as a single PNG file named '{unique_name}' "
        "in the current working directory, overwriting it if it already exists. "
        "Do not create or modify any other file, and do not write any code."
    )

    # IMPORTANTE: a flag `--image` do `codex exec` e variadica (`--image <FILE>...`),
    # ou seja, ela consome todos os argumentos posicionais seguintes como imagens.
    # Se o prompt fosse passado como argumento posicional logo apos `--image <src>`,
    # ele seria engolido como se fosse outra imagem e o Codex acabaria lendo o prompt
    # do stdin (vazio) -> "No prompt provided via stdin".
    #
    # Por isso NAO passamos o prompt na linha de comando: deixamos o argumento
    # posicional `[PROMPT]` ausente e entregamos a instrucao via stdin, que e
    # exatamente o que o `codex exec` espera nesse caso. `--image` fica como ultima
    # flag e recebe apenas a imagem de origem.
    cmd = [
        codex_bin,
        "exec",
        "--cd",
        str(work_dir),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--image",
        str(source_path),
    ]

    try:
        try:
            completed = subprocess.run(
                cmd,
                input=instruction,
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

        # 1) Caso normal: o arquivo com o nome pedido esta no diretorio exclusivo.
        produced: Path | None = expected_in_work if expected_in_work.is_file() else None
        # 2) O Codex pode ter salvo com outro nome dentro do diretorio exclusivo.
        #    Como o diretorio so pertence a esta chamada, pegar a imagem mais
        #    recente dele e seguro (nenhuma outra execucao escreve aqui).
        if produced is None:
            produced = _newest_image_in(work_dir)
        # 3) Ultimo recurso: o Codex pode ter salvo na pasta compartilhada
        #    ~/.codex/generated_images. Casamos APENAS pelo nome unico desta
        #    chamada (nunca por "mais recente"), o que e seguro sob concorrencia.
        if produced is None:
            produced = _find_by_exact_name(
                Path.home() / ".codex" / "generated_images", unique_name
            )

        if produced is not None:
            try:
                _resilient_copy(produced, output_path)
            except OSError as exc:
                raise CodexImageError(
                    f"Falha ao mover imagem gerada pelo Codex: {exc}"
                ) from exc
            return output_path

        # Nenhuma imagem foi gerada. Antes de cair na mensagem generica, tentamos
        # reconhecer um limite de uso/cota/rate limit do Codex para dar um retorno
        # claro ao usuario. Esse caso costuma vir com exit code != 0 e uma mensagem
        # de limite no stdout/stderr (mas tambem cobrimos exit 0 com aviso de limite).
        stdout_text = completed.stdout or ""
        stderr_text = completed.stderr or ""
        stdout_tail = stdout_text[-800:]
        stderr_tail = stderr_text[-800:]

        if _looks_like_usage_limit(stdout_text, stderr_text):
            raise CodexImageError(
                "Limite de uso do Codex atingido. Tente novamente mais tarde.\n"
                f"Codigo de saida: {completed.returncode}\n"
                f"stdout: {stdout_tail}\n"
                f"stderr: {stderr_tail}"
            )

        if completed.returncode != 0:
            raise CodexImageError(
                "Codex CLI finalizou com erro e nenhuma imagem foi gerada.\n"
                f"Codigo de saida: {completed.returncode}\n"
                f"stdout: {stdout_tail}\n"
                f"stderr: {stderr_tail}"
            )

        raise CodexImageError(
            "Codex CLI finalizou mas a imagem esperada nao foi gerada.\n"
            f"Codigo de saida: {completed.returncode}\n"
            f"stdout: {stdout_tail}\n"
            f"stderr: {stderr_tail}"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
