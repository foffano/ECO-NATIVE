from backend.app.services.cdp_viewer import _Keyboard, _Mouse


class RecordingPage:
    def __init__(self):
        self.calls = []

    def call(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        return {}


def test_drag_keeps_the_button_pressed_on_moves():
    page = RecordingPage()
    mouse = _Mouse(page)
    mouse.move(10, 20)
    mouse.down()
    mouse.move(30, 20)
    mouse.up()
    events = [(params["type"], params["x"], params["button"], params["buttons"]) for _, params in page.calls]
    assert events == [
        ("mouseMoved", 10.0, "none", 0),
        ("mousePressed", 10.0, "left", 1),
        ("mouseMoved", 30.0, "left", 1),
        ("mouseReleased", 30.0, "left", 0),
    ]


def test_keys_type_text_but_shortcuts_do_not():
    page = RecordingPage()
    keyboard = _Keyboard(page)
    keyboard.press("Enter")
    keyboard.press("Control+a")
    keyboard.press("Unidentified")
    down = [params for _, params in page.calls if params["type"] != "keyUp"]
    assert [(event["type"], event["key"], event["text"], event["modifiers"]) for event in down] == [
        ("keyDown", "Enter", "\r", 0),
        ("rawKeyDown", "a", "", 2),
    ]
    assert len(page.calls) == 4
