"""The second use case: calibrating an instrument through its GUI.
Measure, compute the correction in Python, apply it, verify the tolerance, save."""
from pathlib import Path

from conftest import OUT
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui
from toolbridge.workflow import load_workflow, run_workflow

WF = {p.stem: load_workflow(p) for p in (Path(__file__).parent / "data" / "calib").glob("*.yaml")}


def test_calibrate_offset(calib_app):
    s = Session({"app": str(OUT / "calib/DemoCalibrator.exe"), "window": calib_app.window_text(),
                 "controls": scan_ui(calib_app)}, window=calib_app)

    before = run_workflow(s, WF["measure"], setpoint="10.000")
    assert before.ok and abs(before.values["measured"] - 10.31) < 0.01     # uncalibrated: 0.31 V high

    offset = before.values["measured"] - 10.0
    assert run_workflow(s, WF["apply_offset"], offset=f"{offset:.3f}").ok

    after = run_workflow(s, WF["verify"], setpoint="10.000", low="9.99", high="10.01")
    assert after.ok, after.message

    saved = run_workflow(s, WF["save"])
    assert saved.ok and saved.values["confirmation"].startswith("Saved offset 0.31")


def test_out_of_tolerance_is_a_failed_result_not_an_exception(calib_app):
    s = Session({"app": str(OUT / "calib/DemoCalibrator.exe"), "window": calib_app.window_text(),
                 "controls": scan_ui(calib_app)}, window=calib_app)
    r = run_workflow(s, WF["verify"], setpoint="10.000", low="9.99", high="10.01")   # never calibrated
    assert not r.ok and "expected between 9.99 and 10.01" in r.message and r.values["measured"] > 10.2
