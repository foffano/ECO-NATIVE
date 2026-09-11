"""Integration check: headed Chromium, private desktop, screenshots and input."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import tempfile
import time
import os
from unittest.mock import patch
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def worker():
    from playwright.sync_api import sync_playwright
    from backend.app.core.playwright_env import configure_playwright_browsers

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    desktop = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    name = ctypes.create_unicode_buffer(256)
    needed = wintypes.DWORD()
    assert user32.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed))
    assert name.value.startswith("ECO-Native-"), name.value
    assert configure_playwright_browsers()
    with tempfile.TemporaryDirectory(prefix="eco-browser-check-") as profile:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(profile, headless=False, viewport={"width": 1280, "height": 720})
            page = context.pages[0]
            page.set_content('<body style="background:#abcdef"><input id="text"><button onclick="this.textContent=\'OK\'">Test</button></body>')
            page.locator("input").click()
            page.keyboard.insert_text("remote input works")
            page.locator("button").click()
            assert page.locator("input").input_value() == "remote input works"
            assert page.locator("button").inner_text() == "OK"
            frame = page.screenshot(type="jpeg", timeout=15000)
            assert len(frame) > 1000
            # Confirm actual Chromium windows belong to the private desktop.
            found = []
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def visit(hwnd, _):
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                if cls.value.startswith("Chrome_WidgetWin"):
                    found.append(cls.value)
                return True
            callback = callback_type(visit)
            user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, callback_type, wintypes.LPARAM]
            assert user32.EnumDesktopWindows(desktop, callback, 0)
            assert found, "No Chromium window on private desktop"
            context.close()
    check_remote_popups()
    print(f"PASS: desktop={name.value}; headed Chrome window; screenshot={len(frame)} bytes; mouse and keyboard OK", flush=True)


def check_remote_popups():
    from backend.app.services.makerworld_session import RemoteBrowserSession
    html = """<button style="width:300px;height:100px">Fazer login</button><script>
    document.querySelector('button').onclick = () => {
      let p=window.open('', 'login', 'width=420,height=350');
      p.document.write('<body style=\"background:yellow\"><input autofocus onkeydown=\"if(event.keyCode===13)window.close()\"></body>');
      p.document.close();
    };</script>"""
    def wait_for(predicate):
        until = time.monotonic() + 20
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(.1)
        if session.frame():
            (Path(tempfile.gettempdir()) / "eco-popup-debug.jpg").write_bytes(session.frame())
        raise AssertionError(f"Remote session timeout: {session.status()}")
    with tempfile.TemporaryDirectory(prefix="eco-popup-test-") as profile:
        def open_context(playwright, **kwargs):
            return playwright.chromium.launch_persistent_context(profile, headless=False, viewport=kwargs["viewport"])
        with patch("backend.app.services.makerworld_session.open_makerworld_context", side_effect=open_context), patch.dict(os.environ, {"ECO_NATIVE_MAKERWORLD_URL": "data:text/html," + quote(html)}):
            session = RemoteBrowserSession("integration-test")
            session.start()
            try:
                wait_for(lambda: session.frame() is not None and len(session.status().pages) == 1)
                original = session.status().active_page_id
                first_frame = session.frame()
                session.send({"type": "click", "x": 80, "y": 45, "page_id": original})
                wait_for(lambda: len(session.status().pages) == 2 and session.status().active_page_id != original)
                popup = session.status().active_page_id
                assert session.frame() != first_frame
                session.send({"type": "select_page", "page_id": original})
                wait_for(lambda: session.status().active_page_id == original)
                session.send({"type": "select_page", "page_id": popup})
                wait_for(lambda: session.status().active_page_id == popup)
                session.send({"type": "click", "x": 60, "y": 15, "page_id": popup})
                session.send({"type": "text", "text": "login test", "page_id": popup})
                session.send({"type": "key", "key": "Enter", "page_id": popup})
                wait_for(lambda: len(session.status().pages) == 1 and session.status().active_page_id == original)
                assert session.status().open
                # A second popup after closing the first must also be followed.
                session.send({"type": "click", "x": 80, "y": 45, "page_id": original})
                wait_for(lambda: len(session.status().pages) == 2 and session.status().active_page_id != original)
            finally:
                session.close()
                session._thread.join(20)
                assert not session._thread.is_alive()


if __name__ == "__main__":
    if "--worker" in sys.argv:
        import traceback
        try:
            worker()
            Path(sys.argv[-1]).write_text("PASS: headed Chromium on private desktop; screenshots, mouse and keyboard; remote popup opening, switching, closing and reopening OK", encoding="utf-8")
        except Exception:
            Path(sys.argv[-1]).write_text(traceback.format_exc(), encoding="utf-8")
            raise
    else:
        from backend.app.core.windows_desktop import run_on_private_desktop
        with tempfile.TemporaryDirectory(prefix="eco-desktop-check-") as output:
            result = Path(output) / "result.txt"
            code = run_on_private_desktop([sys.executable, str(Path(__file__).resolve()), "--worker", str(result)])
            print(result.read_text(encoding="utf-8") if result.exists() else f"Worker failed: {code}")
            sys.exit(code)
