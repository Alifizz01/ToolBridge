# src/toolbridge/scan/native.py
"""Exported functions of a native DLL, with MSVC C++ names decoded. Listed, never called."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import pefile

_dbghelp = ctypes.WinDLL("dbghelp")
_dbghelp.UnDecorateSymbolName.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32]
_UNDNAME_NO_MS_KEYWORDS = 0x0002        # drops __cdecl, __ptr64, ...


@dataclass
class Export:
    name: str
    ordinal: int
    signature: str


def demangle(name: str) -> str:
    if not name.startswith("?"):
        return name
    buf = ctypes.create_string_buffer(1024)
    n = _dbghelp.UnDecorateSymbolName(name.encode(), buf, len(buf), _UNDNAME_NO_MS_KEYWORDS)
    return buf.value.decode() if n else name


def list_exports(dll: Path) -> list[Export]:
    pe = pefile.PE(str(dll), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    out = []
    for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if hasattr(pe, "DIRECTORY_ENTRY_EXPORT") else []:
        name = s.name.decode() if s.name else f"#{s.ordinal}"
        out.append(Export(name, s.ordinal, demangle(name)))
    pe.close()
    return out
