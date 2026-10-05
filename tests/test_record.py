# tests/test_record.py
import threading, time
from conftest import OUT
from toolbridge.record import Recorder, review
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui


def test_records_select_type_click(net_app, tmp_path):
    s = Session({"app": str(OUT / "net/DemoFlasher.exe"), "window": net_app.window_text(),
                 "controls": scan_ui(net_app)}, window=net_app)
    net_app.set_focus()
    rec = Recorder(s); rec.start()
    combo = net_app.child_window(auto_id="cmbEcu", control_type="ComboBox")
    combo.select("ECU2")
    edit = net_app.child_window(auto_id="txtPath", control_type="Edit")
    edit.click_input(); edit.type_keys(r"C:\fw\app.hex", with_spaces=True)
    time.sleep(0.5)       # a person does not click within microseconds of the last keystroke
    net_app.child_window(auto_id="btnFlash", control_type="Button").click_input()
    time.sleep(0.5)
    steps = rec.stop()
    kinds = [(st["do"], st.get("target")) for st in steps]
    assert ("select", "cmbEcu") in kinds and ("set", "txtPath") in kinds and kinds[-1] == ("click", "btnFlash")
    assert next(st for st in steps if st["do"] == "set")["value"] == r"C:\fw\app.hex"


def test_review_makes_params_and_result():
    steps = [{"do": "select", "target": "cmbEcu", "value": "ECU2"},
             {"do": "set", "target": "txtPath", "value": r"C:\fw\app.hex"},
             {"do": "click", "target": "btnFlash"}]
    answers = iter(["ecu", "hex_file", "lblStatus", "^Done"])
    wf = review(steps, name="flash", ask=lambda q: next(answers), show=lambda *_: None)
    assert wf["params"] == ["ecu", "hex_file"]
    assert wf["steps"][0]["value"] == "{ecu}" and wf["steps"][-1] == {"do": "wait", "target": "lblStatus", "until": "^Done"}
    assert wf["result"] == {"target": "lblStatus", "ok": "^Done"}
