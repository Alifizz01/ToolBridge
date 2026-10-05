# ToolBridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a Windows tool with no API (e.g. an ECU flasher) into a Python API and a REST API, by reading its DLLs and driving its GUI. No AI is involved.

**Architecture:** `scan/` reads binaries (folder scan, .NET IL tracing, native exports) and the live UI (UI Automation). `record.py` turns one manual run into a YAML workflow. `runtime.py` replays workflows and single controls robustly. `generate.py` writes a Python package, and `server.py` exposes the same runtime over REST with a one-page Studio. Two demo flashers (.NET WinForms + native Win32) are the test targets.

**Tech Stack:** Python ≥3.10 (Windows), pywinauto 0.6.9 (UIA), dnfile 0.18 + dncil 1.0, pefile, pythonnet 3 (coreclr), FastAPI + uvicorn, PyYAML, pytest + httpx; .NET 8 SDK (WinForms), MSVC (C++ Win32).

**Spec:** `docs/superpowers/specs/2026-10-05-toolbridge-design.md`

## Global Constraints

- Windows only; Python `>=3.10`; package `toolbridge`, src layout, CLI entry point `toolbridge`.
- No AI and no network calls at runtime. The REST server binds `127.0.0.1:8750` by default.
- Native DLL functions are **never called**, only listed. Direct .NET calls happen only for methods listed under `direct:` in `toolbridge.yaml`.
- Every user-facing error is a `ToolBridgeError` with one sentence that says what to check.
- Commits are authored as `Alifizz01 <izzuwan.alif@gmail.com>`, with **no co-author or session trailers**.
- Demo .NET target framework is `net8.0-windows`, and the native demo is built x64 with MSVC.

## Verified facts from the spike (2026-10-05)

- WinForms `Control.Name` appears as the UIA `automation_id` (`btnFlash`, `txtPath`, `cmbEcu`).
- dncil on `InitializeComponent` shows wiring as `ldfld <Field btnFlash>` … `ldftn <MethodDef btnFlash_Click>`, `newobj EventHandler::.ctor`, `callvirt Control::add_Click`. The handler body shows `callvirt FlashCore.FlashService::Program`.
- A .NET 8 `App.exe` is a **native apphost**. The managed code is `App.dll` beside it.
- `ElementFromPoint` returns whatever window is on top, so the recorder must bring the target to the foreground.

## File map

```
pyproject.toml
src/toolbridge/__init__.py        version, ToolBridgeError
src/toolbridge/scan/binary.py     PE kind + bitness
src/toolbridge/scan/dotnet.py     .NET types/methods listing, WinForms control→handler→action tracing
src/toolbridge/scan/native.py     exports + MSVC demangling
src/toolbridge/scan/inspect.py    folder scan, import graph, runtime-DLL hiding
src/toolbridge/scan/ui.py         live UIA scan -> controls with locators
src/toolbridge/project.py         project folder: toolbridge.yaml, target.json, workflows/
src/toolbridge/runtime.py         App, find(), steps, waits, popup watcher, Result, lock, deny-list
src/toolbridge/workflow.py        workflow YAML model + runner
src/toolbridge/direct.py          pythonnet direct calls + bitness check
src/toolbridge/record.py          mouse hook + value diff -> workflow steps, review prompt
src/toolbridge/generate.py        writes <tool>_api package
src/toolbridge/server.py          FastAPI REST + Studio
src/toolbridge/studio.html        the Studio page
src/toolbridge/cli.py             inspect / scan / record / generate / serve / run
demo/DemoFlasher.NET/             WinForms app + FlashCore class library
demo/DemoFlasher.Native/          Win32 C++ app + flashcore_native.dll
demo/build.ps1                    builds both into demo/out/{net,native}
tests/conftest.py                 demo build check, app fixtures
tests/test_*.py
.github/workflows/ci.yml          windows-latest
README.md, docs/
```

---

### Task 1: Scaffold + demo targets

**Files:**
- Create: `pyproject.toml`, `src/toolbridge/__init__.py`, `.gitignore`, `.gitattributes`, `LICENSE`
- Create: `demo/DemoFlasher.NET/FlashCore/FlashCore.csproj`, `FlashService.cs`
- Create: `demo/DemoFlasher.NET/DemoFlasher/DemoFlasher.csproj`, `Program.cs`, `MainForm.cs`, `MainForm.Designer.cs`
- Create: `demo/DemoFlasher.Native/app.cpp`, `flashcore.cpp`, `flashcore.h`
- Create: `demo/build.ps1`
- Test: `tests/test_demo_build.py`

**Interfaces:**
- Produces: `demo/out/net/DemoFlasher.exe`, `demo/out/net/DemoFlasher.dll`, `demo/out/net/FlashCore.dll`, `demo/out/native/DemoFlasherNative.exe`, `demo/out/native/flashcore_native.dll`
- Produces: `toolbridge.ToolBridgeError(RuntimeError)`, `toolbridge.__version__ = "0.1.0"`
- Demo .NET control names (automation IDs): `cmbEcu` (ComboBox, items `ECU1`,`ECU2`,`Gateway`), `txtPath` (TextBox), `btnBrowse`, `btnFlash`, `prgFlash` (ProgressBar), `lblStatus` (Label, starts `Ready`), `chkNoResponse` (CheckBox "Simulate no response"), `btnEraseAll` (Button "Erase all", used by deny-list tests)
- Demo native control IDs (automation IDs): `1001` combo, `1002` edit, `1003` Browse, `1004` Flash, `1005` status static, `1006` "Simulate no response" checkbox

- [ ] **Step 1: pyproject + package root**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "toolbridge"
version = "0.1.0"
description = "Generate a Python and REST API for Windows tools that have none"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "Muhamad Alif Izzuwan Bin Ibrahim"}]
dependencies = ["pywinauto>=0.6.9", "dnfile>=0.18", "dncil>=1.0", "pefile>=2023.2.7",
                "pyyaml>=6", "fastapi>=0.110", "uvicorn>=0.29"]
