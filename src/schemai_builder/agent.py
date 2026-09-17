"""Python API for the create agent: one structured-output turn per run_turn."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model

from .apply import DiffError, apply_and_record
from .models import Project, ReasonsPatch, SchematicDiff
from .persist import load_project, save_project
from .prompt import build_prompt, sheet_pngs
from .reasons import apply_reasons_patch

INSTRUCTIONS = """\
You edit electrical schematics via a structured diff. Components reference \
library ids only; never invent pinouts. If the sheet, net, group, or component \
is unclear, return a question instead of guessing. Keep reasons.md short: \
delete stale ADRs, append only what matters. Open nets during creation are fine.\
"""


class AgentOutput(BaseModel):
    """Structured LLM output: message plus optional question, diff, reasons patch."""

    message: str
    question: str | None = None  # if set, do NOT apply diff or reasons_patch
    diff: SchematicDiff | None = None
    reasons_patch: ReasonsPatch | None = None


class TurnResult(BaseModel):
    """Outcome of one run_turn."""

    project: Project
    message: str
    question: str | None = None
    applied: bool


def _run_agent(model: Model | None, prompt: str, project: Project) -> AgentOutput:
    agent = Agent(
        model or os.environ.get("OPENROUTER_MODEL", "openrouter:openai/gpt-4.1-mini"),
        output_type=AgentOutput,
        instructions=INSTRUCTIONS,
    )
    content: str | list[str | BinaryContent] = prompt
    pngs = sheet_pngs(project.schematic)
    if pngs:
        content = [prompt] + [
            BinaryContent(data=png, media_type="image/png") for png in pngs.values()
        ]
    return agent.run_sync(content).output


def run_turn(
    project_dir: Path,
    text: str,
    *,
    model: Model | None = None,
) -> TurnResult:
    """Load the project, run one agent turn, apply and persist the result."""
    project = load_project(project_dir)
    prompt = build_prompt(project, text)
    output = _run_agent(model, prompt, project)
    if output.question:
        return TurnResult(
            project=project,
            message=output.message,
            question=output.question,
            applied=False,
        )
    diff = output.diff or SchematicDiff()
    try:
        apply_and_record(project, diff, user=text, message=output.message)
    except DiffError as e:
        retry_prompt = f"{prompt}\n\n## diff errors\n" + "\n".join(e.errors)
        output = _run_agent(model, retry_prompt, project)
        diff = output.diff or SchematicDiff()
        apply_and_record(project, diff, user=text, message=output.message)
    if output.reasons_patch:
        project.reasons = apply_reasons_patch(project.reasons, output.reasons_patch)
    save_project(project, project_dir)
    return TurnResult(project=project, message=output.message, applied=True)
