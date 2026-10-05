# tests/conftest.py
import subprocess
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def _start(exe: Path):
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
