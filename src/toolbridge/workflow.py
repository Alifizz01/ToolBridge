# src/toolbridge/workflow.py
"""Workflow YAML: load, validate, replay."""
from __future__ import annotations

import re
import time
from pathlib import Path

import yaml

from . import ToolBridgeError
from .runtime import Result, Session

ACTIONS = {"click", "set", "select", "check", "file_dialog", "wait"}


def load_workflow(path: Path) -> dict:
    wf = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for key in ("name", "steps", "result"):
        if key not in wf:
            raise ToolBridgeError(f"{path.name}: missing '{key}'")
    wf.setdefault("params", [])
    wf.setdefault("timeout_s", 60)
    for i, st in enumerate(wf["steps"], 1):
        if st.get("do") not in ACTIONS:
            raise ToolBridgeError(f"{path.name} step {i}: unknown action '{st.get('do')}' (use {', '.join(sorted(ACTIONS))})")
        if st["do"] != "file_dialog" and "target" not in st:
            raise ToolBridgeError(f"{path.name} step {i}: '{st['do']}' needs a target")
    return wf


def _fill(value, params: dict):
    return str(value).format(**params) if isinstance(value, str) else value


def run_workflow(session: Session, wf: dict, **params) -> Result:
    missing = [p for p in wf["params"] if p not in params]
    extra = [p for p in params if p not in wf["params"]]
    if missing or extra:
        raise ToolBridgeError(f"{wf['name']}() needs {', '.join(wf['params']) or 'no parameters'}"
                              f"{'; missing ' + ', '.join(missing) if missing else ''}"
                              f"{'; unknown ' + ', '.join(extra) if extra else ''}")
    log, t0 = [], time.monotonic()

    def fail(msg):
        return Result(False, msg, time.monotonic() - t0, log, session.screenshot(wf["name"]))

    with session.lock:
        try:
            for st in wf["steps"]:
                do, tgt, val = st["do"], st.get("target"), _fill(st.get("value", ""), params)
                log.append(f"{do} {tgt or ''} {val}".strip())
                if do == "click":
                    session.click(tgt)
                elif do == "set":
                    session.set_text(tgt, val)
                elif do == "select":
                    session.select(tgt, val)
                elif do == "check":
                    session.check(tgt, str(val).lower() in ("1", "true", "yes", "on"))
                elif do == "file_dialog":
                    session.file_dialog(val)
                elif do == "wait":
                    session.wait_text(tgt, st["until"], st.get("timeout_s", wf["timeout_s"]))
                pop = session.popup()
                if pop:
                    log.append(f"popup: {pop}")
                    return fail(pop)
            text = session.read(wf["result"]["target"])
            log.append(f"result: {text}")
            if re.search(wf["result"]["ok"], text):
                return Result(True, text, time.monotonic() - t0, log)
            return fail(text)
        except ToolBridgeError as exc:
            log.append(f"error: {exc}")
            return fail(str(exc))
