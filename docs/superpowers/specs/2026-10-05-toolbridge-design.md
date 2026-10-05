# ToolBridge: design

Date: 2026-10-05 · Status: draft for review

## Problem

Test benches have to drive Windows tools (flashers, configurators, calibration tools) that have no
API. Today a person clicks through them, or a brittle script clicks at pixel positions. ToolBridge
analyses the tool and **generates an API for it**: a Python package and a REST server, so test cases
(pytest, CI, CANoe, anything that speaks HTTP) can run "select ECU, load hex, flash, check result".

No AI is involved: everything comes from Windows UI Automation and from reading the tool's DLLs.

## Scope

In v1:
- **Way A, drive the GUI.** Works on any app UI Automation can see (WinForms, WPF, Win32/MFC, most Qt).
- **Way B, call .NET code directly.** Only for WinForms handlers that tracing resolves, and only if the user opts in for that function.
- **Native DLLs.** Exports are listed and demangled, and the framework **never calls them**.
- **Scan + record**, then generate, then serve, plus the Studio web page.

Later, out of v1: **auto-explore** (clicking every control by itself) behind the deny-list and a sandbox. Tracing WPF/BAML handlers.

## Stack

Python 3.10+, Windows only. `pywinauto` (UIA backend), `dnfile` + `dncil` (.NET metadata and IL),
`pefile` (PE header, exports), `pythonnet` (direct .NET calls), `FastAPI` + `uvicorn` (REST and Studio),
`PyYAML`, `pytest`. A demangler for MSVC names: `UnDecorateSymbolName` from `dbghelp.dll` via ctypes,
so there is no extra dependency.

## Pipeline

```
 ① toolbridge scan     <app.exe> [--dll ...]        -> project/target.json
 ② toolbridge record   <workflow-name>              -> project/workflows/<name>.yaml
 ③ toolbridge generate                              -> project/<tool>_api/   (Python package)
 ④ toolbridge serve                                 -> REST API + Studio on 127.0.0.1:8750
```

A **project** is one folder per tool: `toolbridge.yaml` (app path, deny-list, timeouts), `target.json`,
`workflows/`, the generated package, and `runs/` (logs, failure screenshots).

## Components

| module | does | depends on |
|---|---|---|
| `scan/ui.py` | launches or attaches to the app and walks the UIA tree. Each control becomes `{id, type, label, automation_id, path, window}` | pywinauto |
| `scan/binary.py` | reads the PE header: .NET or native, 32 or 64-bit | pefile |
| `scan/dotnet.py` | WinForms: event wiring in `InitializeComponent` gives `control -> handler`. The handler's IL gives the methods it calls, skipping `System.Windows.Forms.*` and `MessageBox` calls, which leaves `action methods` with their signatures. WPF: handlers matched by name, report only | dnfile, dncil |
| `scan/native.py` | exports, demangled to signatures, report only | pefile, dbghelp |
| `record.py` | subscribes to UIA events (Invoke, ValueChanged, SelectionItem, window opened) and writes the steps. A terminal review then marks which values are parameters and picks the result check (it suggests the text that changed last) | pywinauto / comtypes |
| `runtime.py` | what generated code calls: `App` (start or attach), `find(locator)`, step executors, waits, the popup watcher, failure screenshots, the call lock | pywinauto |
| `generate.py` | writes the Python package: one function per control and one per workflow, plus `*_direct` variants where opted in | templates (string.Template) |
| `server.py` | FastAPI: `/controls`, `/click/{id}`, `/set/{id}`, `/workflows/{name}` (POST runs it), `/report`, the Studio page | FastAPI |
| `cli.py` | `scan`, `record`, `generate`, `serve`, `run <workflow> key=value ...` | |

### Locators
Each control is found by, in order: automation ID, then label + control type within its window, then
its index path in the tree. The scan stores all three. At runtime the first one that matches exactly one
control wins. If none does, the error lists what was there instead.

### Workflow file
```yaml
name: flash
params: [ecu, hex_file]
timeout_s: 600
steps:
  - {do: select, target: cmbEcu, value: "{ecu}"}
  - {do: click,  target: btnBrowse}
  - {do: file_dialog, value: "{hex_file}"}
  - {do: click,  target: btnFlash}
  - {do: wait,   target: lblStatus, until: "^(Done|Error).*", timeout_s: 600}
result: {target: lblStatus, ok: "^Done"}
```

### Result of every call
`Result(ok: bool, message: str, seconds: float, log: list[str], screenshot: str | None)`.

## Error handling

- **Unexpected popup** during a step: its text is read, it's closed with its default or Cancel button, and the call returns `ok=False, message=<popup text>`.
- **Control not found:** the error names the locator and the closest labels present.
- **Timeout:** per step, with a default per workflow. On timeout the call returns `ok=False` with a screenshot.
- **Concurrent calls:** a lock means one call at a time, and the REST server queues requests.
- **Deny-list:** a recorded step on a denied control is refused at record time, and again at runtime.
- **Direct calls:** if the bitness doesn't match the DLL, the error says so and the GUI variant still works. Direct variants exist only when the user opts in.
- **Errors in generated code:** they always raise `ToolBridgeError` with one sentence, and never a raw COM error.

## Demo targets (in repo, built in CI)

- `demo/DemoFlasher.NET`, C# WinForms (net8.0-windows):
  - controls: ECU combo, Browse + path box, Flash button, progress bar, status label
  - `FlashService.Program(string path, string ecu)` simulates a flash in about 3 s
  - a checkbox "simulate no response" makes it show an error popup
- `demo/DemoFlasher.Native`, a C++ Win32 window with the same controls, plus `flashcore.dll` exporting `?Flash@@YAHPBDH@Z`-style C++ functions.

## Testing

pytest runs on `windows-latest`, which has an interactive desktop:
- The scan finds every expected control in both demos.
- .NET tracing resolves `btnFlash -> FlashService.Program(string, string)`.
- Native exports are demangled correctly.
- Replaying a stored workflow file through the Python API, REST, and the direct variant, in both the success case and the error-popup case. Recording is tested by playing synthetic UIA input and checking the YAML.
- Locator fallback, timeout, deny-list, and the bitness-mismatch message.

## Deliverables

- A public repo `Alifizz01/ToolBridge`; commits authored as Alif only.
- A README with the problem statement, a pipeline diagram, Studio screenshots and a GIF of record → API call.
- `docs/` with: getting started on your own tool, the workflow file reference, and the limits (what UIA can't see, e.g. custom-drawn controls).
