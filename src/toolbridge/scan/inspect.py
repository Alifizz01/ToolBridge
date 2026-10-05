# src/toolbridge/scan/inspect.py
"""Folder scan: which DLLs does the app actually use, and what is inside them."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .binary import BinaryInfo, classify

_RUNTIME = re.compile(r"^(api-ms-|ext-ms-|vcruntime|msvcp|ucrtbase|concrt|mfc\d|kernel32|user32|gdi32|advapi32|"
                      r"comdlg32|shell32|ole32|oleaut32|comctl32|ws2_32|ntdll|bcrypt|crypt32|version|"
                      r"system\.|microsoft\.|mscorlib|netstandard|windowsbase|presentation|newtonsoft|"
                      r"qt\d|hostfxr|hostpolicy|coreclr|clrjit|mscordaccore|d3dcompiler)", re.I)


@dataclass
class Entry:
    path: Path
    kind: str
    bits: str
    used: str
    runtime: bool
    functions: int


def functions_of(path: Path) -> list[str]:
    info = classify(path)
    if info.kind == "dotnet":
        from .dotnet import list_methods
        return [m.signature for m in list_methods(path)]
    if info.kind == "native":
        from .native import list_exports
        return [e.signature for e in list_exports(path)]
    return []


def _pick_app(folder: Path) -> Path | None:
    exes = sorted(folder.glob("*.exe"))
    return exes[0] if exes else None


def inspect_folder(folder: Path, app: Path | None = None, show_runtime: bool = False) -> list[Entry]:
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".dll", ".exe"))
    infos: dict[str, BinaryInfo] = {p.name.lower(): classify(p) for p in files}
    by_stem = {p.stem.lower(): p.name.lower() for p in files if p.suffix.lower() == ".dll"}
    app = Path(app) if app else _pick_app(folder)
    used: dict[str, str] = {}
    if app:
        used[app.name.lower()] = "app"
        frontier = [(app.name.lower(), "")]
        twin = infos.get(app.name.lower())
        if twin and twin.kind == "apphost":       # .NET apphost: the real app is <name>.dll
            used[(app.stem + ".dll").lower()] = "app"
            frontier.append(((app.stem + ".dll").lower(), ""))
        while frontier:
            name, via = frontier.pop(0)
            info = infos.get(name)
            if not info:
                continue
            deps = list(info.native_imports) + [by_stem.get(m.lower(), "") for m in info.managed_imports]
            for dep in filter(None, deps):
                if dep in infos and dep not in used:
                    used[dep] = "direct" if used.get(name) == "app" else f"via {infos[name].path.name}"
                    frontier.append((dep, name))
    rows = []
    for key, info in infos.items():
        if info.kind == "not-pe":
            continue
        runtime = bool(_RUNTIME.match(info.path.name))
        if runtime and not show_runtime:
            continue
        n = len(functions_of(info.path)) if info.kind in ("dotnet", "native") and info.path.suffix.lower() == ".dll" else 0
        rows.append(Entry(info.path, info.kind, info.bits, used.get(key, ""), runtime, n))
    order = {"app": 0, "direct": 1}
    rows.sort(key=lambda r: (order.get(r.used, 2 if r.used else 3), r.path.suffix.lower() != ".exe", r.path.name.lower()))
    return rows
