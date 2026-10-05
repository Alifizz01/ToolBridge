# tests/test_inspect.py
from pathlib import Path
from toolbridge.scan.inspect import functions_of, inspect_folder
from toolbridge.cli import main

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_net_folder_ranks_vendor_dll_first_and_hides_runtime():
    rows = inspect_folder(OUT / "net")
    names = [r.path.name for r in rows]
    assert names[0] == "DemoFlasher.exe"
    fc = next(r for r in rows if r.path.name == "FlashCore.dll")
    assert fc.used == "direct" and fc.kind == "dotnet" and fc.functions >= 2
    assert not any(r.runtime for r in rows)
    assert len(inspect_folder(OUT / "net", show_runtime=True)) >= len(rows)


def test_native_folder_marks_used_dll():
    rows = inspect_folder(OUT / "native")
    dll = next(r for r in rows if r.path.name == "flashcore_native.dll")
    assert dll.used == "direct" and dll.functions == 3


def test_functions_of():
    assert any("Program(" in f for f in functions_of(OUT / "net/FlashCore.dll"))


def test_cli_inspect_and_pick(tmp_path, capsys):
    assert main(["inspect", str(OUT / "net"), "--project", str(tmp_path / "p")]) == 0
    assert "FlashCore.dll" in capsys.readouterr().out
    assert main(["inspect", str(OUT / "net"), "--dll", "FlashCore.dll", "--project", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "Program(string path" in out
    assert "FlashCore.dll" in (tmp_path / "p" / "toolbridge.yaml").read_text()
