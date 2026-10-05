"""Record one manual run of a workflow.

A low-level mouse hook only notes which element was under each left click (Windows drops
hooks whose callback is slow). A worker thread does the rest:
  - before each click, every input's value is compared with the last snapshot; changes become
    set / select / check steps (so typing, dropdowns and keyboard use are all captured);
  - clicks on buttons and other non-input controls of the main window become click steps;
  - while a file dialog is open its clicks are ignored; when it closes, the text box whose value
    changed gets a file_dialog step with the chosen path.
review() then turns the raw steps into a parameterised workflow.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import queue
import threading
import time
from pathlib import Path

import yaml

from . import ToolBridgeError
from .project import Project
from .runtime import Session, match

_VALUE_TYPES = {"Edit": "set", "ComboBox": "select", "CheckBox": "check"}


class Recorder:
    def __init__(self, session: Session):
        self.s = session
        self.steps: list[dict] = []
        self._clicks: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._hook = None
        self._pid = session.window.element_info.process_id
        self._in_dialog = False
        self._values = self._snapshot()

    # ---- values ----
    def _snapshot(self) -> dict:
        vals = {}
        for c in self.s.controls.values():
            if c["type"] in _VALUE_TYPES:
                try:
                    w = self.s.find(c["id"])
                    vals[c["id"]] = str(w.get_toggle_state()) if c["type"] == "CheckBox" else self.s.read(c["id"])
                except Exception:
                    pass
        return vals

    def _diff(self, from_dialog: bool = False):
        now = self._snapshot()
        for cid, val in now.items():
            if val == self._values.get(cid):
                continue
            ctype = self.s.controls[cid]["type"]
            if from_dialog and ctype == "Edit":
                self.steps.append({"do": "file_dialog", "value": val})
            else:
                do = _VALUE_TYPES[ctype]
                self.steps.append({"do": do, "target": cid, "value": val if do != "check" else val == "1"})
        self._values = now

    # ---- clicks ----
    def _on_event(self, ev):
        """Runs inside the hook: keep it fast, just note the element under the mouse."""
        if getattr(ev, "current_key", None) == "LButton" and getattr(ev, "event_type", "") == "key up":
            try:
                from pywinauto.uia_defines import IUIA
                self._clicks.put(IUIA().iuia.ElementFromPoint(ctypes.wintypes.POINT(ev.mouse_x, ev.mouse_y)))
            except Exception:
                pass

    def _control_id(self, element) -> str | None:
        from pywinauto.uia_element_info import UIAElementInfo
        node = UIAElementInfo(element)
        if node.process_id != self._pid:
            return None
        while node is not None and node.handle != self.s.window.handle:
            for c in self.s.controls.values():
                if (c["automation_id"] and c["automation_id"] == node.automation_id) or \
                        (c["label"] and c["label"] == node.name and c["type"] == node.control_type):
                    return c["id"]
            parent = node.parent
            if parent is None or parent.process_id != self._pid:
                return None                  # left the app: a top-level window other than the main one
            node = parent
        return None

    def _handle_click(self, element):
        if self._in_dialog:
            return
        cid = self._control_id(element)
        self._diff()
        if cid and self.s.controls[cid]["type"] not in _VALUE_TYPES:
            if cid in self.s.deny:
                print(f"toolbridge: '{cid}' is on the deny-list, so it is not recorded")
                return
            self.steps.append({"do": "click", "target": cid})

    # ---- threads ----
    def _hook_thread(self):
        from pywinauto.win32_hooks import Hook
        self._hook = Hook()
        self._hook.keyboard_id = self._hook.mouse_id = 0    # listen() registers both at exit
        self._hook.handler = self._on_event
        self._hook.hook(keyboard=False, mouse=True)          # returns when stop() unhooks

    def _worker(self):
        import comtypes
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        while not self._stop.is_set():
            try:
                self._handle_click(self._clicks.get(timeout=0.1))
            except queue.Empty:
                pass
            modal = self.s._modal()
            # a file dialog (it has the standard file-name box, id 1148); message boxes do not count
            dialog = modal is not None and bool(match(modal, auto_id="1148"))
            if self._in_dialog and not dialog:
                time.sleep(0.2)              # let the app copy the chosen path into its text box
                self._diff(from_dialog=True)
            self._in_dialog = dialog

    def start(self):
        threading.Thread(target=self._hook_thread, daemon=True).start()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        time.sleep(0.2)                      # hook installed before the user (or a test) clicks

    def stop(self) -> list[dict]:
        time.sleep(0.3)                      # let the last click reach the queue
        if self._hook:
            self._hook.stop()
        while not self._clicks.empty():
            time.sleep(0.05)
        self._stop.set()
        self._worker_thread.join(timeout=5)
        self._diff()
        return list(self.steps)


def review(steps: list[dict], name: str, ask=input, show=print) -> dict:
    params, out = [], []
    for st in steps:
        st = dict(st)
        if st["do"] in ("set", "select", "file_dialog") and st.get("value") not in ("", None):
            p = ask(f"{st['do']} {st.get('target', 'file')} = '{st['value']}'. Parameter name (empty = keep fixed): ").strip()
            if p:
                params.append(p)
                st["value"] = "{" + p + "}"
        out.append(st)
    target = ask("Which control shows the result? (e.g. lblStatus): ").strip()
    if not target:
        raise ToolBridgeError("A workflow needs a control that shows the result")
    ok = ask("Pattern that means success (regex, e.g. ^Done): ").strip() or "."
    out.append({"do": "wait", "target": target, "until": ok})
    show(f"workflow {name}({', '.join(params)}) with {len(out)} steps")
    return {"name": name, "params": params, "timeout_s": 60, "steps": out, "result": {"target": target, "ok": ok}}


def save_workflow(project: Project, wf: dict) -> Path:
    project.workflows_dir.mkdir(parents=True, exist_ok=True)
    path = project.workflows_dir / f"{wf['name']}.yaml"
    path.write_text(yaml.safe_dump(wf, sort_keys=False), encoding="utf-8")
    return path
