# tests/test_scan_ui.py
import json
from conftest import OUT
from toolbridge.project import Project
from toolbridge.scan.ui import scan, scan_ui


def test_net_controls_have_automation_ids(net_app):
    ids = {c["id"]: c for c in scan_ui(net_app)}
    assert {"cmbEcu", "txtPath", "btnBrowse", "btnFlash", "lblStatus", "chkNoResponse"} <= set(ids)
    assert ids["btnFlash"]["type"] == "Button" and ids["btnFlash"]["label"] == "Flash"


def test_native_controls_get_readable_ids(native_app):
    ids = {c["id"] for c in scan_ui(native_app)}
    assert "flash_button" in ids and "browse_button" in ids


def test_scan_writes_target_with_wiring(tmp_path, net_app):
    proj = Project(tmp_path)
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=net_app)
    t = json.loads(proj.target_path.read_text())
    w = {x["control"]: x for x in t["dotnet"]["wiring"]}
    assert "FlashCore.FlashService.Program" in w["btnFlash"]["calls"]
    assert any(m.startswith("FlashCore.FlashService.Program(") for m in t["dotnet"]["methods"])
