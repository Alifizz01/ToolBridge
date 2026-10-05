# tests/test_server.py
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from conftest import OUT
from toolbridge.project import Project
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan
from toolbridge.server import create_app

WF = Path(__file__).parent / "data" / "flash.yaml"


def _client(tmp_path, window):
    proj = Project(tmp_path / "p")
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=window)
    cfg = proj.config; cfg["deny"] = ["btnEraseAll"]; cfg["direct"] = ["FlashCore.FlashService.KnownEcus"]
    proj.save_config(cfg)
    proj.workflows_dir.mkdir(); shutil.copy(WF, proj.workflows_dir)
    s = Session(proj.load_target(), cfg["deny"], proj.runs_dir, window=window)
    return TestClient(create_app(proj, s))


def test_rest_end_to_end(tmp_path, net_app):
    c = _client(tmp_path, net_app)
    assert "DemoFlasher" in c.get("/").text
    assert any(x["id"] == "btnFlash" for x in c.get("/controls").json())
    assert c.get("/workflows").json()["flash"]["params"] == ["ecu", "hex_file"]
    hexf = tmp_path / "a.hex"; hexf.write_bytes(b"x" * 100)
    r = c.post("/workflows/flash", json={"ecu": "ECU2", "hex_file": str(hexf)}).json()
    assert r["ok"] and "ECU2" in r["message"]
    assert c.get("/read/lblStatus").json()["value"].startswith("Done")
    assert c.post("/click/btnEraseAll").status_code == 403
    assert c.post("/direct/FlashCore.FlashService.KnownEcus", json={"args": []}).json()["value"] == ["ECU1", "ECU2", "Gateway"]
    assert c.post("/direct/FlashCore.FlashService.Program", json={"args": []}).status_code == 403
    assert c.post("/workflows/flash", json={"ecu": "ECU1"}).status_code == 400
    rows = c.get("/inspect", params={"folder": str(OUT / "net")}).json()
    assert rows[0]["file"] == "DemoFlasher.exe"
