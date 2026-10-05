# src/toolbridge/cli.py
"""toolbridge: inspect a tool's folder, scan its UI, record workflows, generate and serve its API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ToolBridgeError, __version__
from .project import Project


def _cmd_inspect(a) -> int:
    from .scan.inspect import functions_of, inspect_folder
    proj = Project(a.project)
    folder = Path(a.folder)
    if a.dll:
        path = next(iter(folder.rglob(a.dll)), None)
        if not path:
            raise ToolBridgeError(f"{a.dll} is not in {folder}")
        for f in functions_of(path):
            print(f"  {f}")
        cfg = proj.config
        if str(path) not in cfg["dlls"]:
            cfg["dlls"].append(str(path))
        proj.save_config(cfg)
        print(f"\n{path.name} added to {proj.config_path}")
        return 0
    rows = inspect_folder(folder, Path(a.app) if a.app else None, a.all)
    print(f"{'file':<34}{'kind':<9}{'bit':<6}{'used by app':<26}functions")
    for r in rows:
        print(f"{r.path.name:<34}{r.kind:<9}{r.bits:<6}{r.used or '-':<26}{r.functions or '-'}")
    print("\nPick one:  toolbridge inspect FOLDER --dll NAME.dll")
    return 0


def _cmd_scan(a) -> int:
    from .scan.ui import scan
    proj = Project(a.project)
    dlls = [Path(d) for d in (a.dll or proj.config["dlls"])]
    t = scan(proj, Path(a.app), dlls)
    print(f"{len(t['controls'])} controls in '{t['window']}', "
          f"{len(t['dotnet']['wiring'])} traced handlers, {len(t['native']['exports'])} native exports")
    for w in t["dotnet"]["wiring"]:
        if w["calls"]:
            print(f"  {w['control']}.{w['event']} -> {', '.join(w['calls'])}")
    print(f"-> {proj.target_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="toolbridge", description=__doc__)
    ap.add_argument("--version", action="version", version=f"toolbridge {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="list the DLLs in a tool's folder and what is inside them")
    p.add_argument("folder"); p.add_argument("--dll"); p.add_argument("--app")
    p.add_argument("--all", action="store_true", help="also show runtime/system DLLs")
    p.add_argument("--project", default="toolbridge-project")
    p = sub.add_parser("scan", help="start the app and list every control")
    p.add_argument("app"); p.add_argument("--dll", action="append")
    p.add_argument("--project", default="toolbridge-project")
    a = ap.parse_args(argv)
    try:
        return {"inspect": _cmd_inspect, "scan": _cmd_scan}[a.cmd](a)
    except ToolBridgeError as exc:
        print(f"toolbridge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
