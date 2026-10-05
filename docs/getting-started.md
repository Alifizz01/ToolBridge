# Using ToolBridge on your own tool

Works for any Windows program whose window Windows UI Automation can see: WinForms, WPF,
Win32/MFC, most Qt and Delphi apps. Python 3.10+ on the same PC as the tool.

```powershell
pip install "toolbridge @ git+https://github.com/Alifizz01/ToolBridge"
pip install "toolbridge[direct] @ git+https://github.com/Alifizz01/ToolBridge"   # + direct .NET calls
```

Every command takes `--project DIR` (default `toolbridge-project`): one folder per tool.

## 0. Which DLL matters? (no tool running needed)

```powershell
toolbridge inspect "C:\Program Files\Vendor\FlashTool"
toolbridge inspect "C:\Program Files\Vendor\FlashTool" --dll FlashEngine.dll
```

The first lists every DLL with its kind, bitness and whether the tool actually loads it; runtime and
system libraries are hidden (`--all` shows them). The second lists that DLL's functions and remembers
it for the scan.

## 1. Scan

```powershell
toolbridge scan "C:\Program Files\Vendor\FlashTool\FlashTool.exe"
```

Starts the tool, lists every control, and for .NET tools traces which method each button calls.
Open the screens you need **before** scanning if the tool hides controls in tabs or sub-windows that
are not created until shown: run the scan once per screen into the same project.

## 2. Record

```powershell
toolbridge record flash
```

Do the job once in the tool, then press Enter in the terminal. You are asked which typed or selected
values should become parameters, and which control shows the result. The workflow is saved as YAML
([reference](workflow-reference.md)); edit it freely.

## 3. Use it

```powershell
toolbridge run flash ecu=ECU1 hex_file=C:\fw\app.hex      # one-off, exit code 0/1
toolbridge generate                                      # Python package for tests
toolbridge serve                                         # REST API + Studio on http://127.0.0.1:8750
```

```python
from flashtool_api import Tool
r = Tool().flash(ecu="ECU1", hex_file=r"C:\fw\app.hex")
assert r.ok, r.message
```

```powershell
curl -X POST http://127.0.0.1:8750/workflows/flash -H "content-type: application/json" `
     -d '{"ecu": "ECU1", "hex_file": "C:/fw/app.hex"}'
```

Interactive API docs are at `http://127.0.0.1:8750/docs`.

## toolbridge.yaml

```yaml
app: C:\Program Files\Vendor\FlashTool\FlashTool.exe
dlls: [C:\Program Files\Vendor\FlashTool\FlashEngine.dll]
deny: [btnEraseAll, btnFactoryReset]     # never clicked: not by workflows, the API or REST
direct: [Vendor.Flash.FlashEngine.GetVersion]   # .NET methods callable without the GUI (opt-in)
timeout_s: 60
```

Put anything destructive in `deny`. Only list a method under `direct` when you know what it does:
it skips every check the GUI makes.
