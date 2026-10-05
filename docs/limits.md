# What ToolBridge can and cannot do

Better to know before pointing it at a production tool.

**It sees what UI Automation sees.** Standard controls in WinForms, WPF, Win32/MFC, Qt and Delphi
are fine. Controls that are painted rather than built from widgets (some instrument panels, game
engines, Java Swing without the Access Bridge, many Electron canvases) appear as one big pane.
Clicking those would need image matching, which ToolBridge deliberately does not do.

**It needs a real desktop session.** The tool must run in a logged-in Windows session, not as a
service and not on a locked screen. On a test PC, enable auto-logon and keep the session unlocked;
GitHub's `windows-latest` runners work out of the box.

**Hidden screens are scanned when they are open.** Controls on tabs that the tool creates lazily do
not exist until the tab is shown. Open them before scanning, or scan once per screen.

**Direct calls are .NET-only and opt-in.** Native DLLs are listed (with C++ signatures when the
names are decorated), never called: a wrong guess at a calling convention can crash the tool or,
on a flasher, brick a device. WPF event handlers are wired in compiled XAML (BAML), which
ToolBridge does not decode yet, so WPF tools get the GUI API but no button-to-method trace.

**One action at a time per tool.** Calls are serialised; the REST server queues requests.
Two copies of the tool on one PC need two projects whose window titles differ.

**Reverse engineering may be restricted by the tool's licence.** Reading a DLL's metadata is what
the scan and `inspect` do. Check the licence of the tool you point it at.
