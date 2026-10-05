"""Workflow engine without a GUI: a fake session stands in for the app."""
import threading
from pathlib import Path

import pytest
import yaml

from toolbridge import ToolBridgeError
from toolbridge.project import Project
from toolbridge.workflow import load_workflow, number, run_workflow


class FakeSession:
    """Controls are just a dict of texts; clicking 'btnMeasure' 'measures'."""

    def __init__(self, texts):
        self.texts, self.lock, self.clicked = dict(texts), threading.RLock(), []

    def read(self, cid): return self.texts[cid]
    def set_text(self, cid, v): self.texts[cid] = str(v)
    def click(self, cid): self.clicked.append(cid)
    def popup(self): return None
    def screenshot(self, name): return None


def _wf(tmp_path, steps, params=()):
    p = tmp_path / "wf.yaml"
    p.write_text(yaml.safe_dump({"name": "wf", "params": list(params), "steps": steps}))
    return load_workflow(p)


def test_number_reads_units_and_decimal_comma():
    assert number("10,37 V") == 10.37 and number("offset: -0.25 mV") == -0.25 and number("1e-3 A") == 0.001
    with pytest.raises(ToolBridgeError):
        number("no value")


def test_read_then_expect_within_tolerance(tmp_path):
    wf = _wf(tmp_path, [{"do": "click", "target": "btnMeasure"},
                        {"do": "read", "target": "lblMeasured", "save_as": "measured", "as": "number"},
                        {"do": "expect", "value": "{measured}", "min": "{lo}", "max": 10.05}], params=["lo"])
    r = run_workflow(FakeSession({"lblMeasured": "10,02 V"}), wf, lo=9.95)
    assert r.ok and r.values == {"measured": 10.02}
    r = run_workflow(FakeSession({"lblMeasured": "10,31 V"}), wf, lo=9.95)
    assert not r.ok and r.message == "measured is 10.31, expected between 9.95 and 10.05"


def test_out_of_tolerance_fails_with_the_numbers(tmp_path):
    wf = _wf(tmp_path, [{"do": "expect", "target": "lblMeasured", "min": 9.95, "max": 10.05}])
    r = run_workflow(FakeSession({"lblMeasured": "10.31 V"}), wf)
    assert not r.ok and "10.31" in r.message and "9.95" in r.message


def test_values_flow_into_later_steps(tmp_path):
    wf = _wf(tmp_path, [{"do": "read", "target": "lblSerial", "save_as": "serial"},
                        {"do": "set", "target": "txtLog", "value": "calibrated {serial}"}])
    s = FakeSession({"lblSerial": "SN-0042", "txtLog": ""})
    assert run_workflow(s, wf).ok and s.texts["txtLog"] == "calibrated SN-0042"


def test_regex_fields_are_not_templated(tmp_path):
    wf = _wf(tmp_path, [{"do": "expect", "target": "lblSerial", "match": r"^SN-\d{4}$"}])
    assert run_workflow(FakeSession({"lblSerial": "SN-0042"}), wf).ok


def test_unknown_variable_is_explained(tmp_path):
    wf = _wf(tmp_path, [{"do": "set", "target": "txtLog", "value": "{nope}"}])
    r = run_workflow(FakeSession({"txtLog": ""}), wf)
    assert not r.ok and "nope" in r.message


def test_custom_step_from_project_steps_py(tmp_path):
    proj = Project(tmp_path)
    (tmp_path / "steps.py").write_text(
        "from toolbridge.workflow import register_step\n"
        "@register_step('zero_sensor')\n"
        "def zero(session, step, ctx):\n"
        "    session.click('btnZero'); ctx['zeroed'] = True\n")
    proj.workflows_dir.mkdir()
    (proj.workflows_dir / "z.yaml").write_text("name: z\nsteps:\n  - {do: zero_sensor}\n")
    s = FakeSession({})
    r = run_workflow(s, proj.workflows()["z"])
    assert r.ok and s.clicked == ["btnZero"] and r.values == {"zeroed": True}


def test_unknown_action_lists_the_available_ones(tmp_path):
    with pytest.raises(ToolBridgeError, match="steps.py"):
        _wf(tmp_path, [{"do": "explode"}])
