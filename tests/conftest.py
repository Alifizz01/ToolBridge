# tests/conftest.py
import os
import subprocess
from pathlib import Path

import pytest

# Tests that open the demo apps take over the screen (windows appear and get clicked).
# They run only where that is wanted: CI sets TOOLBRIDGE_UI=1.
UI = os.environ.get("TOOLBRIDGE_UI") == "1"
needs_ui = pytest.mark.skipif(not UI, reason="opens windows on the desktop; set TOOLBRIDGE_UI=1")

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def _start(exe: Path):
    if not UI:
        pytest.skip("opens windows on the desktop; set TOOLBRIDGE_UI=1")
    from pywinauto import Application
    p = subprocess.Popen([str(exe)])
    app = Application(backend="uia").connect(process=p.pid, timeout=20)
    w = app.top_window()
    w.wait("ready", timeout=20)
    return p, w


@pytest.fixture
def net_app():
    p, w = _start(OUT / "net" / "DemoFlasher.exe")
    yield w
    p.kill()


@pytest.fixture
def native_app():
    p, w = _start(OUT / "native" / "DemoFlasherNative.exe")
    yield w
    p.kill()
