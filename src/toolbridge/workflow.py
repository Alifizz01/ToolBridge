"""Workflow YAML: load, validate, replay.

A workflow is a list of steps. Built-in actions cover what GUI tools have in common;
a project can add its own in steps.py (see register_step). Values in a step can use
{param} for the workflow's parameters and {name} for anything an earlier `read` stored.
"""
from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path
from typing import Callable

import yaml

from . import ToolBridgeError
from .runtime import Result, Session

StepFn = Callable[[Session, dict, dict], None]     # (session, step, context) -> None, raise to fail
_STEPS: dict[str, StepFn] = {}
_FILLED = ("value", "target", "min", "max")          # not regexes: "\d{3}" stays as written
_NEEDS_TARGET = {"click", "set", "select", "check", "wait", "read"}
_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?")


def register_step(name: str):
    """Add a custom action, usable as `- {do: name, ...}` in workflows.

        # <project>/steps.py
        from toolbridge.workflow import register_step

        @register_step("zero_sensor")
        def zero_sensor(session, step, ctx):
            session.click("btnZero")
            session.wait_text("lblStatus", "^Zeroed", 30)
    """
    def deco(fn: StepFn) -> StepFn:
        _STEPS[name] = fn
        return fn
    return deco


def number(text: str) -> float:
    """First number in a text: '10,37 V' -> 10.37 (decimal comma accepted)."""
    m = _NUMBER.search(str(text))
    if not m:
        raise ToolBridgeError(f"No number in '{text}'")
    return float(m.group().replace(",", "."))


# ---- built-in steps ----
def _timeout(st, ctx):
    return float(st.get("timeout_s", ctx["_timeout_s"]))


@register_step("click")
def _click(s, st, ctx): s.click(st["target"])


@register_step("set")
def _set(s, st, ctx): s.set_text(st["target"], st.get("value", ""))


@register_step("select")
def _select(s, st, ctx): s.select(st["target"], st["value"])


@register_step("check")
def _check(s, st, ctx): s.check(st["target"], str(st.get("value", True)).lower() in ("1", "true", "yes", "on"))


@register_step("file_dialog")
def _file_dialog(s, st, ctx): s.file_dialog(st["value"])


@register_step("wait")
def _wait(s, st, ctx): s.wait_text(st["target"], st["until"], _timeout(st, ctx))


@register_step("read")
def _read(s, st, ctx):
    text = s.read(st["target"])
    ctx[st.get("save_as", st["target"])] = number(text) if st.get("as") == "number" else text


@register_step("expect")
def _expect(s, st, ctx):
    """Check a value: of a control (target) or of something read earlier (value: "{name}").
    match: regex, and/or min / max for numbers."""
    text = s.read(st["target"]) if "target" in st else str(st.get("value", ""))
    what = st.get("target") or st.get("value")
    if "match" in st and not re.search(st["match"], text):
        raise ToolBridgeError(f"{what} is '{text}', expected to match '{st['match']}'")
    if "min" in st or "max" in st:
        v = number(text)
        lo, hi = float(st.get("min", "-inf")), float(st.get("max", "inf"))
        if not lo <= v <= hi:
            raise ToolBridgeError(f"{what} is {v:g}, expected between {lo:g} and {hi:g}")


@register_step("keys")
def _keys(s, st, ctx): s.keys(st.get("target"), st["value"])


@register_step("menu")
def _menu(s, st, ctx): s.menu(st["value"])


@register_step("sleep")
def _sleep(s, st, ctx): time.sleep(float(st["value"]))


# ---- loading ----
def load_steps(path: Path) -> None:
    """Import a project's steps.py so its @register_step actions exist."""
    if path.is_file():
        spec = importlib.util.spec_from_file_location(f"toolbridge_steps_{abs(hash(str(path)))}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def load_workflow(path: Path) -> dict:
    path = Path(path)
    wf = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("name", "steps"):
        if key not in wf:
            raise ToolBridgeError(f"{path.name}: missing '{key}'")
    wf.setdefault("params", [])
    wf.setdefault("timeout_s", 60)
    for i, st in enumerate(wf["steps"], 1):
        if st.get("do") not in _STEPS:
            raise ToolBridgeError(f"{path.name} step {i}: unknown action '{st.get('do')}' "
                                  f"(available: {', '.join(sorted(_STEPS))}; add your own in steps.py)")
        if st["do"] in _NEEDS_TARGET and "target" not in st:
            raise ToolBridgeError(f"{path.name} step {i}: '{st['do']}' needs a target")
    return wf


def _fill(value, ctx: dict):
    if not isinstance(value, str):
        return value
    try:
        return value.format_map(ctx)
    except KeyError as exc:
        raise ToolBridgeError(f"'{value}' uses {exc}, which is neither a parameter nor read earlier") from exc


# ---- running ----
def run_workflow(session: Session, wf: dict, **params) -> Result:
    missing = [p for p in wf["params"] if p not in params]
    extra = [p for p in params if p not in wf["params"]]
    if missing or extra:
        raise ToolBridgeError(f"{wf['name']}() needs {', '.join(wf['params']) or 'no parameters'}"
                              f"{'; missing ' + ', '.join(missing) if missing else ''}"
                              f"{'; unknown ' + ', '.join(extra) if extra else ''}")
    ctx = {**params, "_timeout_s": wf["timeout_s"]}
    log, t0 = [], time.monotonic()

    def values():
        return {k: v for k, v in ctx.items() if not k.startswith("_") and k not in params}

    def fail(msg):
        return Result(False, msg, time.monotonic() - t0, log, session.screenshot(wf["name"]), values())

    with session.lock:
        try:
            for st in wf["steps"]:
                st = {k: _fill(v, ctx) if k in _FILLED else v for k, v in st.items()}
                log.append(" ".join(str(st[k]) for k in ("do", "target", "value") if st.get(k) not in (None, "")))
                _STEPS[st["do"]](session, st, ctx)
                pop = session.popup()
                if pop:
                    log.append(f"popup: {pop}")
                    return fail(pop)
            if "result" in wf:                       # optional final check on a control's text
                text = session.read(wf["result"]["target"])
                log.append(f"result: {text}")
                if not re.search(wf["result"]["ok"], text):
                    return fail(text)
                return Result(True, text, time.monotonic() - t0, log, None, values())
            return Result(True, "done", time.monotonic() - t0, log, None, values())
        except ToolBridgeError as exc:
            log.append(f"error: {exc}")
            return fail(str(exc))
