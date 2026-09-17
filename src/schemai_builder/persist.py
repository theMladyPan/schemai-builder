"""JSON persistence for projects."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Project


def save_project(project: Project, path: Path) -> None:
    """Save a project as indented JSON."""
    path.write_text(json.dumps(project.model_dump(), indent=2))


def load_project(path: Path) -> Project:
    """Load a project from JSON."""
    return Project.model_validate_json(path.read_text())
