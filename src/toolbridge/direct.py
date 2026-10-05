# src/toolbridge/direct.py
"""Call a .NET method found by tracing, without the GUI. Opt-in only (toolbridge.yaml: direct:)."""
from __future__ import annotations

import struct
from pathlib import Path

from . import ToolBridgeError

_loaded = False


def check_bitness(dll_bits: str) -> None:
    py = "x64" if struct.calcsize("P") == 8 else "x86"
    if dll_bits in ("any", "", py):
        return
    raise ToolBridgeError(f"The tool's assembly is {dll_bits} but this Python is {py}; use a {dll_bits} Python "
                          "for direct calls, or the GUI version of this function")


def _load(assembly: Path):
    global _loaded
    if not _loaded:
        try:
            import pythonnet
            pythonnet.load("coreclr")
        except Exception as exc:
            raise ToolBridgeError(f"Direct calls need pythonnet and the .NET runtime: {exc}") from exc
        _loaded = True
    import clr  # noqa: F401  (available after pythonnet.load)
    import System
    return System.Reflection.Assembly.LoadFrom(str(Path(assembly).resolve()))


def call(assembly: Path, full_name: str, *args):
    from .scan.binary import classify
    check_bitness(classify(Path(assembly)).bits)
    asm = _load(assembly)
    type_name, method_name = full_name.rsplit(".", 1)
    t = asm.GetType(type_name)
    if t is None:
        raise ToolBridgeError(f"{type_name} is not in {Path(assembly).name}")
    m = next((x for x in t.GetMethods() if x.Name == method_name and len(x.GetParameters()) == len(args)), None)
    if m is None:
        raise ToolBridgeError(f"{full_name} with {len(args)} arguments is not in {Path(assembly).name}")
    import System
    target = None if m.IsStatic else System.Activator.CreateInstance(t)
    try:
        return m.Invoke(target, list(args) if args else None)
    except Exception as exc:
        inner = getattr(exc, "InnerException", None)
        raise ToolBridgeError(f"{full_name} failed: {inner.Message if inner else exc}") from exc
