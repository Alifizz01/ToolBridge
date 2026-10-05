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

    def workflows(self) -> dict:
        from .workflow import load_workflow
        return {p.stem: load_workflow(p) for p in sorted(self.workflows_dir.glob("*.yaml"))}
