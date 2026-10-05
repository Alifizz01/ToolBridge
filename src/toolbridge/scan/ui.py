# src/toolbridge/scan/ui.py
"""Walk the running app's UI Automation tree and write target.json."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

from .. import ToolBridgeError
from ..project import Project

_SKIP = {"TitleBar", "MenuBar", "ScrollBar", "Thumb"}
_INTERACTIVE = {"Button", "Edit", "ComboBox", "CheckBox", "RadioButton", "List", "ListItem", "MenuItem",
                "Tab", "TabItem", "Text", "ProgressBar", "Slider", "Spinner", "Tree", "TreeItem", "DataGrid"}


def _slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    return s if s and not s[0].isdigit() else ""


def _value(ctrl) -> str:
    try:
        if ctrl.element_info.control_type in ("Edit", "ComboBox"):
            return ctrl.get_value() if hasattr(ctrl, "get_value") else ctrl.window_text()
        if ctrl.element_info.control_type == "CheckBox":
            return str(ctrl.get_toggle_state())
    except Exception:
        pass
    return ""


def scan_ui(window) -> list[dict]:
    out, seen = [], set()
    title = window.window_text()

    def walk(ctrl, path):
        for i, child in enumerate(ctrl.children()):
            ei = child.element_info
            ctype = ei.control_type or "Custom"
            if ctype in _SKIP:
                continue
            p = path + [i]
            if ctype in _INTERACTIVE and not _inside_combo(child):
                aid, label = ei.automation_id or "", ei.name or ""
                base = (aid if aid.isidentifier() else "") or \
                       (f"{_slug(label)}_{ctype.lower()}" if _slug(label) else f"{ctype.lower()}")
                cid, n = base, 2
                while cid in seen:
                    cid, n = f"{base}_{n}", n + 1
                seen.add(cid)
                out.append({"id": cid, "type": ctype, "label": label, "automation_id": aid,
                            "path": p, "window": title, "value": _value(child)})
            walk(child, p)

    walk(window, [])
    return out


def _inside_combo(ctrl) -> bool:
    parent = ctrl.parent()
    return bool(parent) and parent.element_info.control_type == "ComboBox"


def launch(app: Path):
    from pywinauto import Application
    if not Path(app).is_file():
        raise ToolBridgeError(f"{app} does not exist")
    p = subprocess.Popen([str(app)])
    a = Application(backend="uia").connect(process=p.pid, timeout=30)
    w = a.top_window()
    w.wait("ready", timeout=30)
    return p, w


def scan(project: Project, app: Path, dlls: list[Path], window=None) -> dict:
    from .binary import classify
    app, dlls = Path(app).resolve(), [Path(d).resolve() for d in dlls]
    proc = None
    if window is None:
        proc, window = launch(app)
    try:
        target = {"app": str(app), "window": window.window_text(), "controls": scan_ui(window),
                  "dotnet": {"wiring": [], "methods": []}, "native": {"exports": []}}
    finally:
        if proc:
            proc.kill()
    main = classify(Path(app))
    managed = [Path(app).with_suffix(".dll")] if main.kind == "apphost" else ([Path(app)] if main.kind == "dotnet" else [])
    for dll in managed + [Path(d) for d in dlls]:
        kind = classify(dll).kind
        if kind == "dotnet":
            from .dotnet import list_methods, trace_winforms
            target["dotnet"]["wiring"] += [asdict(w) for w in trace_winforms(dll)]
            target["dotnet"]["methods"] += [m.signature for m in list_methods(dll)]
            target["dotnet"].setdefault("assemblies", []).append(str(dll))
        elif kind == "native":
            from .native import list_exports
            target["native"]["exports"] += [{"dll": dll.name, **asdict(e)} for e in list_exports(dll)]
    project.target_path.write_text(json.dumps(target, indent=2), encoding="utf-8")
    cfg = project.config
    cfg["app"] = str(app)
    project.save_config(cfg)
    return target
