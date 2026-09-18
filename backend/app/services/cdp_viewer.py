"""Passive DevTools connection to a browser that a collect job drives.

A second Playwright connection would redirect the browser's downloads to its own folder
(the job's 3MF files came out empty) and auto-attach to every tab. This client only takes
screenshots, reads the page state and dispatches input to the job's tab.
"""
import base64
import itertools
import json
import time
import urllib.request

from websockets.sync.client import connect

BUTTON_MASKS = {"left": 1, "right": 2, "middle": 4}
MODIFIER_MASKS = {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}
# key: (code, windowsVirtualKeyCode, text)
SPECIAL_KEYS = {
    "Enter": ("Enter", 13, "\r"),
    "Tab": ("Tab", 9, ""),
    "Backspace": ("Backspace", 8, ""),
    "Delete": ("Delete", 46, ""),
    "Escape": ("Escape", 27, ""),
    "ArrowLeft": ("ArrowLeft", 37, ""),
    "ArrowUp": ("ArrowUp", 38, ""),
    "ArrowRight": ("ArrowRight", 39, ""),
    "ArrowDown": ("ArrowDown", 40, ""),
    "Home": ("Home", 36, ""),
    "End": ("End", 35, ""),
    "PageUp": ("PageUp", 33, ""),
    "PageDown": ("PageDown", 34, ""),
}


class CdpError(RuntimeError):
    pass


class CdpPage:
    """The part of Playwright's Page API the remote panel uses, over a raw DevTools socket."""

    def __init__(self, endpoint: str, timeout: float = 10.0) -> None:
        with urllib.request.urlopen(f"{endpoint}/json/version", timeout=timeout) as response:
            socket_url = json.load(response)["webSocketDebuggerUrl"]
        self._socket = connect(socket_url, max_size=None, open_timeout=timeout)
        self._ids = itertools.count(1)
        self._session: str | None = None
        self._target: str | None = None
        self.mouse = _Mouse(self)
        self.keyboard = _Keyboard(self)
        self._attach()

    def close(self) -> None:
        self._socket.close()

    def call(self, method: str, params: dict | None = None, *, page: bool = True, timeout: float = 10.0) -> dict:
        message_id = next(self._ids)
        message = {"id": message_id, "method": method, "params": params or {}}
        if page:
            if not self._session:
                raise CdpError("A aba da coleta foi fechada")
            message["sessionId"] = self._session
        self._socket.send(json.dumps(message))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CdpError(f"{method}: tempo esgotado")
            reply = json.loads(self._socket.recv(timeout=remaining))
            if reply.get("method") == "Target.detachedFromTarget" and reply["params"].get("sessionId") == self._session:
                self._session = None
            if reply.get("id") == message_id:
                if "error" in reply:
                    raise CdpError(f"{method}: {reply['error'].get('message')}")
                return reply.get("result", {})

    def _attach(self) -> None:
        targets = self.call("Target.getTargets", page=False)["targetInfos"]
        tabs = [target for target in targets if target["type"] == "page" and not target["url"].startswith("devtools://")]
        if not tabs:
            raise CdpError("Nenhuma aba aberta no navegador da coleta")
        # The collect job drives the browser's first tab.
        self._target = tabs[0]["targetId"]
        self._session = self.call("Target.attachToTarget", {"targetId": self._target, "flatten": True}, page=False)["sessionId"]

    def is_closed(self) -> bool:
        return self._session is None

    @property
    def url(self) -> str:
        return self.call("Target.getTargetInfo", {"targetId": self._target}, page=False)["targetInfo"]["url"]

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result.get("result", {}).get("value")

    def screenshot(self, quality: int = 68, timeout: float = 5.0) -> bytes:
        data = self.call("Page.captureScreenshot", {"format": "jpeg", "quality": quality}, timeout=timeout)["data"]
        return base64.b64decode(data)

    def wait_for_timeout(self, milliseconds: float) -> None:
        time.sleep(milliseconds / 1000)


class _Mouse:
    def __init__(self, page: CdpPage) -> None:
        self._page = page
        self._x = 0.0
        self._y = 0.0
        self._pressed: str | None = None

    def _dispatch(self, kind: str, **params) -> None:
        self._page.call("Input.dispatchMouseEvent", {"type": kind, "x": self._x, "y": self._y, **params})

    def move(self, x: float, y: float) -> None:
        self._x, self._y = float(x), float(y)
        # Drags need the held button on every move so the page sees them as drags.
        self._dispatch("mouseMoved", button=self._pressed or "none", buttons=BUTTON_MASKS.get(self._pressed, 0))

    def down(self, button: str = "left") -> None:
        self._pressed = button
        self._dispatch("mousePressed", button=button, buttons=BUTTON_MASKS[button], clickCount=1)

    def up(self, button: str = "left") -> None:
        self._pressed = None
        self._dispatch("mouseReleased", button=button, buttons=0, clickCount=1)

    def click(self, x: float, y: float, button: str = "left") -> None:
        self.move(x, y)
        self.down(button)
        self.up(button)

    def wheel(self, delta_x: float, delta_y: float) -> None:
        self._dispatch("mouseWheel", deltaX=float(delta_x), deltaY=float(delta_y))


class _Keyboard:
    def __init__(self, page: CdpPage) -> None:
        self._page = page

    def insert_text(self, text: str) -> None:
        self._page.call("Input.insertText", {"text": text})

    def press(self, combo: str) -> None:
        *modifiers, key = combo.split("+") if combo != "+" else ["+"]
        mask = sum(MODIFIER_MASKS.get(name, 0) for name in modifiers)
        if key in SPECIAL_KEYS:
            code, virtual_key, text = SPECIAL_KEYS[key]
        elif len(key) == 1:
            code = f"Key{key.upper()}" if key.isalpha() else ""
            virtual_key = ord(key.upper())
            # With Control/Meta the key is a shortcut, not typed text.
            text = "" if mask & (MODIFIER_MASKS["Control"] | MODIFIER_MASKS["Meta"]) else key
        else:
            return
        event = {"key": key, "code": code, "windowsVirtualKeyCode": virtual_key, "modifiers": mask}
        self._page.call("Input.dispatchKeyEvent", {"type": "keyDown" if text else "rawKeyDown", "text": text, **event})
        self._page.call("Input.dispatchKeyEvent", {"type": "keyUp", **event})
