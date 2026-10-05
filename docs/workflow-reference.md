# Workflow files

A workflow is one YAML file in `<project>/workflows/`. `toolbridge record NAME` writes one for you;
this page is for reading and editing them.

```yaml
name: verify                    # becomes tool.verify(...) and POST /workflows/verify
params: [setpoint, low, high]   # arguments; use them as {setpoint}
timeout_s: 60                   # default for every wait in this workflow
steps:
  - {do: set,    target: txtSetpoint, value: "{setpoint}"}
  - {do: click,  target: btnMeasure}
  - {do: wait,   target: lblStatus, until: "^Ready"}
  - {do: read,   target: lblMeasured, save_as: measured, as: number}
  - {do: expect, value: "{measured}", min: "{low}", max: "{high}"}
result: {target: lblStatus, ok: "^Ready"}   # optional final check
```

`target` is a control id from the scan (`target.json`, or the Controls tab in Studio).

## Built-in steps

| step | fields | what it does |
|---|---|---|
| `click` | `target` | presses a button, check box, menu item, tab… |
| `set` | `target`, `value` | replaces the text of an edit box |
| `select` | `target`, `value` | picks an entry of a drop-down or list by its text |
| `check` | `target`, `value` (true/false) | sets a check box |
| `file_dialog` | `value` | fills the open/save dialog the previous click opened and confirms it |
| `wait` | `target`, `until` (regex), `timeout_s` | waits until the control's text matches |
| `read` | `target`, `save_as`, `as: number` | stores the control's text (or the first number in it) for later steps and for `Result.values` |
| `expect` | `target` **or** `value`, `match` (regex), `min`, `max` | fails the workflow unless the text matches / the number is in range |
| `keys` | `target` (optional), `value` | types keys, pywinauto syntax: `{ENTER}`, `^s` = Ctrl+S, `%f` = Alt+F |
| `menu` | `value` | opens a menu item: `File > Export > CSV` |
| `sleep` | `value` (seconds) | waits a fixed time; prefer `wait` |

Numbers are read the way instruments print them: `"10,37 V"` → `10.37`, `"-0.25 mV"` → `-0.25`,
`"1e-3 A"` → `0.001`.

Only `value`, `target`, `min` and `max` are filled with `{...}`; regexes such as `until: "\d{3}"` are
used as written.

## Results

Every run returns the same thing, from Python and from REST:

```python
r = tool.verify(setpoint="10.000", low="9.99", high="10.01")
r.ok          # False if any step failed, a popup appeared, or `result` did not match
r.message     # what went wrong, or the result text
r.values      # {"measured": 10.002}: everything `read` stored
r.seconds, r.log, r.screenshot   # screenshot only on failure, saved in <project>/runs/
```

A popup that the workflow did not expect (an error message box, "Are you sure?") is read, closed,
and returned as `ok=False` with its text, so a test never hangs on a dialog.

## Your own steps

Anything specific to your tool goes in `<project>/steps.py`. It is loaded with the workflows.

```python
from toolbridge.workflow import register_step, number

@register_step("zero_sensor")
def zero_sensor(session, step, ctx):
    session.click("btnZero")
    session.wait_text("lblStatus", "^Zeroed", float(step.get("timeout_s", 30)))

@register_step("read_table_cell")
def read_table_cell(session, step, ctx):
    grid = session.find(step["target"])                       # the pywinauto wrapper
    ctx[step["save_as"]] = grid.get_item(int(step["row"]), int(step["column"])).window_text()
```

```yaml
steps:
  - {do: zero_sensor, timeout_s: 45}
  - {do: read_table_cell, target: gridResults, row: 0, column: 3, save_as: gain}
```

A step fails by raising `toolbridge.ToolBridgeError("one sentence")`. `session` gives you `find`,
`click`, `set_text`, `select`, `check`, `read`, `wait_text`, `keys`, `menu`, `popup` and `screenshot`.

## Loops and decisions

Keep workflows straight lines and put logic in Python on top of the generated API. A calibration
that converges:

```python
tool = Tool()
offset = 0.0
for attempt in range(5):
    r = tool.measure(setpoint="10.000")
    error = r.values["measured"] - 10.0
    if abs(error) < 0.005:
        break
    offset += error
    tool.apply_offset(offset=f"{offset:.4f}")
tool.save()
```
