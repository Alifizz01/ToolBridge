# tests/test_native.py
from pathlib import Path
from toolbridge.scan.native import demangle, list_exports

OUT = Path(__file__).resolve().parents[1] / "demo" / "out" / "native"


def test_demangle_msvc():
    assert demangle("?Flash@@YAHPEBDH@Z") == "int Flash(char const *,int)"
    assert demangle("plain_c") == "plain_c"


def test_lists_demo_exports():
    sigs = {e.signature for e in list_exports(OUT / "flashcore_native.dll")}
    assert "int Flash(char const *,int)" in sigs
    assert any("EraseAll" in s for s in sigs)
