# src/toolbridge/runtime.py
"""What generated APIs and the REST server call: find controls robustly and act on them."""
from __future__ import annotations

import ctypes
import difflib
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ToolBridgeError

_BM_CLICK = 0x00F5


def match(root, auto_id=None, title=None, control_type=None) -> list:
    """Descendants of root filtered by automation id / name / control type (pywinauto's
    descendants() only filters by some of these)."""
    out = []
    for w in root.descendants(**({"control_type": control_type} if control_type else {})):
        ei = w.element_info
        if (auto_id is None or ei.automation_id == auto_id) and (title is None or ei.name == title):
            out.append(w)
    return out


@dataclass
class Result:
    ok: bool
    message: str
    seconds: float
    log: list[str] = field(default_factory=list)
    screenshot: str | None = None
    values: dict = field(default_factory=dict)      # what `read` steps stored, e.g. {"measured": 10.02}


class Session:
    def __init__(self, target: dict, deny=(), runs_dir: Path | None = None, window=None):
        self.target, self.deny, self.runs_dir = target, set(deny), Path(runs_dir) if runs_dir else None
        self.window, self.lock, self.proc = window, threading.RLock(), None
        self.controls = {c["id"]: c for c in target["controls"]}

    # ---- app ----
    def start(self):
        from pywinauto import Application, Desktop
        if self.window is not None and self.window.exists():
            return self
        title = self.target.get("window", "")
        wins = [w for w in Desktop(backend="uia").windows() if w.window_text() == title] if title else []
        if wins:
            self.window = Application(backend="uia").connect(handle=wins[0].handle).window(handle=wins[0].handle)
        else:
            self.proc = subprocess.Popen([self.target["app"]])
            app = Application(backend="uia").connect(process=self.proc.pid, timeout=30)
            self.window = app.top_window()
        self.window.wait("ready", timeout=30)
        return self

    # ---- finding ----
    def find(self, cid: str):
        if cid in self.deny:
            raise ToolBridgeError(f"'{cid}' is on the deny-list in toolbridge.yaml; ToolBridge will not touch it")
        c = self.controls.get(cid)
        if not c:
            near = difflib.get_close_matches(cid, self.controls, n=3)
            raise ToolBridgeError(f"No control '{cid}' in the scan. Did you mean: {', '.join(near) or 'nothing close'}?")
        self.start()
        tries = []
        if c["automation_id"]:
            tries.append(dict(auto_id=c["automation_id"], control_type=c["type"]))
        if c["label"]:
            tries.append(dict(title=c["label"], control_type=c["type"]))
        for crit in tries:
            hits = match(self.window, **crit)
            if len(hits) == 1:
                return hits[0]
        node = self.window.wrapper_object()
        try:
            for i in c["path"]:            # indices over all children, as scan_ui stored them
                node = node.children()[i]
            if node.element_info.control_type == c["type"]:
                return node
        except IndexError:
            pass
        present = sorted({w.element_info.name for w in self.window.descendants(control_type=c["type"]) if w.element_info.name})
        raise ToolBridgeError(f"Could not find {c['type']} '{c['label'] or cid}' (automation id "
                              f"'{c['automation_id']}'). {c['type']}s on screen now: {', '.join(present) or 'none'}")

    # ---- actions ----
    def click(self, cid):
        with self.lock:
            w = self.find(cid)
            # UIA Invoke blocks until a modal dialog the button opens is closed, so native
            # buttons get a posted BM_CLICK (returns at once); windowless ones fall back to Invoke.
            if w.handle and ctypes.windll.user32.PostMessageW(w.handle, _BM_CLICK, 0, 0):
                time.sleep(0.3)
                return
            w.invoke()

    def set_text(self, cid, value):
        with self.lock:
            w = self.find(cid)
            try:
                w.set_edit_text(str(value))
            except Exception:
                w.iface_value.SetValue(str(value))

    def select(self, cid, value):
        with self.lock:
            w = self.find(cid)
            try:
                w.select(str(value))
            except Exception as exc:
                raise ToolBridgeError(f"'{value}' is not an option in {cid}") from exc

    def check(self, cid, on: bool = True):
        with self.lock:
            w = self.find(cid)
            if bool(w.get_toggle_state()) != bool(on):
                w.toggle()

    def read(self, cid) -> str:
        with self.lock:
            w = self.find(cid)
            for get in (lambda: w.get_value(), lambda: w.window_text(), lambda: w.element_info.name):
                try:
                    v = get()
                    if v:
                        return str(v)
                except Exception:
                    continue
            return ""

    def keys(self, cid, keys: str):
        """Type keys (pywinauto syntax: '{ENTER}', '^s' = Ctrl+S) into a control, or the window."""
        with self.lock:
            w = self.find(cid) if cid else self.start().window
            w.set_focus()
            w.type_keys(keys, with_spaces=True, set_foreground=True)

    def menu(self, path: str):
        """Open a menu item: 'File > Save as'."""
        with self.lock:
            items = [p.strip() for p in re.split(r">|->", path) if p.strip()]
            try:
                self.start().window.menu_select("->".join(items))
            except Exception as exc:
                raise ToolBridgeError(f"Could not open menu '{path}': {exc}") from exc

    def wait_text(self, cid, pattern: str, timeout_s: float) -> str:
        rx, end, last = re.compile(pattern), time.monotonic() + timeout_s, ""
        while time.monotonic() < end:
            last = self.read(cid)
            if rx.search(last):
                return last
            if self._modal():
                return last
            time.sleep(0.2)
        raise ToolBridgeError(f"Timed out after {timeout_s:.0f} s waiting for {cid} to match '{pattern}' "
                              f"(it says '{last}')")

    def _modal(self):
        from pywinauto import Desktop
        pid = self.window.element_info.process_id
        for w in Desktop(backend="uia").windows(process=pid):
            if w.handle != self.window.handle and w.element_info.class_name == "#32770":
                return w
        for w in self.window.children(control_type="Window"):
            if w.element_info.class_name == "#32770":
                return w
        return None

    def popup(self) -> str | None:
        with self.lock:
            dlg = self._modal()
            if not dlg or match(dlg, auto_id="1148"):   # none, or a file dialog (a file_dialog step handles it)
                return None
            text = " ".join(t.window_text() for t in dlg.descendants(control_type="Text") if t.window_text())
            for name in ("OK", "Cancel", "Close", "Yes"):
                btns = match(dlg, title=name, control_type="Button")
                if btns:
                    btns[0].invoke(); break
            return text or dlg.window_text()

    def file_dialog(self, path: str, timeout_s: float = 10):
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            dlg = self._modal()
            if dlg:
                edit = match(dlg, auto_id="1148", control_type="Edit") or match(dlg, control_type="Edit")
                edit[0].set_edit_text(str(path))
                match(dlg, auto_id="1", control_type="Button")[0].invoke()
                return
            time.sleep(0.2)
        raise ToolBridgeError("No file dialog opened within 10 s")

    def screenshot(self, name: str) -> str | None:
        if not self.runs_dir or self.window is None:
            return None
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.png"
        try:
            self.window.capture_as_image().save(path)
            return str(path)
        except Exception:
            return None
