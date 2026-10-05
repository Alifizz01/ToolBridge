# tests/test_dotnet.py
from pathlib import Path
from toolbridge.scan.dotnet import list_methods, trace_winforms

OUT = Path(__file__).resolve().parents[1] / "demo" / "out" / "net"


def test_lists_public_methods_with_signatures():
    ms = {m.full_name: m for m in list_methods(OUT / "FlashCore.dll")}
    prog = ms["FlashCore.FlashService.Program"]
    assert [p[1] for p in prog.params] == ["path", "ecu", "progress"]
    assert prog.params[0][0] == "string" and prog.returns == "long" and not prog.static
    assert ms["FlashCore.FlashService.KnownEcus"].static


def test_traces_button_to_vendor_method():
    w = {x.control: x for x in trace_winforms(OUT / "DemoFlasher.dll")}
    assert w["btnFlash"].event == "Click" and w["btnFlash"].handler == "btnFlash_Click"
    assert "FlashCore.FlashService.Program" in w["btnFlash"].calls
    assert w["btnBrowse"].calls == []          # only framework calls (OpenFileDialog)
    assert set(w) >= {"btnFlash", "btnBrowse", "btnEraseAll"}
