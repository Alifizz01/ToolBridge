"""Make the README images from real runs: both demo tools are started, scanned, driven through
Studio in a headless browser, and captured. Also saves the real terminal output of the CLI.

Runs in CI (.github/workflows/screenshots.yml) because it takes over the desktop:
    python tools/screenshots.py      ->  docs/img/*.png, docs/img/*.txt
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT, IMG = ROOT / "demo" / "out", ROOT / "docs" / "img"
sys.path.insert(0, str(ROOT / "src"))

from toolbridge.project import Project            # noqa: E402
from toolbridge.runtime import Session            # noqa: E402
from toolbridge.scan.ui import launch, scan       # noqa: E402
from toolbridge.server import create_app          # noqa: E402
from toolbridge.workflow import run_workflow      # noqa: E402


def cli(*args) -> str:
    out = subprocess.run([sys.executable, "-m", "toolbridge.cli", *map(str, args)], capture_output=True,
                         text=True, cwd=ROOT).stdout
    return out.replace(str(ROOT) + "\\", "").replace(tempfile.gettempdir(), "%TEMP%")


def serve(project: Project, port: int):
    server = uvicorn.Server(uvicorn.Config(create_app(project), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    return server


def project(base: Path, name: str, exe: Path, dlls: list[Path], workflows: list[Path], window, cfg: dict) -> Project:
    p = Project(base / name)
    scan(p, exe, dlls, window=window)
    p.save_config({**p.config, **cfg})
    p.workflows_dir.mkdir(exist_ok=True)
    for wf in workflows:
        shutil.copy(wf, p.workflows_dir)
    return p


def shot(page, path: Path) -> None:
    """Screenshot the page down to the end of its content, not the empty viewport below."""
    page.evaluate("window.scrollTo(0, 0)")
    height = page.evaluate("Math.ceil(document.querySelector('main').getBoundingClientRect().bottom) + 20")
    page.screenshot(path=path, clip={"x": 0, "y": 0, "width": 1180, "height": height}, full_page=True)


def capture(window, path: Path) -> None:
    """The window as drawn: DWM's frame bounds, without the invisible resize borders."""
    import ctypes
    import ctypes.wintypes
    from PIL import ImageGrab
    window.set_focus()
    time.sleep(0.3)
    rect = ctypes.wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.wintypes.HWND(window.handle), 9,   # EXTENDED_FRAME_BOUNDS
                                               ctypes.byref(rect), ctypes.sizeof(rect))
    ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(path)


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="toolbridge-shots-"))
    Path("C:/fw").mkdir(exist_ok=True)                  # a short, realistic path for the images
    hexf = Path("C:/fw/app_v2.1.hex")
    hexf.write_bytes(b":10000000" + b"0" * 32 + b"\n" * 4000)

    (IMG / "terminal-inspect.txt").write_text(cli("inspect", OUT / "net", "--project", base / "cli"), encoding="utf-8")
    (IMG / "terminal-functions.txt").write_text(
        cli("inspect", OUT / "net", "--dll", "FlashCore.dll", "--project", base / "cli"), encoding="utf-8")

    flasher_proc, flasher_win = launch(OUT / "net" / "DemoFlasher.exe")
    calib_proc, calib_win = launch(OUT / "calib" / "DemoCalibrator.exe")
    try:
        fl = project(base, "demoflasher", OUT / "net/DemoFlasher.exe", [OUT / "net/FlashCore.dll"],
                     [ROOT / "tests/data/flash.yaml"], flasher_win,
                     {"deny": ["btnEraseAll"], "direct": ["FlashCore.FlashService.KnownEcus"]})
        ca = project(base, "democalibrator", OUT / "calib/DemoCalibrator.exe", [],
                     sorted((ROOT / "tests/data/calib").glob("*.yaml")), calib_win, {})
        (IMG / "terminal-scan.txt").write_text(
            cli("scan", OUT / "net/DemoFlasher.exe", "--dll", OUT / "net/FlashCore.dll", "--project", base / "cli2")
            .replace(str(base), "."), encoding="utf-8")
        serve(fl, 8751)
        serve(ca, 8752)

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1180, "height": 700}, device_scale_factor=2)

            page.goto("http://127.0.0.1:8751/")
            page.click("#ctl .row[data-id=btnFlash]")
            shot(page, IMG / "studio-controls.png")

            page.click("nav button[data-t=dlls]")
            page.fill("#folder", str(OUT / "net"))
            page.click("#scanbtn")
            page.click("#dllrows .row:has-text('FlashCore.dll')")
            page.wait_for_function("document.querySelector('#funcs').textContent.includes('Program(')")
            shot(page, IMG / "studio-dlls.png")

            page.click("nav button[data-t=workflows]")
            page.fill("input[data-wf=flash][data-p=ecu]", "Gateway")
            page.fill("input[data-wf=flash][data-p=hex_file]", str(hexf))
            page.click("button[data-run=flash]")
            status = flasher_win.child_window(auto_id="lblStatus")
            while not status.window_text().startswith("Flashing"):   # past the file dialog
                time.sleep(0.1)
            time.sleep(1.2)                                   # mid-flash: progress bar moving
            capture(flasher_win, IMG / "demoflasher.png")
            page.wait_for_selector("#wfout p.ok, #wfout p.bad", timeout=60_000)
            shot(page, IMG / "studio-flash.png")

            # calibration: measure, correct, then show the verify run in Studio
            s = Session(ca.load_target(), window=calib_win)
            wfs = ca.workflows()
            before = run_workflow(s, wfs["measure"], setpoint="10.000")
            run_workflow(s, wfs["apply_offset"], offset=f"{before.values['measured'] - 10:.3f}")
            page.goto("http://127.0.0.1:8752/")
            page.click("nav button[data-t=workflows]")
            for k, v in {"setpoint": "10.000", "low": "9.99", "high": "10.01"}.items():
                page.fill(f"input[data-wf=verify][data-p={k}]", v)
            page.click("button[data-run=verify]")
            page.wait_for_selector("#wfout p.ok, #wfout p.bad", timeout=60_000)
            shot(page, IMG / "studio-calibration.png")
            capture(calib_win, IMG / "democalibrator.png")
            (IMG / "calibration-run.txt").write_text(yaml.safe_dump(
                {"before": round(before.values["measured"], 3), "offset": round(before.values["measured"] - 10, 3)}),
                encoding="utf-8")
            browser.close()
    finally:
        flasher_proc.kill()
        calib_proc.kill()
    print("\n".join(sorted(p.name for p in IMG.iterdir())))


if __name__ == "__main__":
    main()
