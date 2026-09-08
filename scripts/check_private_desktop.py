"""Integration check: headed Chromium, private desktop, screenshots and input."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import tempfile

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
    print(f"PASS: desktop={name.value}; headed Chrome window; screenshot={len(frame)} bytes; mouse and keyboard OK", flush=True)


if __name__ == "__main__":
    if "--worker" in sys.argv:
        import traceback
        try:
            worker()
            Path(sys.argv[-1]).write_text("PASS: headed Chromium on private desktop; screenshots, mouse and keyboard OK", encoding="utf-8")
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
