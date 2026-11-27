import socket
import sys
from pathlib import Path

import pytest

from backend import desktop_app
from backend.app.core import paths, shell_path


def test_merged_path_keeps_order_and_drops_repeats():
    assert shell_path.merged_path("/a:/b", None, "/b:/c", "", "/a") == "/a:/b:/c"


def test_login_shell_path_reads_after_profile_output(tmp_path):
    shell = tmp_path / "fake-shell"
    # Plays a login shell whose profile prints a greeting, which must not end up in PATH.
    # `shift` drops -l, so /bin/sh does not read the real /etc/profile.
    shell.write_text('#!/bin/sh\necho "welcome"\nPATH=/tools/bin:/usr/bin\nexport PATH\nshift\nexec /bin/sh "$@"\n')
    shell.chmod(0o755)
    assert shell_path.login_shell_path(str(shell)) == "/tools/bin:/usr/bin"


def test_login_shell_path_is_none_when_the_shell_cannot_run(tmp_path):
    assert shell_path.login_shell_path(str(tmp_path / "missing-shell")) is None


def test_use_login_shell_path_adds_homebrew(monkeypatch):
    monkeypatch.setattr(shell_path, "login_shell_path", lambda: None)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    path = shell_path.use_login_shell_path().split(":")
    assert path[:2] == ["/usr/bin", "/bin"]
    assert "/opt/homebrew/bin" in path


def test_choose_port_moves_off_a_busy_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        port = desktop_app.choose_port(taken)
    assert port != taken and port > 0


def test_choose_port_keeps_a_free_preferred_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    assert desktop_app.choose_port(free) == free


@pytest.mark.parametrize("frozen", [False, True])
def test_mac_data_dir(monkeypatch, tmp_path, frozen):
    monkeypatch.delenv("ECO_NATIVE_DATA_DIR", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    repo = tmp_path / "repo"
    (repo / "backend").mkdir(parents=True)
    (repo / "package.json").write_text("{}")
    monkeypatch.chdir(repo)
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    expected = (
        tmp_path / "home" / "Library" / "Application Support" / paths.APP_NAME
        if frozen
        else repo / "data"
    )
    # A packaged app opened from the repository folder still uses Application Support.
    assert paths.get_data_dir() == expected


def test_startup_error_page_escapes_the_message(tmp_path):
    page = desktop_app.startup_error_page("<script>x</script>", tmp_path)
    assert "<script>x" not in page and "&lt;script&gt;" in page
