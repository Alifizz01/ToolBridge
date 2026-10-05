# tests/test_binary.py
from pathlib import Path
from toolbridge.scan.binary import classify

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_dotnet_library():
    b = classify(OUT / "net/FlashCore.dll")
    assert b.kind == "dotnet" and b.bits == "any"


def test_dotnet_app_imports_flashcore():
    b = classify(OUT / "net/DemoFlasher.dll")
    assert "FlashCore" in b.managed_imports


def test_apphost_exe():
    assert classify(OUT / "net/DemoFlasher.exe").kind == "apphost"


def test_native_exe_imports_its_dll():
    b = classify(OUT / "native/DemoFlasherNative.exe")
    assert b.kind == "native" and b.bits == "x64"
    assert "flashcore_native.dll" in b.native_imports


def test_not_pe(tmp_path):
    f = tmp_path / "x.dll"; f.write_bytes(b"hello")
    assert classify(f).kind == "not-pe"
