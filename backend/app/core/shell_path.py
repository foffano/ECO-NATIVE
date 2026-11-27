"""PATH of the user's login shell, for an app started from Finder or the Dock.

macOS starts such an app with a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin), so
command-line tools the app runs, such as the Codex CLI installed by Homebrew or npm,
are not found. The login shell reads the user's profile and knows where they are.
"""
import os
import subprocess
from pathlib import Path

_MARKER = "__ECO_NATIVE_PATH__"
COMMON_DIRS = ("/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin")


def login_shell_path(shell: str | None = None, timeout: float = 5.0) -> str | None:
    """PATH that the user's login shell sets, or None when it cannot be read."""
    shell = shell or os.environ.get("SHELL") or "/bin/zsh"
    try:
        completed = subprocess.run(
            [shell, "-l", "-c", f'printf "{_MARKER}%s" "$PATH"'],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # The profile may print its own text first; the PATH follows the marker.
    _, marker, path = completed.stdout.rpartition(_MARKER)
    if not marker:
        return None
    return path.strip() or None


def merged_path(*parts: str | None) -> str:
    """Join PATH strings in order, keeping the first copy of each folder."""
    seen: set[str] = set()
    folders: list[str] = []
    for part in parts:
        for folder in (part or "").split(os.pathsep):
            if folder and folder not in seen:
                seen.add(folder)
                folders.append(folder)
    return os.pathsep.join(folders)


def use_login_shell_path() -> str:
    """Put the login shell's folders, then the usual tool folders, on this process's PATH."""
    path = merged_path(
        login_shell_path(),
        os.environ.get("PATH"),
        os.pathsep.join(COMMON_DIRS),
        str(Path.home() / ".local" / "bin"),
    )
    os.environ["PATH"] = path
    return path
