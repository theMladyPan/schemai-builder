"""CLI: mock replay of scripted conversations."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pydantic import ValidationError

from .apply import apply_and_record
from .models import Project, SchematicDiff, empty_schematic
from .render import render_all


def replay(script: Path, out_dir: Path, sleep: float | None = None) -> Project:
    """Replay a scripted conversation, writing each sheet SVG after every step."""
    data = json.loads(script.read_text())
    delay = data.get("sleep", 0) if sleep is None else sleep
    out_dir.mkdir(parents=True, exist_ok=True)
    project = Project(schematic=empty_schematic())
    for step in data.get("steps", []):
        if delay:
            time.sleep(delay)
        try:
            diff = SchematicDiff.model_validate(step["diff"])
        except ValidationError as e:
            raise SystemExit(
                f"invalid diff in step {step.get('message')!r}: {e}"
            ) from e
        project = apply_and_record(project, diff)
        for number, svg in render_all(project.schematic).items():
            (out_dir / f"sheet-{number}.svg").write_text(svg)
    return project


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="schemai-builder")
    sub = parser.add_subparsers(dest="command", required=True)
    p_replay = sub.add_parser("replay", help="replay a scripted conversation")
    p_replay.add_argument("script", type=Path)
    p_replay.add_argument("--out", type=Path, required=True)
    p_replay.add_argument("--sleep", type=float, default=None)
    p_serve = sub.add_parser("serve", help="run the web UI")
    p_serve.add_argument("--project", type=Path, required=True)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn

        from .app import create_app

        uvicorn.run(create_app(args.project), host=args.host, port=args.port)
    else:
        replay(args.script, args.out, args.sleep)
