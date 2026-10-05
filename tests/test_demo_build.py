# tests/test_demo_build.py
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_demo_binaries_exist():
    for rel in ["net/DemoFlasher.exe", "net/DemoFlasher.dll", "net/FlashCore.dll",
                "native/DemoFlasherNative.exe", "native/flashcore_native.dll"]:
        assert (OUT / rel).is_file(), f"run demo/build.ps1 first: missing {rel}"
