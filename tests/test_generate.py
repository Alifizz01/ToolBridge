# tests/test_generate.py
import importlib, json, shutil, sys
from conftest import OUT
from toolbridge.generate import generate
from toolbridge.project import Project
from toolbridge.scan.ui import scan

WF = __import__("pathlib").Path(__file__).parent / "data" / "flash.yaml"


def test_generated_api_runs_workflow_and_direct(tmp_path, net_app):
    proj = Project(tmp_path / "proj")
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=net_app)
    cfg = proj.config; cfg["deny"] = ["btnEraseAll"]; cfg["direct"] = ["FlashCore.FlashService.KnownEcus"]
    proj.save_config(cfg)
    proj.workflows_dir.mkdir(); shutil.copy(WF, proj.workflows_dir)
    pkg = generate(proj)
    assert pkg.name == "demoflasher_api"
    sys.path.insert(0, str(pkg.parent))
    api = importlib.import_module("demoflasher_api")
    assert "flash" in api.WORKFLOWS
    tool = api.Tool()
    assert not hasattr(tool, "click_btnEraseAll") and hasattr(tool, "click_btnFlash")
    assert list(tool.KnownEcus_direct()) == ["ECU1", "ECU2", "Gateway"]
    hexf = tmp_path / "a.hex"; hexf.write_bytes(b"x" * 1024)
    r = tool.flash(ecu="ECU1", hex_file=str(hexf))
    assert r.ok, r.message
    src = (pkg / "__init__.py").read_text()
    compile(src, "api", "exec")
