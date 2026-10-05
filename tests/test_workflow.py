# tests/test_workflow.py
from pathlib import Path
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui
from toolbridge.workflow import load_workflow, run_workflow

WF = Path(__file__).parent / "data" / "flash.yaml"


def _s(w, tmp_path):
    return Session({"app": str(OUT / "net/DemoFlasher.exe"), "window": w.window_text(),
                    "controls": scan_ui(w)}, window=w, runs_dir=tmp_path / "runs")


def test_flash_ok(net_app, tmp_path):
    hexf = tmp_path / "app.hex"; hexf.write_bytes(b"x" * 2048)
    r = run_workflow(_s(net_app, tmp_path), load_workflow(WF), ecu="Gateway", hex_file=str(hexf))
    assert r.ok and "Done" in r.message and "Gateway" in r.message and r.seconds > 0


def test_flash_error_popup(net_app, tmp_path):
    s = _s(net_app, tmp_path); s.check("chkNoResponse", True)
    r = run_workflow(s, load_workflow(WF), ecu="ECU1", hex_file=__file__)
    assert not r.ok and "ECU not responding" in r.message and r.screenshot


def test_missing_param(net_app, tmp_path):
    with pytest.raises(ToolBridgeError, match="hex_file"):
        run_workflow(_s(net_app, tmp_path), load_workflow(WF), ecu="ECU1")


def test_bad_step_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"; bad.write_text("name: x\nparams: []\nsteps: [{do: explode, target: a}]\nresult: {target: a, ok: x}\n")
    with pytest.raises(ToolBridgeError, match="explode"):
        load_workflow(bad)
