# src/toolbridge/scan/binary.py
"""What is this file: .NET or native, 32 or 64 bit, and what does it load?"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import dnfile
import pefile

_MACHINE = {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}
_COR_ILONLY, _COR_32BITREQUIRED = 0x1, 0x2


@dataclass
class BinaryInfo:
    path: Path
    kind: str
    bits: str
    managed_imports: list[str] = field(default_factory=list)
    native_imports: list[str] = field(default_factory=list)


def classify(path: Path) -> BinaryInfo:
    path = Path(path)
    try:
        pe = dnfile.dnPE(str(path), fast_load=False)
    except (pefile.PEFormatError, OSError):
        return BinaryInfo(path, "not-pe", "")
    try:
        bits = _MACHINE.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
        native = sorted({e.dll.decode(errors="replace").lower()
                         for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])})
        if pe.net is not None and pe.net.mdtables is not None:
            flags = pe.net.struct.Flags
            if bits == "x86" and flags & _COR_ILONLY and not flags & _COR_32BITREQUIRED:
                bits = "any"
            refs = [str(r.Name) for r in (pe.net.mdtables.AssemblyRef or [])]
            return BinaryInfo(path, "dotnet", bits, refs, native)
        twin = path.with_suffix(".dll")
        if path.suffix.lower() == ".exe" and twin.is_file() and classify(twin).kind == "dotnet":
            return BinaryInfo(path, "apphost", bits, [twin.stem], native)
        return BinaryInfo(path, "native", bits, [], native)
    finally:
        pe.close()
