# tests/test_runtime.py
import json
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui


def _session(window, **kw):
    target = {"app": str(OUT / "net/DemoFlasher.exe"), "window": window.window_text(), "controls": scan_ui(window)}
    return Session(target, window=window, **kw)


def test_select_set_click_and_wait(net_app, tmp_path):
    hexf = tmp_path / "app.hex"; hexf.write_bytes(b":00000001FF\n" * 100)
    s = _session(net_app)
    s.select("cmbEcu", "ECU2")
    s.set_text("txtPath", str(hexf))
    s.click("btnFlash")
    assert s.wait_text("lblStatus", r"^(Done|Error)", 20).startswith("Done")


def test_popup_is_caught(net_app):
    s = _session(net_app)
    s.check("chkNoResponse", True)
    s.select("cmbEcu", "ECU1"); s.set_text("txtPath", __file__)
    s.click("btnFlash")
    s.wait_text("lblStatus", r"^Error", 20)
    assert "ECU not responding" in (s.popup() or "")


def test_deny_list(net_app):
    with pytest.raises(ToolBridgeError, match="deny"):
        _session(net_app, deny=["btnEraseAll"]).click("btnEraseAll")


def test_locator_falls_back_to_label(net_app):
    s = _session(net_app)
    for c in s.target["controls"]:
        if c["id"] == "btnFlash":
            c["automation_id"] = "renamedInNewVersion"
    assert s.find("btnFlash").window_text() == "Flash"


def test_unknown_control_lists_alternatives(net_app):
    with pytest.raises(ToolBridgeError, match="btnFlash"):
        _session(net_app).find("btnFlsh")