[project.optional-dependencies]
direct = ["pythonnet>=3.0"]
dev = ["pytest>=8", "httpx>=0.27", "pythonnet>=3.0"]
[project.scripts]
toolbridge = "toolbridge.cli:main"
[tool.setuptools.packages.find]
where = ["src"]
[tool.setuptools.package-data]
toolbridge = ["studio.html"]
[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# src/toolbridge/__init__.py
"""ToolBridge: an API for Windows tools that do not have one."""
__version__ = "0.1.0"


class ToolBridgeError(RuntimeError):
    """One sentence a person can act on."""
```

- [ ] **Step 2: FlashCore library**

```xml
<!-- demo/DemoFlasher.NET/FlashCore/FlashCore.csproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup>
</Project>
```

```csharp
// demo/DemoFlasher.NET/FlashCore/FlashService.cs
using System;
using System.IO;
using System.Threading;

namespace FlashCore
{
    /// The "vendor" logic a real flasher hides behind its GUI.
    public class FlashService
    {
        public bool SimulateNoResponse { get; set; }

        /// Flashes the file to the ECU. Returns bytes written; throws on error.
        public long Program(string path, string ecu, Action<int> progress = null)
        {
            if (string.IsNullOrEmpty(ecu)) throw new ArgumentException("No ECU selected");
            if (!File.Exists(path)) throw new FileNotFoundException("Hex file not found", path);
            if (SimulateNoResponse) { Thread.Sleep(500); throw new TimeoutException("ECU not responding"); }
            long size = new FileInfo(path).Length;
            for (int i = 1; i <= 10; i++) { Thread.Sleep(300); progress?.Invoke(i * 10); }
            return size;
        }

        public static string[] KnownEcus() => new[] { "ECU1", "ECU2", "Gateway" };
    }
}
```

- [ ] **Step 3: WinForms app.** The designer file is hand-written but in standard designer style, so `InitializeComponent` produces the IL pattern the tracer expects.

```xml
<!-- demo/DemoFlasher.NET/DemoFlasher/DemoFlasher.csproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType><TargetFramework>net8.0-windows</TargetFramework>
    <UseWindowsForms>true</UseWindowsForms><Nullable>disable</Nullable><ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup><ProjectReference Include="..\FlashCore\FlashCore.csproj" /></ItemGroup>
</Project>
```

```csharp
// demo/DemoFlasher.NET/DemoFlasher/Program.cs
namespace DemoFlasher;
static class Program
{
    [STAThread]
    static void Main() { ApplicationConfiguration.Initialize(); Application.Run(new MainForm()); }
}
```

```csharp
// demo/DemoFlasher.NET/DemoFlasher/MainForm.cs
using FlashCore;
namespace DemoFlasher;

public partial class MainForm : Form
{
    readonly FlashService service = new FlashService();

    public MainForm()
    {
        InitializeComponent();
        cmbEcu.Items.AddRange(FlashService.KnownEcus());
    }

    private void btnBrowse_Click(object sender, EventArgs e)
    {
        using var dlg = new OpenFileDialog { Title = "Open", Filter = "Hex files|*.hex|All files|*.*" };
        if (dlg.ShowDialog(this) == DialogResult.OK) txtPath.Text = dlg.FileName;
    }

    private async void btnFlash_Click(object sender, EventArgs e)
    {
        btnFlash.Enabled = false; lblStatus.Text = "Flashing..."; prgFlash.Value = 0;
        service.SimulateNoResponse = chkNoResponse.Checked;
        string path = txtPath.Text, ecu = cmbEcu.Text;
        try
        {
            long n = await Task.Run(() => service.Program(path, ecu, p => Invoke(() => prgFlash.Value = p)));
            lblStatus.Text = $"Done: {n / 1024.0:0.0} kB written to {ecu}";
        }
        catch (Exception ex)
        {
            lblStatus.Text = "Error";
            MessageBox.Show(this, "Error: " + ex.Message, "DemoFlasher", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally { btnFlash.Enabled = true; }
    }

    private void btnEraseAll_Click(object sender, EventArgs e) => lblStatus.Text = "Erased";
}
```

```csharp
// demo/DemoFlasher.NET/DemoFlasher/MainForm.Designer.cs
namespace DemoFlasher;
partial class MainForm
{
    private System.ComponentModel.IContainer components = null;
    private ComboBox cmbEcu; private TextBox txtPath; private Button btnBrowse; private Button btnFlash;
    private ProgressBar prgFlash; private Label lblStatus; private CheckBox chkNoResponse; private Button btnEraseAll;

    private void InitializeComponent()
    {
        cmbEcu = new ComboBox(); txtPath = new TextBox(); btnBrowse = new Button(); btnFlash = new Button();
        prgFlash = new ProgressBar(); lblStatus = new Label(); chkNoResponse = new CheckBox(); btnEraseAll = new Button();
        SuspendLayout();
        cmbEcu.Name = "cmbEcu"; cmbEcu.DropDownStyle = ComboBoxStyle.DropDownList; cmbEcu.SetBounds(20, 20, 200, 24);
        txtPath.Name = "txtPath"; txtPath.SetBounds(20, 56, 300, 24);
        btnBrowse.Name = "btnBrowse"; btnBrowse.Text = "Browse..."; btnBrowse.SetBounds(330, 55, 90, 26);
        btnBrowse.Click += btnBrowse_Click;
        btnFlash.Name = "btnFlash"; btnFlash.Text = "Flash"; btnFlash.SetBounds(20, 92, 100, 30);
        btnFlash.Click += btnFlash_Click;
        btnEraseAll.Name = "btnEraseAll"; btnEraseAll.Text = "Erase all"; btnEraseAll.SetBounds(130, 92, 100, 30);
        btnEraseAll.Click += btnEraseAll_Click;
        chkNoResponse.Name = "chkNoResponse"; chkNoResponse.Text = "Simulate no response"; chkNoResponse.SetBounds(250, 96, 180, 24);
        prgFlash.Name = "prgFlash"; prgFlash.SetBounds(20, 134, 400, 18);
        lblStatus.Name = "lblStatus"; lblStatus.Text = "Ready"; lblStatus.SetBounds(20, 162, 400, 22);
        ClientSize = new Size(440, 200);
        Controls.AddRange(new Control[] { cmbEcu, txtPath, btnBrowse, btnFlash, btnEraseAll, chkNoResponse, prgFlash, lblStatus });
        Name = "MainForm"; Text = "DemoFlasher";
        ResumeLayout(false); PerformLayout();
    }
}
```

- [ ] **Step 4: Native demo.** Same window in Win32. `flashcore_native.dll` exports C++ functions; the app links to it, so the import graph sees it.

```cpp
// demo/DemoFlasher.Native/flashcore.h
#pragma once
#ifdef FLASHCORE_EXPORTS
#define FC_API __declspec(dllexport)
#else
#define FC_API __declspec(dllimport)
#endif
FC_API int Flash(const char* path, int ecu);
FC_API int EraseAll(int ecu);
FC_API const char* Version();
```

```cpp
// demo/DemoFlasher.Native/flashcore.cpp
#define FLASHCORE_EXPORTS
#include "flashcore.h"
#include <windows.h>
FC_API int Flash(const char* path, int ecu) {
    if (!path || !*path || ecu < 0) return -1;
    Sleep(1500);
    return 0;
}
FC_API int EraseAll(int) { return 0; }
FC_API const char* Version() { return "1.0"; }
```

```cpp
// demo/DemoFlasher.Native/app.cpp
#include <windows.h>
#include "flashcore.h"
enum { ID_ECU = 1001, ID_PATH, ID_BROWSE, ID_FLASH, ID_STATUS, ID_NORESP };
static HWND hEcu, hPath, hStatus, hNoResp;

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    switch (m) {
    case WM_CREATE: {
        HINSTANCE hi = ((LPCREATESTRUCT)l)->hInstance;
        hEcu = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_TABSTOP, 20, 20, 200, 120, h, (HMENU)ID_ECU, hi, 0);
        for (auto s : { L"ECU1", L"ECU2", L"Gateway" }) SendMessageW(hEcu, CB_ADDSTRING, 0, (LPARAM)s);
        hPath = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL, 20, 56, 300, 24, h, (HMENU)ID_PATH, hi, 0);
        CreateWindowW(L"BUTTON", L"Browse...", WS_CHILD | WS_VISIBLE, 330, 55, 90, 26, h, (HMENU)ID_BROWSE, hi, 0);
        CreateWindowW(L"BUTTON", L"Flash", WS_CHILD | WS_VISIBLE, 20, 92, 100, 30, h, (HMENU)ID_FLASH, hi, 0);
        hNoResp = CreateWindowW(L"BUTTON", L"Simulate no response", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 250, 96, 180, 24, h, (HMENU)ID_NORESP, hi, 0);
        hStatus = CreateWindowW(L"STATIC", L"Ready", WS_CHILD | WS_VISIBLE, 20, 162, 400, 22, h, (HMENU)ID_STATUS, hi, 0);
        return 0; }
    case WM_COMMAND:
        if (LOWORD(w) == ID_BROWSE) {
            wchar_t file[MAX_PATH] = L"";
            OPENFILENAMEW ofn = { sizeof ofn }; ofn.hwndOwner = h; ofn.lpstrFile = file; ofn.nMaxFile = MAX_PATH;
            ofn.lpstrTitle = L"Open"; ofn.Flags = OFN_FILEMUSTEXIST;
            if (GetOpenFileNameW(&ofn)) SetWindowTextW(hPath, file);
        } else if (LOWORD(w) == ID_FLASH) {
            char path[MAX_PATH]; GetWindowTextA(hPath, path, MAX_PATH);
            int ecu = (int)SendMessageW(hEcu, CB_GETCURSEL, 0, 0);
            SetWindowTextW(hStatus, L"Flashing...");
            if (SendMessageW(hNoResp, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                SetWindowTextW(hStatus, L"Error");
                MessageBoxW(h, L"Error: ECU not responding", L"DemoFlasherNative", MB_OK | MB_ICONERROR);
            } else if (Flash(path, ecu) == 0) SetWindowTextW(hStatus, L"Done: flashed");
            else { SetWindowTextW(hStatus, L"Error"); MessageBoxW(h, L"Error: no ECU or file", L"DemoFlasherNative", MB_OK | MB_ICONERROR); }
        }
        return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

int WINAPI wWinMain(HINSTANCE hi, HINSTANCE, PWSTR, int show) {
    WNDCLASSW wc = {}; wc.lpfnWndProc = WndProc; wc.hInstance = hi; wc.lpszClassName = L"DemoFlasherNative";
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1); wc.hCursor = LoadCursor(0, IDC_ARROW);
    RegisterClassW(&wc);
    HWND h = CreateWindowW(L"DemoFlasherNative", L"DemoFlasherNative", WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME,
                           CW_USEDEFAULT, CW_USEDEFAULT, 460, 240, 0, 0, hi, 0);
    ShowWindow(h, show);
    MSG msg; while (GetMessageW(&msg, 0, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    return 0;
}
```

- [ ] **Step 5: Build script**

```powershell
# demo/build.ps1 — builds both demos into demo/out/{net,native}. Needs the .NET 8+ SDK and MSVC (VS 2022 C++).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
dotnet publish "$here/DemoFlasher.NET/DemoFlasher/DemoFlasher.csproj" -c Release -o "$here/out/net" --nologo -v q
if ($LASTEXITCODE) { throw "dotnet publish failed" }
$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath
$out = "$here/out/native"; New-Item -ItemType Directory -Force $out | Out-Null
$cmd = "`"$vs\VC\Auxiliary\Build\vcvars64.bat`" >nul && cd /d `"$out`" && " +
       "cl /nologo /EHsc /LD /Fe:flashcore_native.dll `"$here\DemoFlasher.Native\flashcore.cpp`" && " +
       "cl /nologo /EHsc /Fe:DemoFlasherNative.exe `"$here\DemoFlasher.Native\app.cpp`" flashcore_native.lib user32.lib comdlg32.lib /link /SUBSYSTEM:WINDOWS"
cmd /c $cmd
if ($LASTEXITCODE) { throw "MSVC build failed" }
```

- [ ] **Step 6: Test that the demos exist**

```python
# tests/test_demo_build.py
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_demo_binaries_exist():
    for rel in ["net/DemoFlasher.exe", "net/DemoFlasher.dll", "net/FlashCore.dll",
                "native/DemoFlasherNative.exe", "native/flashcore_native.dll"]:
        assert (OUT / rel).is_file(), f"run demo/build.ps1 first: missing {rel}"
```

- [ ] **Step 7: Build and run.** Run `powershell -File demo/build.ps1`, then `pip install -e ".[dev]"`, then `pytest tests/test_demo_build.py -v`. Expected: PASS.

- [ ] **Step 8: Commit.** `.gitignore` has `demo/out/`, `bin/`, `obj/`, `.venv/`, `__pycache__/`, `*.egg-info/`, `runs/`, `*.obj`. `.gitattributes` has `* text=auto eol=lf` and `*.ps1 text eol=crlf`.

```bash
git add -A && git commit -m "Scaffold and demo flashers (.NET WinForms, native Win32)"
```

---

### Task 2: Binary classification (`scan/binary.py`)

**Files:** Create `src/toolbridge/scan/__init__.py` (empty), `src/toolbridge/scan/binary.py`. Test: `tests/test_binary.py`

**Interfaces:**
- Produces: `@dataclass BinaryInfo(path: Path, kind: str, bits: str, managed_imports: list[str], native_imports: list[str])`, where `kind` is `"dotnet" | "native" | "apphost" | "not-pe"` and `bits` is `"x86" | "x64" | "arm64" | "any"`.
- Produces: `classify(path: Path) -> BinaryInfo`. `"apphost"` means a native exe with a .NET dll of the same stem next to it.

- [ ] **Step 1: Failing tests**

```python
# tests/test_binary.py
from pathlib import Path
from toolbridge.scan.binary import classify

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_dotnet_library():
    b = classify(OUT / "net/FlashCore.dll")
    assert b.kind == "dotnet" and b.bits == "any"


def test_dotnet_app_imports_flashcore():
    b = classify(OUT / "net/DemoFlasher.dll")
    assert "FlashCore" in b.managed_imports


def test_apphost_exe():
    assert classify(OUT / "net/DemoFlasher.exe").kind == "apphost"


def test_native_exe_imports_its_dll():
    b = classify(OUT / "native/DemoFlasherNative.exe")
    assert b.kind == "native" and b.bits == "x64"
    assert "flashcore_native.dll" in b.native_imports


def test_not_pe(tmp_path):
    f = tmp_path / "x.dll"; f.write_bytes(b"hello")
    assert classify(f).kind == "not-pe"
```

- [ ] **Step 2: Run them.** `pytest tests/test_binary.py -v` should FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/scan/binary.py
"""What is this file: .NET or native, 32 or 64 bit, and what does it load?"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import dnfile
import pefile

_MACHINE = {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}
_COR_ILONLY, _COR_32BITREQUIRED = 0x1, 0x2


@dataclass
class BinaryInfo:
    path: Path
    kind: str
    bits: str
    managed_imports: list[str] = field(default_factory=list)
    native_imports: list[str] = field(default_factory=list)


def classify(path: Path) -> BinaryInfo:
    path = Path(path)
    try:
        pe = dnfile.dnPE(str(path), fast_load=False)
    except (pefile.PEFormatError, OSError):
        return BinaryInfo(path, "not-pe", "")
    try:
        bits = _MACHINE.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
        native = sorted({e.dll.decode(errors="replace").lower()
                         for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])})
        if pe.net is not None and pe.net.mdtables is not None:
            flags = pe.net.struct.Flags
            if bits == "x86" and flags & _COR_ILONLY and not flags & _COR_32BITREQUIRED:
                bits = "any"
            refs = [str(r.Name) for r in (pe.net.mdtables.AssemblyRef or [])]
            return BinaryInfo(path, "dotnet", bits, refs, native)
        twin = path.with_suffix(".dll")
        if path.suffix.lower() == ".exe" and twin.is_file() and classify(twin).kind == "dotnet":
            return BinaryInfo(path, "apphost", bits, [twin.stem], native)
        return BinaryInfo(path, "native", bits, [], native)
    finally:
        pe.close()
```

- [ ] **Step 4: Run them.** `pytest tests/test_binary.py -v` should PASS. If `pe.net.struct.Flags` is not the attribute name in dnfile 0.18, print `dir(pe.net.struct)` and use the CorFlags field it shows.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Classify binaries: .NET, native, apphost, bitness, imports"`

---

### Task 3: .NET reader and WinForms tracing (`scan/dotnet.py`)

**Files:** Create `src/toolbridge/scan/dotnet.py`. Test: `tests/test_dotnet.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except the demo binaries.
- Produces:
  - `@dataclass Method(type: str, name: str, params: list[tuple[str, str]], returns: str, static: bool, public: bool)` with `.signature -> str`, e.g. `"FlashCore.FlashService.Program(string path, string ecu, Action<int> progress) -> long"`, and `.full_name -> "FlashCore.FlashService.Program"`
  - `list_methods(dll: Path, public_only=True) -> list[Method]`, which excludes property accessors, constructors and compiler-generated names (those containing `<`)
  - `@dataclass Wiring(control: str, event: str, handler: str, calls: list[str])`, where `calls` holds the full names of non-framework methods called by the handler, following `async` state machines (the `<handler>d__N.MoveNext` method)
  - `trace_winforms(dll: Path) -> list[Wiring]`

- [ ] **Step 1: Failing tests**

```python
# tests/test_dotnet.py
from pathlib import Path
from toolbridge.scan.dotnet import list_methods, trace_winforms

OUT = Path(__file__).resolve().parents[1] / "demo" / "out" / "net"


def test_lists_public_methods_with_signatures():
    ms = {m.full_name: m for m in list_methods(OUT / "FlashCore.dll")}
    prog = ms["FlashCore.FlashService.Program"]
    assert [p[1] for p in prog.params] == ["path", "ecu", "progress"]
    assert prog.params[0][0] == "string" and prog.returns == "long" and not prog.static
    assert ms["FlashCore.FlashService.KnownEcus"].static


def test_traces_button_to_vendor_method():
    w = {x.control: x for x in trace_winforms(OUT / "DemoFlasher.dll")}
    assert w["btnFlash"].event == "Click" and w["btnFlash"].handler == "btnFlash_Click"
    assert "FlashCore.FlashService.Program" in w["btnFlash"].calls
    assert w["btnBrowse"].calls == []          # only framework calls (OpenFileDialog)
    assert set(w) >= {"btnFlash", "btnBrowse", "btnEraseAll"}
```

- [ ] **Step 2: Run them.** `pytest tests/test_dotnet.py -v` should FAIL.

- [ ] **Step 3: Implement.** Signature decoding uses dnfile's parsed `MethodDef.Signature` blob. Element types: `0x01 void, 0x02 bool, 0x03 char, 0x08 int, 0x0A long, 0x0C float, 0x0D double, 0x0E string, 0x1C object, 0x1D szarray, 0x12 class, 0x11 valuetype, 0x15 generic inst`.

```python
# src/toolbridge/scan/dotnet.py
"""Read a .NET assembly without running it: public methods, and which WinForms control
calls which method (InitializeComponent wiring -> handler body -> non-framework calls)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.clr.token import Token

_FRAMEWORK = ("System.", "Microsoft.", "<")
_PRIM = {0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "sbyte", 0x05: "byte", 0x06: "short",
         0x07: "ushort", 0x08: "int", 0x09: "uint", 0x0A: "long", 0x0B: "ulong", 0x0C: "float",
         0x0D: "double", 0x0E: "string", 0x18: "IntPtr", 0x1C: "object"}
_TBL_FIELD, _TBL_METHODDEF, _TBL_MEMBERREF = 0x04, 0x06, 0x0A


@dataclass
class Method:
    type: str
    name: str
    params: list[tuple[str, str]]
    returns: str
    static: bool
    public: bool

    @property
    def full_name(self) -> str:
        return f"{self.type}.{self.name}"

    @property
    def signature(self) -> str:
        args = ", ".join(f"{t} {n}" for t, n in self.params)
        return f"{self.full_name}({args}) -> {self.returns}"


@dataclass
class Wiring:
    control: str
    event: str
    handler: str
    calls: list[str]


class _Reader(CilMethodBodyReaderBase):
    def __init__(self, pe: dnfile.dnPE, rva: int):
        self.pe, self.offset = pe, pe.get_offset_from_rva(rva)

    def read(self, n: int) -> bytes:
        data = self.pe.get_data(self.pe.get_rva_from_offset(self.offset), n)
        self.offset += n
        return data

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int) -> int:
        self.offset = offset
        return offset


def _type_name(row) -> str:
    ns = str(getattr(row, "TypeNamespace", "") or "")
    return f"{ns}.{row.TypeName}" if ns else str(row.TypeName)


class _Sig:
    """Decodes a MethodDefSig blob (ECMA-335 II.23.2.1) into type names."""

    def __init__(self, pe: dnfile.dnPE, blob: bytes):
        self.pe, self.b, self.i = pe, blob, 0

    def u(self) -> int:
        b = self.b[self.i]
        if b & 0x80 == 0:
            self.i += 1; return b
        if b & 0xC0 == 0x80:
            v = ((b & 0x3F) << 8) | self.b[self.i + 1]; self.i += 2; return v
        v = ((b & 0x1F) << 24) | (self.b[self.i + 1] << 16) | (self.b[self.i + 2] << 8) | self.b[self.i + 3]
        self.i += 4; return v

    def typedef_or_ref(self) -> str:
        coded = self.u()
        table, rid = coded & 0x3, coded >> 2
        md = self.pe.net.mdtables
        rows = {0: md.TypeDef, 1: md.TypeRef}.get(table)
        return _type_name(rows[rid - 1]) if rows else "?"

    def type(self) -> str:
        et = self.u()
        if et in _PRIM:
            return _PRIM[et]
        if et in (0x11, 0x12):
            name = self.typedef_or_ref()
            return name.split(".")[-1].split("`")[0] if name.startswith("System.") else name
        if et == 0x1D:
            return self.type() + "[]"
        if et == 0x15:
            self.u()                               # class/valuetype marker
            base = self.typedef_or_ref().split(".")[-1].split("`")[0]
            args = [self.type() for _ in range(self.u())]
            return f"{base}<{', '.join(args)}>"
        if et in (0x13, 0x1E):
            return f"T{self.u()}"
        if et == 0x10:
            return "ref " + self.type()
        return f"type0x{et:x}"

    def method(self) -> tuple[list[str], str]:
        conv = self.u()
        if conv & 0x10:
            self.u()                               # generic param count
        n = self.u()
        ret = self.type()
        return [self.type() for _ in range(n)], ret


def _open(dll: Path) -> dnfile.dnPE:
    return dnfile.dnPE(str(dll))


def _methods_by_type(pe):
    """Yields (typedef_row, methoddef_index0) using TypeDef.MethodList ranges."""
    md = pe.net.mdtables
    types = list(md.TypeDef)
    starts = [t.MethodList[0].row_index if t.MethodList else None for t in types]
    for t in types:
        for ref in t.MethodList or []:
            yield t, ref.row_index - 1


def list_methods(dll: Path, public_only: bool = True) -> list[Method]:
    pe = _open(dll)
    md = pe.net.mdtables
    out = []
    for t, idx in _methods_by_type(pe):
        m = md.MethodDef[idx]
        name = str(m.Name)
        public = bool(m.Flags.mdPublic)
        if (public_only and not public) or "<" in name or name.startswith((".", "get_", "set_", "add_", "remove_")):
            continue
        if public_only and not t.Flags.tdPublic:
            continue
        ptypes, ret = _Sig(pe, bytes(m.Signature.raw_data if hasattr(m.Signature, "raw_data") else m.Signature)).method()
        pnames = [str(p.row.Name) for p in (m.ParamList or []) if p.row.Sequence > 0]
        pnames += [f"arg{i}" for i in range(len(pnames), len(ptypes))]
        out.append(Method(_type_name(t), name, list(zip(ptypes, pnames)), ret,
                          bool(m.Flags.mdStatic), public))
    pe.close()
    return out


def _callee(pe, operand) -> str | None:
    tok = operand if isinstance(operand, Token) else Token(int(operand))
    md = pe.net.mdtables
    if tok.table == _TBL_MEMBERREF:
        r = md.MemberRef[tok.rid - 1]
        return f"{_type_name(r.Class.row)}.{r.Name}"
    if tok.table == _TBL_METHODDEF:
        for t, idx in _methods_by_type(pe):
            if idx == tok.rid - 1:
                return f"{_type_name(t)}.{md.MethodDef[idx].Name}"
    return None


def _body(pe, idx: int):
    m = pe.net.mdtables.MethodDef[idx]
    return CilMethodBody(_Reader(pe, m.Rva)).instructions if m.Rva else []


def trace_winforms(dll: Path) -> list[Wiring]:
    pe = _open(dll)
    md = pe.net.mdtables
    by_name = {}
    for t, idx in _methods_by_type(pe):
        by_name.setdefault(str(md.MethodDef[idx].Name), []).append((t, idx))
    wirings = []
    for t, idx in by_name.get("InitializeComponent", []):
        field = handler = None
        for ins in _body(pe, idx):
            op = ins.opcode.name
            if op == "ldfld" and Token(int(ins.operand)).table == _TBL_FIELD:
                field = str(md.Field[Token(int(ins.operand)).rid - 1].Name)
            elif op == "ldftn":
                handler = (_callee(pe, ins.operand) or "").rsplit(".", 1)[-1]
            elif op == "callvirt" and handler and field:
                callee = _callee(pe, ins.operand) or ""
                event = callee.rsplit(".", 1)[-1]
                if event.startswith("add_"):
                    wirings.append(Wiring(field, event[4:], handler, _handler_calls(pe, by_name, handler)))
                    handler = None
    pe.close()
    return wirings


def _handler_calls(pe, by_name, handler: str) -> list[str]:
    md = pe.net.mdtables
    bodies = [idx for _, idx in by_name.get(handler, [])]
    # async handlers: the real code is in the compiler-generated <handler>d__N.MoveNext
    for t, idx in _methods_by_type(pe):
        if str(t.TypeName).startswith(f"<{handler}>") and str(md.MethodDef[idx].Name) == "MoveNext":
            bodies.append(idx)
    calls = []
    for idx in bodies:
        for ins in _body(pe, idx):
            if ins.opcode.name in ("call", "callvirt", "newobj"):
                name = _callee(pe, ins.operand)
                if name and not name.startswith(_FRAMEWORK) and ".<" not in name and "+<" not in name \
                        and not name.rsplit(".", 1)[-1].startswith((".", "get_", "set_", "<")) and name not in calls:
                    calls.append(name)
    return calls
```

- [ ] **Step 4: Run the tests.** `pytest tests/test_dotnet.py -v` should PASS. Two checks to make against dnfile 0.18 while making it pass:
  - the Signature attribute holds the raw blob bytes (`m.Signature` may already be bytes)
  - `TypeDef.MethodList` items expose `.row_index`

  Adjust only those accessors, and keep the logic.

- [ ] **Step 5: Commit.** `git add -A && git commit -m ".NET reader: method signatures and WinForms button-to-method tracing"`

---

### Task 4: Native exports (`scan/native.py`)

**Files:** Create `src/toolbridge/scan/native.py`. Test: `tests/test_native.py`

**Interfaces:**
- Produces: `@dataclass Export(name: str, ordinal: int, signature: str)` and `list_exports(dll: Path) -> list[Export]`. `signature` is the demangled name, or `name` itself when the export isn't C++-mangled.
- Produces: `demangle(name: str) -> str`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_native.py
from pathlib import Path
from toolbridge.scan.native import demangle, list_exports

OUT = Path(__file__).resolve().parents[1] / "demo" / "out" / "native"


def test_demangle_msvc():
    assert demangle("?Flash@@YAHPEBDH@Z") == "int __cdecl Flash(char const *,int)"
    assert demangle("plain_c") == "plain_c"


def test_lists_demo_exports():
    sigs = {e.signature for e in list_exports(OUT / "flashcore_native.dll")}
    assert "int __cdecl Flash(char const *,int)" in sigs
    assert any("EraseAll" in s for s in sigs)
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/scan/native.py
"""Exported functions of a native DLL, with MSVC C++ names decoded. Listed, never called."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import pefile

_dbghelp = ctypes.WinDLL("dbghelp")
_dbghelp.UnDecorateSymbolName.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32]
_UNDNAME_COMPLETE = 0x0000


@dataclass
class Export:
    name: str
    ordinal: int
    signature: str


def demangle(name: str) -> str:
    if not name.startswith("?"):
        return name
    buf = ctypes.create_string_buffer(1024)
    n = _dbghelp.UnDecorateSymbolName(name.encode(), buf, len(buf), _UNDNAME_COMPLETE)
    return buf.value.decode() if n else name


def list_exports(dll: Path) -> list[Export]:
    pe = pefile.PE(str(dll), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    out = []
    for s in getattr(pe, "DIRECTORY_ENTRY_EXPORT", None).symbols if hasattr(pe, "DIRECTORY_ENTRY_EXPORT") else []:
        name = s.name.decode() if s.name else f"#{s.ordinal}"
        out.append(Export(name, s.ordinal, demangle(name)))
    pe.close()
    return out
```

- [ ] **Step 4: Run them.** They should PASS. If the exact text from dbghelp differs (e.g. spacing), update the expected string in the test to what `UnDecorateSymbolName` returns on the build machine. The test exists to catch regressions, not to pin dbghelp's formatting.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Native exports with MSVC demangling"`

---

### Task 5: Folder scan (`scan/inspect.py`) + CLI `inspect`

**Files:** Create `src/toolbridge/scan/inspect.py`, `src/toolbridge/cli.py`, `src/toolbridge/project.py`. Test: `tests/test_inspect.py`

**Interfaces:**
- Consumes: `classify`, `list_methods`, `list_exports`.
- Produces:
  - `@dataclass Entry(path: Path, kind: str, bits: str, used: str, runtime: bool, functions: int)`. `used` is `"app"` for the main assembly, `"direct"`, `"via <name>"`, or `""` when the app doesn't load it.
  - `inspect_folder(folder: Path, app: Path | None = None, show_runtime=False) -> list[Entry]`. `app` defaults to the only `.exe` in the folder, or else the first one alphabetically. Entries are sorted with the app first, then direct, then via, then unused, then by name.
  - `functions_of(path: Path) -> list[str]`: signatures for .NET or demangled exports for native.
  - `project.py`: `@dataclass Project(root: Path)` with `.config -> dict` (`toolbridge.yaml`), `.save_config(dict)`, `.target_path`, `.workflows_dir`, `.runs_dir`, `.load_target() -> dict`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_inspect.py
from pathlib import Path
from toolbridge.scan.inspect import functions_of, inspect_folder
from toolbridge.cli import main

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def test_net_folder_ranks_vendor_dll_first_and_hides_runtime():
    rows = inspect_folder(OUT / "net")
    names = [r.path.name for r in rows]
    assert names[0] == "DemoFlasher.exe"
    fc = next(r for r in rows if r.path.name == "FlashCore.dll")
    assert fc.used == "direct" and fc.kind == "dotnet" and fc.functions >= 2
    assert not any(r.runtime for r in rows)
    assert len(inspect_folder(OUT / "net", show_runtime=True)) >= len(rows)


def test_native_folder_marks_used_dll():
    rows = inspect_folder(OUT / "native")
    dll = next(r for r in rows if r.path.name == "flashcore_native.dll")
    assert dll.used == "direct" and dll.functions == 3


def test_functions_of():
    assert any("Program(" in f for f in functions_of(OUT / "net/FlashCore.dll"))


def test_cli_inspect_and_pick(tmp_path, capsys):
    assert main(["inspect", str(OUT / "net"), "--project", str(tmp_path / "p")]) == 0
    assert "FlashCore.dll" in capsys.readouterr().out
    assert main(["inspect", str(OUT / "net"), "--dll", "FlashCore.dll", "--project", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "Program(string path" in out
    assert "FlashCore.dll" in (tmp_path / "p" / "toolbridge.yaml").read_text()
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/project.py
"""One folder per tool: toolbridge.yaml, target.json, workflows/, runs/."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULTS = {"app": "", "dlls": [], "deny": [], "direct": [], "timeout_s": 60}


@dataclass
class Project:
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path: return self.root / "toolbridge.yaml"
    @property
    def target_path(self) -> Path: return self.root / "target.json"
    @property
    def workflows_dir(self) -> Path: return self.root / "workflows"
    @property
    def runs_dir(self) -> Path: return self.root / "runs"

    @property
    def config(self) -> dict:
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
        return {**DEFAULTS, **(data or {})}

    def save_config(self, cfg: dict) -> None:
        self.config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    def load_target(self) -> dict:
        from . import ToolBridgeError
        if not self.target_path.exists():
            raise ToolBridgeError(f"No scan in {self.root} yet. Run: toolbridge scan <app.exe> --project {self.root}")
        return json.loads(self.target_path.read_text(encoding="utf-8"))
```

```python
# src/toolbridge/scan/inspect.py
"""Folder scan: which DLLs does the app actually use, and what is inside them."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .binary import BinaryInfo, classify

_RUNTIME = re.compile(r"^(api-ms-|ext-ms-|vcruntime|msvcp|ucrtbase|concrt|mfc\d|kernel32|user32|gdi32|advapi32|"
                      r"comdlg32|shell32|ole32|oleaut32|comctl32|ws2_32|ntdll|bcrypt|crypt32|version|"
                      r"system\.|microsoft\.|mscorlib|netstandard|windowsbase|presentation|newtonsoft|"
                      r"qt\d|hostfxr|hostpolicy|coreclr|clrjit|mscordaccore|d3dcompiler)", re.I)


@dataclass
class Entry:
    path: Path
    kind: str
    bits: str
    used: str
    runtime: bool
    functions: int


def functions_of(path: Path) -> list[str]:
    info = classify(path)
    if info.kind == "dotnet":
        from .dotnet import list_methods
        return [m.signature for m in list_methods(path)]
    if info.kind == "native":
        from .native import list_exports
        return [e.signature for e in list_exports(path)]
    return []


def _pick_app(folder: Path) -> Path | None:
    exes = sorted(folder.glob("*.exe"))
    return exes[0] if exes else None


def inspect_folder(folder: Path, app: Path | None = None, show_runtime: bool = False) -> list[Entry]:
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".dll", ".exe"))
    infos: dict[str, BinaryInfo] = {p.name.lower(): classify(p) for p in files}
    by_stem = {p.stem.lower(): p.name.lower() for p in files if p.suffix.lower() == ".dll"}
    app = Path(app) if app else _pick_app(folder)
    used: dict[str, str] = {}
    if app:
        used[app.name.lower()] = "app"
        frontier = [(app.name.lower(), "")]
        while frontier:
            name, via = frontier.pop(0)
            info = infos.get(name)
            if not info:
                continue
            deps = list(info.native_imports) + [by_stem.get(m.lower(), "") for m in info.managed_imports]
            for dep in filter(None, deps):
                if dep in infos and dep not in used:
                    used[dep] = "direct" if name == app.name.lower() or used.get(name) == "app" else f"via {infos[name].path.name}"
                    frontier.append((dep, name))
    rows = []
    for key, info in infos.items():
        if info.kind == "not-pe":
            continue
        runtime = bool(_RUNTIME.match(info.path.name))
        if runtime and not show_runtime:
            continue
        n = len(functions_of(info.path)) if info.kind in ("dotnet", "native") and info.path.suffix.lower() == ".dll" else 0
        rows.append(Entry(info.path, info.kind, info.bits, used.get(key, ""), runtime, n))
    order = {"app": 0, "direct": 1}
    rows.sort(key=lambda r: (order.get(r.used, 2 if r.used else 3), r.path.name.lower()))
    return rows
```

The "app" DLL of an apphost (`DemoFlasher.dll`) is reached as `direct` from the exe, and `FlashCore.dll` from it. Treat everything reached from the app's own assembly as `direct` by marking the apphost twin as `app` too. Add this right after `used[app.name.lower()] = "app"`:

```python
        twin = infos.get(app.name.lower())
        if twin and twin.kind == "apphost":
            used[(app.stem + ".dll").lower()] = "app"
            frontier.append(((app.stem + ".dll").lower(), ""))
```

and change the `direct` condition to `used.get(name) == "app"`.

```python
# src/toolbridge/cli.py
"""toolbridge: inspect a tool's folder, scan its UI, record workflows, generate and serve its API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ToolBridgeError, __version__
from .project import Project


def _cmd_inspect(a) -> int:
    from .scan.inspect import functions_of, inspect_folder
    proj = Project(a.project)
    folder = Path(a.folder)
    if a.dll:
        path = next(iter(folder.rglob(a.dll)), None)
        if not path:
            raise ToolBridgeError(f"{a.dll} is not in {folder}")
        for f in functions_of(path):
            print(f"  {f}")
        cfg = proj.config
        if str(path) not in cfg["dlls"]:
            cfg["dlls"].append(str(path))
        proj.save_config(cfg)
        print(f"\n{path.name} added to {proj.config_path}")
        return 0
    rows = inspect_folder(folder, Path(a.app) if a.app else None, a.all)
    print(f"{'file':<34}{'kind':<9}{'bit':<6}{'used by app':<26}functions")
    for r in rows:
        print(f"{r.path.name:<34}{r.kind:<9}{r.bits:<6}{r.used or '-':<26}{r.functions or '-'}")
    print("\nPick one:  toolbridge inspect FOLDER --dll NAME.dll")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="toolbridge", description=__doc__)
    ap.add_argument("--version", action="version", version=f"toolbridge {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect", help="list the DLLs in a tool's folder and what is inside them")
    p.add_argument("folder"); p.add_argument("--dll"); p.add_argument("--app")
    p.add_argument("--all", action="store_true", help="also show runtime/system DLLs")
    p.add_argument("--project", default="toolbridge-project")
    a = ap.parse_args(argv)
    try:
        return {"inspect": _cmd_inspect}[a.cmd](a)
    except ToolBridgeError as exc:
        print(f"toolbridge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run them.** `pytest tests/test_inspect.py -v` should PASS.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Folder scan: find which DLLs the app uses and list their functions"`

---

### Task 6: Live UI scan (`scan/ui.py`) + CLI `scan`

**Files:** Create `src/toolbridge/scan/ui.py`. Modify `src/toolbridge/cli.py` (add `scan`). Test: `tests/test_scan_ui.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `Project`, `classify`, `trace_winforms`, `list_methods`, `list_exports`.
- Produces:
  - `scan_ui(window) -> list[dict]`. Each control is `{"id": str, "type": str, "label": str, "automation_id": str, "path": list[int], "window": str, "value": str}`. `id` is a Python-identifier-safe name: the automation_id if it's an identifier and not numeric, else `slug(label)_type`, else `type_N`. Ids are unique, with suffixes `_2`, `_3`…
  - `scan(project: Project, app: Path, dlls: list[Path]) -> dict` writes `target.json` = `{"app": str, "window": str, "controls": [...], "dotnet": {"wiring": [...], "methods": [...]}, "native": {"exports": [...]}}`.
  - `tests/conftest.py` fixtures: `net_app` and `native_app` start the demo exe and yield a pywinauto `WindowSpecification` (top window), killing the process after the test. `OUT` is a constant.

- [ ] **Step 1: conftest**

```python
# tests/conftest.py
import subprocess
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[1] / "demo" / "out"


def _start(exe: Path):
    from pywinauto import Application
    p = subprocess.Popen([str(exe)])
    app = Application(backend="uia").connect(process=p.pid, timeout=20)
    w = app.top_window()
    w.wait("ready", timeout=20)
    return p, w


@pytest.fixture
def net_app():
    p, w = _start(OUT / "net" / "DemoFlasher.exe")
    yield w
    p.kill()


@pytest.fixture
def native_app():
    p, w = _start(OUT / "native" / "DemoFlasherNative.exe")
    yield w
    p.kill()
```

- [ ] **Step 2: Failing tests**

```python
# tests/test_scan_ui.py
import json
from conftest import OUT
from toolbridge.project import Project
from toolbridge.scan.ui import scan, scan_ui


def test_net_controls_have_automation_ids(net_app):
    ids = {c["id"]: c for c in scan_ui(net_app)}
    assert {"cmbEcu", "txtPath", "btnBrowse", "btnFlash", "lblStatus", "chkNoResponse"} <= set(ids)
    assert ids["btnFlash"]["type"] == "Button" and ids["btnFlash"]["label"] == "Flash"


def test_native_controls_get_readable_ids(native_app):
    ids = {c["id"] for c in scan_ui(native_app)}
    assert "flash_button" in ids and "browse_button" in ids


def test_scan_writes_target_with_wiring(tmp_path, net_app):
    proj = Project(tmp_path)
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=net_app)
    t = json.loads(proj.target_path.read_text())
    w = {x["control"]: x for x in t["dotnet"]["wiring"]}
    assert "FlashCore.FlashService.Program" in w["btnFlash"]["calls"]
    assert any(m.startswith("FlashCore.FlashService.Program(") for m in t["dotnet"]["methods"])
```

- [ ] **Step 3: Run them.** They should FAIL.

- [ ] **Step 4: Implement**

```python
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
```

Add to `cli.py`:

```python
def _cmd_scan(a) -> int:
    from .scan.ui import scan
    proj = Project(a.project)
    dlls = [Path(d) for d in (a.dll or proj.config["dlls"])]
    t = scan(proj, Path(a.app), dlls)
    print(f"{len(t['controls'])} controls in '{t['window']}', "
          f"{len(t['dotnet']['wiring'])} traced handlers, {len(t['native']['exports'])} native exports")
    for w in t["dotnet"]["wiring"]:
        if w["calls"]:
            print(f"  {w['control']}.{w['event']} -> {', '.join(w['calls'])}")
    print(f"-> {proj.target_path}")
    return 0
```

and register it with `p = sub.add_parser("scan", help="start the app and list every control"); p.add_argument("app"); p.add_argument("--dll", action="append"); p.add_argument("--project", default="toolbridge-project")`, then add `"scan": _cmd_scan` to the dispatch dict.

- [ ] **Step 5: Run them.** `pytest tests/test_scan_ui.py -v` should PASS. The native combo's label is empty, so its id comes out as `combobox`. The test only checks the buttons.

- [ ] **Step 6: Commit.** `git add -A && git commit -m "Live UI scan to target.json with traced handlers"`

---

### Task 7: Runtime (`runtime.py`)

**Files:** Create `src/toolbridge/runtime.py`. Test: `tests/test_runtime.py`

**Interfaces:**
- Consumes: target dicts from Task 6.
- Produces:
  - `@dataclass Result(ok: bool, message: str, seconds: float, log: list[str], screenshot: str | None = None)`
  - `class Session(target: dict, deny: list[str] = (), runs_dir: Path | None = None, window=None)`:
    - `.start()` attaches to a running instance by window title, else launches `target["app"]`
    - `.find(control_id) -> wrapper` uses automation_id, then label+type, then path. Raises `ToolBridgeError` listing the closest labels
    - `.click(id)`, `.set_text(id, value)`, `.select(id, value)`, `.check(id, on: bool)`, `.read(id) -> str`
    - `.file_dialog(path)` fills an open file dialog and confirms it
    - `.wait_text(id, pattern, timeout_s) -> str`
    - `.popup() -> str | None` returns the text of an unexpected modal dialog after closing it
    - `.screenshot(name) -> str`
    - `.lock`, a `threading.RLock` held for every action
  - Every action raises `ToolBridgeError` if `id` is in `deny`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_runtime.py
import json
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui


def _session(window, **kw):
    target = {"app": str(OUT / "net/DemoFlasher.exe"), "window": window.window_text(), "controls": scan_ui(window)}
    return Session(target, window=window, **kw)


def test_select_set_click_and_wait(net_app, tmp_path):
    hexf = tmp_path / "app.hex"; hexf.write_bytes(b":00000001FF\n" * 100)
    s = _session(net_app)
    s.select("cmbEcu", "ECU2")
    s.set_text("txtPath", str(hexf))
    s.click("btnFlash")
    assert s.wait_text("lblStatus", r"^(Done|Error)", 20).startswith("Done")


def test_popup_is_caught(net_app):
    s = _session(net_app)
    s.check("chkNoResponse", True)
    s.select("cmbEcu", "ECU1"); s.set_text("txtPath", __file__)
    s.click("btnFlash")
    s.wait_text("lblStatus", r"^Error", 20)
    assert "ECU not responding" in (s.popup() or "")


def test_deny_list(net_app):
    with pytest.raises(ToolBridgeError, match="deny"):
        _session(net_app, deny=["btnEraseAll"]).click("btnEraseAll")


def test_locator_falls_back_to_label(net_app):
    s = _session(net_app)
    for c in s.target["controls"]:
        if c["id"] == "btnFlash":
            c["automation_id"] = "renamedInNewVersion"
    assert s.find("btnFlash").window_text() == "Flash"


def test_unknown_control_lists_alternatives(net_app):
    with pytest.raises(ToolBridgeError, match="btnFlash"):
        _session(net_app).find("btnFlsh")
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/runtime.py
"""What generated APIs and the REST server call: find controls robustly and act on them."""
from __future__ import annotations

import difflib
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import ToolBridgeError


@dataclass
class Result:
    ok: bool
    message: str
    seconds: float
    log: list[str] = field(default_factory=list)
    screenshot: str | None = None


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
            hits = self.window.descendants(**crit)
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
            try:
                w.invoke()
            except Exception:
                w.click_input()

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
            if not dlg:
                return None
            text = " ".join(t.window_text() for t in dlg.descendants(control_type="Text") if t.window_text())
            for name in ("OK", "Cancel", "Close", "Yes"):
                btns = dlg.descendants(title=name, control_type="Button")
                if btns:
                    btns[0].invoke(); break
            return text or dlg.window_text()

    def file_dialog(self, path: str, timeout_s: float = 10):
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            dlg = self._modal()
            if dlg:
                edit = dlg.descendants(auto_id="1148", control_type="Edit") or dlg.descendants(control_type="Edit")
                edit[0].set_edit_text(str(path))
                dlg.descendants(auto_id="1", control_type="Button")[0].invoke()
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
```

- [ ] **Step 4: Run them.** `pytest tests/test_runtime.py -v` should PASS. `capture_as_image` needs Pillow, so add `"pillow>=10"` to the dependencies.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Runtime: robust locators, actions, waits, popup and file-dialog handling, deny-list"`

---

### Task 8: Workflows (`workflow.py`) + CLI `run`

**Files:** Create `src/toolbridge/workflow.py`. Modify `cli.py`. Test: `tests/test_workflow.py`, fixture file `tests/data/flash.yaml`

**Interfaces:**
- Consumes: `Session`, `Result`, `Project`.
- Produces:
  - `load_workflow(path: Path) -> dict` validates `name`, `params`, `steps[*].do ∈ {click, set, select, check, file_dialog, wait}`, `steps[*].target`, and `result.target` / `result.ok`. Raises `ToolBridgeError` naming the bad key.
  - `run_workflow(session: Session, wf: dict, **params) -> Result`. Missing or extra params raise `ToolBridgeError`. A popup during any step gives `ok=False`, `message=popup text`. A timeout gives `ok=False` plus a screenshot.
  - `Project.workflows() -> dict[str, dict]`, added to project.py.

- [ ] **Step 1: Fixture workflow**

```yaml
# tests/data/flash.yaml
name: flash
params: [ecu, hex_file]
timeout_s: 30
steps:
  - {do: select, target: cmbEcu, value: "{ecu}"}
  - {do: click, target: btnBrowse}
  - {do: file_dialog, value: "{hex_file}"}
  - {do: click, target: btnFlash}
  - {do: wait, target: lblStatus, until: "^(Done|Error)"}
result: {target: lblStatus, ok: "^Done"}
```

- [ ] **Step 2: Failing tests**

```python
# tests/test_workflow.py
from pathlib import Path
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan_ui
from toolbridge.workflow import load_workflow, run_workflow

WF = Path(__file__).parent / "data" / "flash.yaml"


def _s(w, tmp_path):
    return Session({"app": str(OUT / "net/DemoFlasher.exe"), "window": w.window_text(),
                    "controls": scan_ui(w)}, window=w, runs_dir=tmp_path / "runs")


def test_flash_ok(net_app, tmp_path):
    hexf = tmp_path / "app.hex"; hexf.write_bytes(b"x" * 2048)
    r = run_workflow(_s(net_app, tmp_path), load_workflow(WF), ecu="Gateway", hex_file=str(hexf))
    assert r.ok and "Done" in r.message and "Gateway" in r.message and r.seconds > 0


def test_flash_error_popup(net_app, tmp_path):
    s = _s(net_app, tmp_path); s.check("chkNoResponse", True)
    r = run_workflow(s, load_workflow(WF), ecu="ECU1", hex_file=__file__)
    assert not r.ok and "ECU not responding" in r.message and r.screenshot


def test_missing_param(net_app, tmp_path):
    with pytest.raises(ToolBridgeError, match="hex_file"):
        run_workflow(_s(net_app, tmp_path), load_workflow(WF), ecu="ECU1")


def test_bad_step_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"; bad.write_text("name: x\nparams: []\nsteps: [{do: explode, target: a}]\nresult: {target: a, ok: x}\n")
    with pytest.raises(ToolBridgeError, match="explode"):
        load_workflow(bad)
```

- [ ] **Step 3: Run them.** They should FAIL.

- [ ] **Step 4: Implement**

```python
# src/toolbridge/workflow.py
"""Workflow YAML: load, validate, replay."""
from __future__ import annotations

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
            import re
            if re.search(wf["result"]["ok"], text):
                return Result(True, text, time.monotonic() - t0, log)
            return fail(text)
        except ToolBridgeError as exc:
            log.append(f"error: {exc}")
            return fail(str(exc))
```

Add to `project.py`:

```python
    def workflows(self) -> dict:
        from .workflow import load_workflow
        return {p.stem: load_workflow(p) for p in sorted(self.workflows_dir.glob("*.yaml"))}
```

Add CLI `run`: `toolbridge run NAME key=value ... --project P`. It builds `Session(proj.load_target(), proj.config["deny"], proj.runs_dir)`, runs the workflow, prints `ok`/`FAILED`, the message and the time, and returns 0 or 1.

- [ ] **Step 5: Run them.** `pytest tests/test_workflow.py -v` should PASS.

- [ ] **Step 6: Commit.** `git add -A && git commit -m "Workflows: YAML model, replay with popup/timeout handling, CLI run"`

---

### Task 9: Recorder (`record.py`) + CLI `record`

**Files:** Create `src/toolbridge/record.py`. Modify `cli.py`. Test: `tests/test_record.py`

**Interfaces:**
- Consumes: `Session`, `scan_ui`, `Project`.
- Produces:
  - `class Recorder(session: Session)` with `.start()` and `.stop() -> list[dict]` (raw steps). It uses a low-level mouse hook (`pywinauto.win32_hooks.Hook`) on a background thread. On each left-button-up inside the app's process:
    1. **Diff values first.** Snapshot every Edit/ComboBox/CheckBox value. For each one that changed since the last snapshot, emit `set`/`select`/`check`. Skip edits whose change came from a file dialog.
    2. **Then the click.** Get the element with `ElementFromPoint`, map it to a scanned control id (walking up parents until a match), and emit `click`. Clicks inside a `#32770` file dialog are not emitted. When the dialog closes with a path, emit `file_dialog` with that path and mark the target edit as "set by dialog".
  - `review(steps, ask=input, show=print) -> dict` (a workflow dict). It asks for each literal value: "make this a parameter? name (empty = keep)". It asks for the result control, defaulting to the Text control whose value changed last, and for the ok-pattern, defaulting to `^` + the first word of the final text. It adds a `wait` step on the result control before the end.
  - `save_workflow(project, wf) -> Path`.

- [ ] **Step 1: Failing tests.** These use real synthetic input; the deny-list is checked at record time.

```python
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
```

The value steps come before the click because the recorder diffs at the moment of the click. The combo selection made by `select()` shows up in that diff, since the recorder compares values rather than watching mouse paths.

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/record.py
"""Record one manual run: a low-level mouse hook marks each click; value changes are found by
diffing the app's inputs at every click; the result is turned into a workflow by review()."""
from __future__ import annotations

import ctypes
import threading
from pathlib import Path

import yaml

from . import ToolBridgeError
from .project import Project
from .runtime import Session

_VALUE_TYPES = {"Edit": "set", "ComboBox": "select", "CheckBox": "check"}


class Recorder:
    def __init__(self, session: Session):
        self.s = session
        self.steps: list[dict] = []
        self._values = self._snapshot()
        self._hook = None
        self._thread = None
        self._dialog_edit: str | None = None

    def _snapshot(self) -> dict:
        vals = {}
        for c in self.s.controls.values():
            if c["type"] in _VALUE_TYPES:
                try:
                    vals[c["id"]] = self.s.read(c["id"]) if c["type"] != "CheckBox" else \
                        str(self.s.find(c["id"]).get_toggle_state())
                except ToolBridgeError:
                    pass
        return vals

    def _diff(self):
        now = self._snapshot()
        for cid, val in now.items():
            if val != self._values.get(cid) and cid != self._dialog_edit:
                do = _VALUE_TYPES[self.s.controls[cid]["type"]]
                self.steps.append({"do": do, "target": cid, "value": val if do != "check" else val == "1"})
        self._dialog_edit = None
        self._values = now

    def _control_at(self, x, y) -> tuple[str | None, bool, str]:
        from pywinauto.uia_defines import IUIA
        from pywinauto.uia_element_info import UIAElementInfo
        el = UIAElementInfo(IUIA().iuia.ElementFromPoint(ctypes.wintypes.POINT(x, y)))
        if el.process_id != self.s.window.element_info.process_id:
            return None, False, ""
        node, in_dialog = el, False
        while node is not None:
            if node.class_name == "#32770":
                in_dialog = True
            if not in_dialog:
                for c in self.s.controls.values():
                    if (c["automation_id"] and c["automation_id"] == node.automation_id) or \
                            (c["label"] and c["label"] == node.name and c["type"] == node.control_type):
                        return c["id"], False, el.automation_id
            node = node.parent
        return None, in_dialog, el.automation_id

    def _on_event(self, ev):
        if getattr(ev, "current_key", None) != "LButton" or getattr(ev, "event_type", "") != "key up":
            return
        cid, in_dialog, el_auto_id = self._control_at(ev.mouse_x, ev.mouse_y)
        if in_dialog:
            if el_auto_id == "1":                      # the dialog's Open button
                dlg = self.s._modal()
                if dlg:
                    edits = dlg.descendants(auto_id="1148", control_type="Edit") or dlg.descendants(control_type="Edit")
                    self.steps.append({"do": "file_dialog", "value": edits[0].get_value()})
                    self._dialog_edit = next((c["id"] for c in self.s.controls.values() if c["type"] == "Edit"), None)
            return
        self._diff()
        if cid:
            if cid in self.s.deny:
                raise ToolBridgeError(f"'{cid}' is on the deny-list; it cannot be part of a workflow")
            self.steps.append({"do": "click", "target": cid})

    def start(self):
        from pywinauto.win32_hooks import Hook
        self._hook = Hook()
        self._hook.handler = self._on_event
        self._thread = threading.Thread(target=self._hook.hook, kwargs={"keyboard": False, "mouse": True}, daemon=True)
        self._thread.start()

    def stop(self) -> list[dict]:
        if self._hook:
            self._hook.stop()
        self._diff()
        return [{k: v for k, v in st.items() if not k.startswith("_")} for st in self.steps]


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
    ok = ask("Pattern that means success (regex, e.g. ^Done): ").strip() or "."
    out.append({"do": "wait", "target": target, "until": ok})
    show(f"workflow {name}({', '.join(params)}) with {len(out)} steps")
    return {"name": name, "params": params, "timeout_s": 60, "steps": out, "result": {"target": target, "ok": ok}}


def save_workflow(project: Project, wf: dict) -> Path:
    project.workflows_dir.mkdir(parents=True, exist_ok=True)
    path = project.workflows_dir / f"{wf['name']}.yaml"
    path.write_text(yaml.safe_dump(wf, sort_keys=False), encoding="utf-8")
    return path
```

`review` records the wait step as `until: <ok pattern>`. That is enough for the result, since a failure shows up as a popup or a timeout with a screenshot. 

File dialog capture is in `_on_event` above. The hook fires before the dialog's Open handler runs, so the dialog's edit can still be read at that point.

Add CLI `record NAME --project P`. It starts or attaches the Session, prints "Do the workflow in the app now. Press Enter here when done.", calls `input()`, then `stop()`, then `review(..., name)`, then `save_workflow`, and prints the path.

- [ ] **Step 4: Run them.** `pytest tests/test_record.py -v` should PASS.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Recorder: mouse hook + value diff, review into a parameterised workflow"`

---

### Task 10: Direct .NET calls (`direct.py`)

**Files:** Create `src/toolbridge/direct.py`. Test: `tests/test_direct.py`

**Interfaces:**
- Consumes: `classify`, `target["dotnet"]["assemblies"]`.
- Produces:
  - `check_bitness(dll_bits: str) -> None` raises `ToolBridgeError("... is a 32-bit (x86) assembly but this Python is 64-bit; use a 32-bit Python for direct calls, or the GUI version of this function")` when the bitness doesn't match. `"any"` always passes.
  - `call(assembly: Path, full_name: str, *args)` loads coreclr once (`pythonnet.load("coreclr")`), adds every DLL in the assembly's folder to the probing path (`clr.AddReference` on the assembly), resolves the type, and builds an instance with a parameterless constructor unless the method is static. It invokes the method with Python args and returns the converted result. .NET exceptions become a `ToolBridgeError` carrying the exception message.

- [ ] **Step 1: Failing tests**

```python
# tests/test_direct.py
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.direct import call, check_bitness


def test_static_call():
    assert list(call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.KnownEcus")) == ["ECU1", "ECU2", "Gateway"]


def test_instance_call_returns_bytes_written(tmp_path):
    f = tmp_path / "a.hex"; f.write_bytes(b"x" * 4096)
    assert call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.Program", str(f), "ECU1", None) == 4096


def test_exception_becomes_error():
    with pytest.raises(ToolBridgeError, match="not found"):
        call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.Program", "C:/nope.hex", "ECU1", None)


def test_bitness_mismatch_message():
    import struct
    other = "x86" if struct.calcsize("P") == 8 else "x64"
    with pytest.raises(ToolBridgeError, match="GUI version"):
        check_bitness(other)
    check_bitness("any")
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/direct.py
"""Call a .NET method found by tracing, without the GUI. Opt-in only (toolbridge.yaml: direct:)."""
from __future__ import annotations

import struct
from pathlib import Path

from . import ToolBridgeError

_loaded = False


def check_bitness(dll_bits: str) -> None:
    py = "x64" if struct.calcsize("P") == 8 else "x86"
    if dll_bits in ("any", "", py):
        return
    raise ToolBridgeError(f"The tool's assembly is {dll_bits} but this Python is {py}; use a {dll_bits} Python "
                          "for direct calls, or the GUI version of this function")


def _load(assembly: Path):
    global _loaded
    if not _loaded:
        try:
            import pythonnet
            pythonnet.load("coreclr")
        except Exception as exc:
            raise ToolBridgeError(f"Direct calls need pythonnet and the .NET runtime: {exc}") from exc
        _loaded = True
    import clr  # noqa: F401  (available after pythonnet.load)
    import System
    return System.Reflection.Assembly.LoadFrom(str(Path(assembly).resolve()))


def call(assembly: Path, full_name: str, *args):
    from .scan.binary import classify
    check_bitness(classify(Path(assembly)).bits)
    asm = _load(assembly)
    type_name, method_name = full_name.rsplit(".", 1)
    t = asm.GetType(type_name)
    if t is None:
        raise ToolBridgeError(f"{type_name} is not in {Path(assembly).name}")
    m = next((x for x in t.GetMethods() if x.Name == method_name and len(x.GetParameters()) == len(args)), None)
    if m is None:
        raise ToolBridgeError(f"{full_name} with {len(args)} arguments is not in {Path(assembly).name}")
    import System
    target = None if m.IsStatic else System.Activator.CreateInstance(t)
    try:
        return m.Invoke(target, list(args) if args else None)
    except Exception as exc:
        inner = getattr(exc, "InnerException", None)
        raise ToolBridgeError(f"{full_name} failed: {inner.Message if inner else exc}") from exc
```

- [ ] **Step 4: Run them.** They should PASS. If `Invoke` wraps the exception differently in pythonnet 3, take the message from `exc.__cause__` or from `str(exc)`. The test only requires "not found" in the text.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Direct .NET calls via pythonnet, with bitness check"`

---

### Task 11: Generator (`generate.py`) + CLI `generate`

**Files:** Create `src/toolbridge/generate.py`. Modify `cli.py`. Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: `Project` (target, config `direct`, `deny`, workflows), `Session`, `run_workflow`, `call`.
- Produces: `generate(project: Project, package: str | None = None) -> Path`, which writes `<project>/<package>/__init__.py`. The default package name is `slug(window title) + "_api"`. The module contains:
  - `class Tool:` with `__init__(self, project_dir=<abs path>)`, which creates a `Session`
  - per control: `click_<id>()` for Button/MenuItem/CheckBox; `set_<id>(value)` for Edit; `select_<id>(value)` for ComboBox; `read_<id>() -> str` for every control
  - per workflow: `def <name>(self, <params>) -> Result` with a docstring listing the steps
  - per opt-in direct method: `def <method>_direct(self, *args)`, docstring = signature
  - module-level `CONTROLS`, `WORKFLOWS` (names) for introspection.

  Denied controls get no click/set/select methods.

- [ ] **Step 1: Failing tests**

```python
# tests/test_generate.py
import importlib, json, shutil, sys
from conftest import OUT
from toolbridge.generate import generate
from toolbridge.project import Project
from toolbridge.scan.ui import scan

WF = __import__("pathlib").Path(__file__).parent / "data" / "flash.yaml"


def test_generated_api_runs_workflow_and_direct(tmp_path, net_app):
    proj = Project(tmp_path / "proj")
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=net_app)
    cfg = proj.config; cfg["deny"] = ["btnEraseAll"]; cfg["direct"] = ["FlashCore.FlashService.KnownEcus"]
    proj.save_config(cfg)
    proj.workflows_dir.mkdir(); shutil.copy(WF, proj.workflows_dir)
    pkg = generate(proj)
    assert pkg.name == "demoflasher_api"
    sys.path.insert(0, str(pkg.parent))
    api = importlib.import_module("demoflasher_api")
    assert "flash" in api.WORKFLOWS
    tool = api.Tool()
    assert not hasattr(tool, "click_btnEraseAll") and hasattr(tool, "click_btnFlash")
    assert list(tool.KnownEcus_direct()) == ["ECU1", "ECU2", "Gateway"]
    hexf = tmp_path / "a.hex"; hexf.write_bytes(b"x" * 1024)
    r = tool.flash(ecu="ECU1", hex_file=str(hexf))
    assert r.ok, r.message
    src = (pkg / "__init__.py").read_text()
    compile(src, "api", "exec")
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement**

```python
# src/toolbridge/generate.py
"""Write a plain Python package for one tool: methods per control, per workflow, per opt-in direct call."""
from __future__ import annotations

import re
from pathlib import Path

from .project import Project

_HEADER = '''"""API for {window}, generated by ToolBridge from {app}.

Regenerate with:  toolbridge generate --project "{project}"
"""
from pathlib import Path

from toolbridge.project import Project
from toolbridge.runtime import Result, Session
from toolbridge.workflow import run_workflow

PROJECT = Path(r"{project}")
CONTROLS = {controls!r}
WORKFLOWS = {workflows!r}


class Tool:
    """One running instance of {window}. Methods are thread-safe (one action at a time)."""

    def __init__(self, project_dir=PROJECT):
        self._project = Project(Path(project_dir))
        cfg = self._project.config
        self.session = Session(self._project.load_target(), cfg["deny"], self._project.runs_dir)
        self._workflows = self._project.workflows()
'''


def _ident(s: str) -> str:
    s = re.sub(r"\W+", "_", s).strip("_")
    return s if s and not s[0].isdigit() else f"c_{s}"


def generate(project: Project, package: str | None = None) -> Path:
    t, cfg = project.load_target(), project.config
    deny = set(cfg["deny"])
    workflows = project.workflows()
    package = package or _ident(t["window"]).lower() + "_api"
    lines = [_HEADER.format(window=t["window"], app=t["app"], project=project.root.resolve(),
                            controls=[c["id"] for c in t["controls"]], workflows=list(workflows))]
    for c in t["controls"]:
        cid, name = c["id"], _ident(c["id"])
        what = f'{c["type"]} "{c["label"]}"' if c["label"] else c["type"]
        if cid not in deny:
            if c["type"] in ("Button", "MenuItem", "CheckBox", "RadioButton", "TabItem", "ListItem"):
                lines.append(f'    def click_{name}(self):\n        """Click {what}."""\n'
                             f'        self.session.click({cid!r})\n')
            if c["type"] == "Edit":
                lines.append(f'    def set_{name}(self, value):\n        """Type into {what}."""\n'
                             f'        self.session.set_text({cid!r}, value)\n')
            if c["type"] == "ComboBox":
                lines.append(f'    def select_{name}(self, value):\n        """Pick an option in {what}."""\n'
                             f'        self.session.select({cid!r}, value)\n')
        lines.append(f'    def read_{name}(self) -> str:\n        """Current text of {what}."""\n'
                     f'        return self.session.read({cid!r})\n')
    for wname, wf in workflows.items():
        params = ", ".join(wf["params"])
        steps = "\n        ".join(f"- {s['do']} {s.get('target', '')} {s.get('value', s.get('until', ''))}".rstrip()
                                  for s in wf["steps"])
        kwargs = ", ".join(f"{p}={p}" for p in wf["params"])
        lines.append(f'    def {_ident(wname)}(self{", " + params if params else ""}) -> Result:\n'
                     f'        """Recorded workflow. Steps:\n        {steps}\n        """\n'
                     f'        return run_workflow(self.session, self._workflows[{wname!r}]{", " + kwargs if kwargs else ""})\n')
    sigs = {s.split("(")[0]: s for s in t["dotnet"]["methods"]}
    assemblies = t["dotnet"].get("assemblies", [])
    for full in cfg["direct"]:
        asm = next((a for a in assemblies if Path(a).stem == full.split(".")[0]), assemblies[-1] if assemblies else "")
        lines.append(f'    def {_ident(full.rsplit(".", 1)[1])}_direct(self, *args):\n'
                     f'        """Direct .NET call, no GUI: {sigs.get(full, full)}"""\n'
                     f'        from toolbridge.direct import call\n'
                     f'        return call(Path(r"{asm}"), {full!r}, *args)\n')
    pkg = project.root / package
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("\n".join(lines), encoding="utf-8")
    return pkg
```

The assembly for a direct method is picked by matching the namespace's first segment to the DLL stem (`FlashCore.*` → `FlashCore.dll`), falling back to the last assembly scanned. Add a CLI `generate --project P [--package NAME]` that prints the package path and a three-line usage example.

- [ ] **Step 4: Run them.** They should PASS.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Generator: Python package with control, workflow and direct methods"`

---

### Task 12: REST server + Studio (`server.py`, `studio.html`) + CLI `serve`

**Files:** Create `src/toolbridge/server.py`, `src/toolbridge/studio.html`. Modify `cli.py`. Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `Project`, `Session`, `run_workflow`, `inspect_folder`, `functions_of`, `call`.
- Produces: `create_app(project: Project, session: Session | None = None) -> FastAPI`, with these endpoints:
  - `GET /` serves Studio HTML
  - `GET /report` returns the target minus controls, plus the config
  - `GET /controls` lists the controls
  - `POST /click/{id}`
  - `POST /set/{id}` with body `{"value": str}`
  - `POST /select/{id}` with body `{"value": str}`
  - `GET /read/{id}` returns `{"value": str}`
  - `GET /workflows` returns `{name: {"params": [...], "steps": n}}`
  - `POST /workflows/{name}` with a body of params returns a `Result` as JSON (`200` even when `ok=false`)
  - `POST /direct/{full_name}` with body `{"args": [...]}` returns `{"value": ...}`, only for names in `direct:`, else `403`
  - `GET /inspect?folder=...` returns rows as JSON
  - `ToolBridgeError` becomes `400 {"error": msg}`; a denied control gives `403`.
  - Calls are serialized by `session.lock`, and FastAPI runs them in its threadpool.

- [ ] **Step 1: Failing tests**

```python
# tests/test_server.py
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from conftest import OUT
from toolbridge.project import Project
from toolbridge.runtime import Session
from toolbridge.scan.ui import scan
from toolbridge.server import create_app

WF = Path(__file__).parent / "data" / "flash.yaml"


def _client(tmp_path, window):
    proj = Project(tmp_path / "p")
    scan(proj, OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"], window=window)
    cfg = proj.config; cfg["deny"] = ["btnEraseAll"]; cfg["direct"] = ["FlashCore.FlashService.KnownEcus"]
    proj.save_config(cfg)
    proj.workflows_dir.mkdir(); shutil.copy(WF, proj.workflows_dir)
    s = Session(proj.load_target(), cfg["deny"], proj.runs_dir, window=window)
    return TestClient(create_app(proj, s))


def test_rest_end_to_end(tmp_path, net_app):
    c = _client(tmp_path, net_app)
    assert "DemoFlasher" in c.get("/").text
    assert any(x["id"] == "btnFlash" for x in c.get("/controls").json())
    assert c.get("/workflows").json()["flash"]["params"] == ["ecu", "hex_file"]
    hexf = tmp_path / "a.hex"; hexf.write_bytes(b"x" * 100)
    r = c.post("/workflows/flash", json={"ecu": "ECU2", "hex_file": str(hexf)}).json()
    assert r["ok"] and "ECU2" in r["message"]
    assert c.get("/read/lblStatus").json()["value"].startswith("Done")
    assert c.post("/click/btnEraseAll").status_code == 403
    assert c.post("/direct/FlashCore.FlashService.KnownEcus", json={"args": []}).json()["value"] == ["ECU1", "ECU2", "Gateway"]
    assert c.post("/direct/FlashCore.FlashService.Program", json={"args": []}).status_code == 403
    assert c.post("/workflows/flash", json={"ecu": "ECU1"}).status_code == 400
    rows = c.get("/inspect", params={"folder": str(OUT / "net")}).json()
    assert rows[0]["file"] == "DemoFlasher.exe"
```

- [ ] **Step 2: Run them.** They should FAIL.

- [ ] **Step 3: Implement the server**

```python
# src/toolbridge/server.py
"""REST API + Studio over one tool's project. Binds 127.0.0.1 by default."""
from __future__ import annotations

from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import ToolBridgeError
from .project import Project
from .runtime import Session
from .workflow import run_workflow


def create_app(project: Project, session: Session | None = None) -> FastAPI:
    cfg = project.config
    target = project.load_target()
    session = session or Session(target, cfg["deny"], project.runs_dir)
    app = FastAPI(title=f"ToolBridge: {target['window']}", version="0.1.0")

    @app.exception_handler(ToolBridgeError)
    async def _err(_: Request, exc: ToolBridgeError):
        code = 403 if "deny-list" in str(exc) else 400
        return JSONResponse({"error": str(exc)}, status_code=code)

    @app.get("/", response_class=HTMLResponse)
    def studio():
        return files("toolbridge").joinpath("studio.html").read_text(encoding="utf-8").replace("{{TITLE}}", target["window"])

    @app.get("/report")
    def report():
        return {**{k: v for k, v in target.items() if k != "controls"}, "config": project.config}

    @app.get("/controls")
    def controls():
        return target["controls"]

    @app.post("/click/{cid}")
    def click(cid: str):
        session.click(cid); return {"ok": True}

    @app.post("/set/{cid}")
    def set_(cid: str, value: str = Body(..., embed=True)):
        session.set_text(cid, value); return {"ok": True}

    @app.post("/select/{cid}")
    def select(cid: str, value: str = Body(..., embed=True)):
        session.select(cid, value); return {"ok": True}

    @app.get("/read/{cid}")
    def read(cid: str):
        return {"value": session.read(cid)}

    @app.get("/workflows")
    def workflows():
        return {n: {"params": wf["params"], "steps": len(wf["steps"])} for n, wf in project.workflows().items()}

    @app.post("/workflows/{name}")
    def run(name: str, params: dict = Body(default={})):
        wfs = project.workflows()
        if name not in wfs:
            raise HTTPException(404, f"no workflow '{name}'")
        return asdict(run_workflow(session, wfs[name], **params))

    @app.post("/direct/{full_name}")
    def direct(full_name: str, args: list = Body(default=[], embed=True)):
        if full_name not in project.config["direct"]:
            raise HTTPException(403, f"{full_name} is not enabled for direct calls (toolbridge.yaml: direct:)")
        from .direct import call
        asm = next((a for a in target["dotnet"].get("assemblies", []) if Path(a).stem == full_name.split(".")[0]), None)
        value = call(Path(asm), full_name, *args)
        try:
            value = list(value) if not isinstance(value, (str, int, float, bool)) and value is not None else value
        except TypeError:
            value = str(value)
        return {"value": value}

    @app.get("/inspect")
    def inspect(folder: str, all: bool = False):
        from .scan.inspect import inspect_folder
        return [{"file": r.path.name, "path": str(r.path), "kind": r.kind, "bits": r.bits, "used": r.used,
                 "functions": r.functions} for r in inspect_folder(Path(folder), show_runtime=all)]

    @app.get("/functions")
    def functions(path: str):
        from .scan.inspect import functions_of
        return functions_of(Path(path))

    return app
```

- [ ] **Step 4: Implement Studio.** One file, vanilla JS, no CDN. It has four panels: **DLLs** (folder input → `/inspect`, click a row → `/functions`), **Controls** (tree from `/controls`, with a detail pane showing the automation id, the traced call from `/report` wiring, and the Python and REST call snippets), **Workflows** (one row per workflow, param inputs, a ▶ Try button posting to `/workflows/{name}`, showing ok/message/seconds/log), and **Direct** (enabled methods with an argument box). Use a dark/light theme via `prefers-color-scheme`, and put `{{TITLE}}` in `<title>` and the header.

```html
<!-- src/toolbridge/studio.html -->
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ToolBridge · {{TITLE}}</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#14171c;--muted:#5b6472;--line:#dfe3e8;--accent:#0b62d6;--ok:#1a7f37;--bad:#c62828}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--panel:#171b21;--ink:#e6e9ee;--muted:#9aa4b2;--line:#29303a;--accent:#5aa2ff;--ok:#4cc26a;--bad:#ff6b6b}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:12px;align-items:baseline;padding:14px 20px;border-bottom:1px solid var(--line)}
header b{font-size:17px}header span{color:var(--muted)}
nav{display:flex;gap:4px;padding:8px 20px}nav button{border:0;background:none;color:var(--muted);padding:6px 12px;border-radius:6px;cursor:pointer;font:inherit}
nav button.on{background:var(--panel);color:var(--ink);box-shadow:0 0 0 1px var(--line)}
main{padding:0 20px 20px}section{display:none}section.on{display:grid;gap:14px;grid-template-columns:minmax(240px,1fr) 2fr}
@media (max-width:760px){section.on{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto}
.row{padding:6px 8px;border-radius:6px;cursor:pointer;display:flex;justify-content:space-between;gap:8px}.row:hover,.row.sel{background:var(--bg)}
.tag{font-size:12px;color:var(--muted)}code,pre{font:12.5px ui-monospace,Consolas,monospace}pre{background:var(--bg);padding:8px;border-radius:6px;white-space:pre-wrap}
input{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);width:100%}
button.go{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 14px;cursor:pointer;font:inherit}
.ok{color:var(--ok)}.bad{color:var(--bad)}
</style></head><body>
<header><b>ToolBridge</b><span>{{TITLE}}</span><span id="sum"></span></header>
<nav><button data-t="dlls">DLLs</button><button data-t="controls" class="on">Controls</button><button data-t="workflows">Workflows</button><button data-t="direct">Direct</button></nav>
<main>
<section id="dlls"><div class="card"><input id="folder" placeholder="Tool folder, e.g. C:\Program Files\Vendor\Flasher"><br><br><button class="go" id="scanbtn">Inspect</button><div id="dllrows"></div></div><div class="card"><pre id="funcs">Pick a DLL to see its functions.</pre></div></section>
<section id="controls" class="on"><div class="card" id="ctl"></div><div class="card" id="ctldetail">Pick a control.</div></section>
<section id="workflows"><div class="card" id="wfl"></div><div class="card" id="wfout">Run a workflow to see its result.</div></section>
<section id="direct"><div class="card" id="dir"></div><div class="card"><pre id="dirout"></pre></div></section>
</main>
<script>
const $=s=>document.querySelector(s), j=(u,o)=>fetch(u,o).then(r=>r.json()), post=(u,b)=>j(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button,section').forEach(x=>x.classList.remove('on'));b.classList.add('on');$('#'+b.dataset.t).classList.add('on')});
let report={};
async function load(){
  report=await j('/report'); const ctls=await j('/controls'), wfs=await j('/workflows');
  const wiring=Object.fromEntries((report.dotnet?.wiring||[]).map(w=>[w.control,w]));
  $('#sum').textContent=`${ctls.length} controls · ${Object.keys(wfs).length} workflows`;
  $('#ctl').innerHTML=ctls.map(c=>`<div class="row" data-id="${esc(c.id)}"><span>${esc(c.label||c.id)}</span><span class="tag">${esc(c.type)}</span></div>`).join('');
  $('#ctl').onclick=e=>{const r=e.target.closest('.row');if(!r)return;document.querySelectorAll('#ctl .row').forEach(x=>x.classList.toggle('sel',x===r));
    const c=ctls.find(x=>x.id===r.dataset.id), w=wiring[c.automation_id]; const verb=c.type==='Edit'?'set':c.type==='ComboBox'?'select':'click';
    $('#ctldetail').innerHTML=`<b>${esc(c.type)} "${esc(c.label)}"</b><p class="tag">automation id <code>${esc(c.automation_id||'—')}</code> · window ${esc(c.window)}</p>`+
      (w?`<p>${esc(w.event)} → <code>${esc(w.handler)}</code>${w.calls.length?' → <code>'+w.calls.map(esc).join('</code>, <code>')+'</code>':''}</p>`:'')+
      `<pre>tool.${verb}_${esc(c.id)}(${verb==='click'?'':'"…"'})\nPOST /${verb}/${esc(c.id)}</pre>`};
  $('#wfl').innerHTML=Object.entries(wfs).map(([n,w])=>`<div class="card"><b>${esc(n)}</b> <span class="tag">${w.steps} steps</span>`+
    w.params.map(p=>`<p><label class="tag">${esc(p)}</label><input data-wf="${esc(n)}" data-p="${esc(p)}"></p>`).join('')+`<button class="go" data-run="${esc(n)}">▶ Try</button></div>`).join('')||'No workflows yet: <code>toolbridge record NAME</code>';
  $('#wfl').onclick=async e=>{const n=e.target.dataset.run;if(!n)return;const body={};document.querySelectorAll(`[data-wf="${n}"]`).forEach(i=>body[i.dataset.p]=i.value);
    $('#wfout').textContent='Running…';const r=await post('/workflows/'+n,body);
    $('#wfout').innerHTML=r.error?`<p class="bad">${esc(r.error)}</p>`:`<p class="${r.ok?'ok':'bad'}"><b>${r.ok?'✔ ok':'✘ failed'}</b> · ${esc(r.message)} · ${r.seconds.toFixed(1)} s</p><pre>${r.log.map(esc).join('\n')}</pre>${r.screenshot?'<p class="tag">screenshot: '+esc(r.screenshot)+'</p>':''}`};
  const direct=report.config?.direct||[];
  $('#dir').innerHTML=direct.map(d=>`<p><b><code>${esc(d)}</code></b><input data-d="${esc(d)}" placeholder='args as JSON, e.g. ["C:/fw/app.hex","ECU1",null]'><br><br><button class="go" data-call="${esc(d)}">Call</button></p>`).join('')||'Nothing enabled. Add method names under <code>direct:</code> in toolbridge.yaml.';
  $('#dir').onclick=async e=>{const d=e.target.dataset.call;if(!d)return;let args=[];try{args=JSON.parse(document.querySelector(`[data-d="${d}"]`).value||'[]')}catch{}
    $('#dirout').textContent=JSON.stringify(await post('/direct/'+d,{args}),null,2)};
}
$('#scanbtn').onclick=async()=>{const rows=await j('/inspect?folder='+encodeURIComponent($('#folder').value));
  $('#dllrows').innerHTML=rows.error?`<p class="bad">${esc(rows.error)}</p>`:rows.map(r=>`<div class="row" data-path="${esc(r.path)}"><span>${esc(r.file)}</span><span class="tag">${esc(r.kind)} · ${esc(r.bits)} · ${esc(r.used||'unused')} · ${r.functions||'–'}</span></div>`).join('')};
$('#dllrows').onclick=async e=>{const r=e.target.closest('.row');if(!r)return;const f=await j('/functions?path='+encodeURIComponent(r.dataset.path));$('#funcs').textContent=Array.isArray(f)?f.join('\n')||'(no functions)':f.error};
load();
</script></body></html>
```

- [ ] **Step 5: CLI `serve`.** `toolbridge serve --project P [--host 127.0.0.1] [--port 8750]` runs `uvicorn.run(create_app(Project(a.project)), host=a.host, port=a.port)` and prints `Studio: http://127.0.0.1:8750`.

- [ ] **Step 6: Run them.** `pytest tests/test_server.py -v` should PASS.

- [ ] **Step 7: Commit.** `git add -A && git commit -m "REST API and Studio"`

---

### Task 13: CI, README, docs, screenshots, publish

**Files:**
- Create: `.github/workflows/ci.yml`, `README.md`, `docs/getting-started.md`, `docs/workflow-reference.md`, `docs/limits.md`
- Create: `tools/screenshots.py`, which serves the demo project, opens Studio in headless Chrome with Playwright, and writes `docs/img/{inspect,controls,workflow,direct}.png`
- Create: `examples/demo-project/` (a scanned demo project with `flash.yaml`), `examples/pytest_example.py`

- [ ] **Step 1: CI**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with: { dotnet-version: "8.0.x" }
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - name: build demo targets
        shell: pwsh
        run: ./demo/build.ps1
      - run: pip install -e ".[dev]"
      - run: pytest -v
```

- [ ] **Step 2: Example test**

```python
# examples/pytest_example.py — how a test bench uses a generated API
import pytest
from demoflasher_api import Tool


@pytest.fixture(scope="session")
def flasher():
    return Tool()


@pytest.mark.parametrize("ecu", ["ECU1", "ECU2", "Gateway"])
def test_flash_every_ecu(flasher, ecu, tmp_path):
    hexf = tmp_path / "app.hex"; hexf.write_bytes(b":00000001FF\n")
    r = flasher.flash(ecu=ecu, hex_file=str(hexf))
    assert r.ok, f"{ecu}: {r.message} (screenshot: {r.screenshot})"
```

- [ ] **Step 3: README.** Sections, in order:
  - problem statement table (the usual way / what goes wrong / ToolBridge)
  - the pipeline diagram from the spec (⓪–④)
  - Studio screenshots
  - "Try it on the demo" (build.ps1 → inspect → scan → record or copy flash.yaml → generate → serve)
  - "Use it on your tool"
  - Python, REST (curl) and pytest examples
  - What it can and cannot see (link to limits.md)
  - How it is built and tested, with the real test count from `pytest`

- [ ] **Step 4: Screenshots.** Run `python tools/screenshots.py` and check each PNG by eye.

- [ ] **Step 5: Publish.**
  - `gh repo create Alifizz01/ToolBridge --public --source . --push`, with commits as Alif (`git log --format='%an %ae' | sort -u` must show only Alifizz01).
  - Watch CI until it's green on both Python versions; `gh run watch`.

- [ ] **Step 6: Commit** each part as it lands, e.g. `git commit -m "README, docs, CI, screenshots"`.

---

## Self-review notes

- **Spec coverage:**
  - inspect: Task 5
  - scan: Task 6
  - record: Task 9
  - generate: Task 11
  - serve and Studio: Task 12
  - runtime, locators, popups, timeouts, lock, deny: Task 7
  - workflows: Task 8
  - direct and bitness: Task 10
  - native report-only: Tasks 4 and 5 (no call path exists)
  - WPF by-name matching: **not covered**. The spec lists it as report-only, so it's deferred to after v1 and mentioned in `docs/limits.md`.
  - auto-explore: out of scope (spec)
- **Names checked across tasks:**
  - `Session.click/set_text/select/check/read/wait_text/popup/file_dialog/screenshot/find/lock/controls/target/deny`
  - `run_workflow(session, wf, **params)`, `Project.workflows()`
  - `target["dotnet"]["assemblies"|"wiring"|"methods"]`
  - `call(assembly, full_name, *args)`
