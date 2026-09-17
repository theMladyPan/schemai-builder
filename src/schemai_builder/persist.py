"""Project folder persistence: schematic.json, reasons.md, history.jsonl, render/."""

from __future__ import annotations

import json
from pathlib import Path

from .library import LIBRARY
from .models import HistoryEntry, Project, Schematic
from .render import render_all


def save_project(project: Project, project_dir: Path) -> None:
    """Save a project folder; render/ SVGs are a derived cache."""
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "schematic.json").write_text(
        json.dumps(project.schematic.model_dump(), indent=2)
    )
    (project_dir / "reasons.md").write_text(project.reasons)
    with (project_dir / "history.jsonl").open("w") as f:
        for entry in project.history:
            f.write(entry.model_dump_json() + "\n")
    render_dir = project_dir / "render"
    render_dir.mkdir(exist_ok=True)
    for stale in render_dir.glob("sheet-*.svg"):
        stale.unlink()
    for number, svg in render_all(project.schematic).items():
        (render_dir / f"sheet-{number}.svg").write_text(svg)


def load_project(project_dir: Path) -> Project:
    """Load a project folder; rejects components with unknown library ids."""
    sch = Schematic.model_validate(
        json.loads((project_dir / "schematic.json").read_text())
    )
    bad = [c.library_id for c in sch.components if c.library_id not in LIBRARY]
    if bad:
        raise ValueError(f"unknown library_id {bad[0]!r}")
    reasons_path = project_dir / "reasons.md"
    reasons = reasons_path.read_text() if reasons_path.exists() else ""
    history_path = project_dir / "history.jsonl"
    history = (
        [
            HistoryEntry.model_validate_json(line)
            for line in history_path.read_text().splitlines()
            if line.strip()
        ]
        if history_path.exists()
        else []
    )
    return Project(schematic=sch, reasons=reasons, history=history)
