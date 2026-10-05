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
