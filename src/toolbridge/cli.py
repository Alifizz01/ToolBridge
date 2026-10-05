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


def _session(proj: Project):
    from .runtime import Session
    return Session(proj.load_target(), proj.config["deny"], proj.runs_dir)


def _cmd_run(a) -> int:
    from .workflow import run_workflow
    proj = Project(a.project)
    wfs = proj.workflows()
    if a.name not in wfs:
        raise ToolBridgeError(f"No workflow '{a.name}' (have: {', '.join(wfs) or 'none'})")
    params = dict(kv.split("=", 1) for kv in a.params)
    r = run_workflow(_session(proj), wfs[a.name], **params)
    print(f"{'ok' if r.ok else 'FAILED'}: {r.message} ({r.seconds:.1f} s)")
    if r.screenshot:
        print(f"screenshot: {r.screenshot}")
    return 0 if r.ok else 1


def _cmd_record(a) -> int:
    from .record import Recorder, review, save_workflow
    proj = Project(a.project)
    session = _session(proj).start()
    rec = Recorder(session)
    rec.start()
    input(f"Recording '{a.name}'. Do the workflow in {session.target['window']} now, "
          "then press Enter here... ")
    steps = rec.stop()
    if not steps:
        raise ToolBridgeError("Nothing was recorded (no clicks or value changes in the app)")
    wf = review(steps, a.name)
    print(f"-> {save_workflow(proj, wf)}")
    return 0


def _cmd_generate(a) -> int:
    from .generate import generate
    proj = Project(a.project)
    pkg = generate(proj, a.package)
    print(f"-> {pkg}")
    print()
    print(f'    import sys; sys.path.insert(0, r"{pkg.parent}")')
    print(f"    from {pkg.name} import Tool")
    print("    tool = Tool()   # then tool.<workflow>(...), tool.click_<id>(), tool.read_<id>()")
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
    p = sub.add_parser("run", help="run a recorded workflow: toolbridge run flash ecu=ECU1 hex_file=app.hex")
    p.add_argument("name"); p.add_argument("params", nargs="*")
    p.add_argument("--project", default="toolbridge-project")
    p = sub.add_parser("record", help="record a workflow by doing it once in the app")
    p.add_argument("name"); p.add_argument("--project", default="toolbridge-project")
    p = sub.add_parser("generate", help="write the Python package for this tool")
    p.add_argument("--package"); p.add_argument("--project", default="toolbridge-project")
    a = ap.parse_args(argv)
    try:
        return {"inspect": _cmd_inspect, "scan": _cmd_scan, "run": _cmd_run, "record": _cmd_record, "generate": _cmd_generate}[a.cmd](a)
    except ToolBridgeError as exc:
        print(f"toolbridge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
