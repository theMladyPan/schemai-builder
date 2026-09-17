"""JSON persistence for projects."""

from __future__ import annotations

import json
from pathlib import Path

from .library import LIBRARY
from .models import Project


def save_project(project: Project, path: Path) -> None:
    """Save a project as indented JSON."""
    path.write_text(json.dumps(project.model_dump(), indent=2))


def load_project(path: Path) -> Project:
    """Load a project from JSON; rejects components with unknown library ids."""
    project = Project.model_validate_json(path.read_text())
    bad = [
        c.library_id
        for c in project.schematic.components
        if c.library_id not in LIBRARY
    ]
    if bad:
        raise ValueError(f"unknown library_id {bad[0]!r}")
    return project
