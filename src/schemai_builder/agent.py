"""Python API for the create agent: one structured-output turn per run_turn."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model
from pydantic_ai.output import PromptedOutput

from .apply import DiffError, apply_and_record
from .config.settings import get_settings
from .erc import ErcIssue, run_erc
from .library import library_for
from .models import Project, ReasonsPatch, SchematicDiff
from .persist import load_project, save_project
from .prompt import build_prompt, history_tail, library_text, netlist_text, sheet_pngs
from .reasons import apply_reasons_patch, format_numbered, split_paragraphs

INSTRUCTIONS = """\
You edit electrical schematics via a structured diff. Components reference \
library ids only; never invent pinouts. ## library lists built-ins and this \
project's parts. If a needed part is missing, create it with add_parts — pin \
names and sides only; placement and symbol drawing are handled for you, and \
the part becomes reusable. Never send coordinates. If the sheet, net, group, or \
component is unclear, return a question instead of guessing. Keep reasons.md \
short: delete stale ADRs, append only what matters. Open nets during creation \
are fine.\
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


def _run_agent(
    model: Model | None,
    prompt: str,
    project: Project,
    *,
    output_type: type[BaseModel],
    instructions: str,
    extra_images: list[BinaryContent] | None = None,
) -> BaseModel:
    agent = Agent(
        model or get_settings().llm_model,
        output_type=PromptedOutput(output_type),
        instructions=instructions,
        retries={"output": 3},
    )
    images = [
        BinaryContent(data=png, media_type="image/png")
        for png in sheet_pngs(project.schematic, library_for(project)).values()
    ]
    images += extra_images or []
    content: str | list[str | BinaryContent] = [prompt, *images] if images else prompt
    return agent.run_sync(content).output


def _file_parts(
    files: list[tuple[str, bytes, str]] | None,
) -> tuple[list[BinaryContent], str]:
    """Split attachments: images become BinaryContent, decodable text joins prompt."""
    images: list[BinaryContent] = []
    texts: list[str] = []
    for name, data, media_type in files or []:
        if media_type.startswith("image/"):
            images.append(BinaryContent(data=data, media_type=media_type))
            continue
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            continue  # ponytail: ignore non-image binaries
        texts.append(f"## file {name}\n{decoded}")
    return images, "\n\n".join(texts)


def run_turn(
    project_dir: Path,
    text: str,
    *,
    model: Model | None = None,
    files: list[tuple[str, bytes, str]] | None = None,  # name, data, media_type
) -> TurnResult:
    """Load the project, run one agent turn, apply and persist the result."""
    project = load_project(project_dir)
    prompt = build_prompt(project, text)
    images, file_text = _file_parts(files)
    if file_text:
        prompt = f"{prompt}\n\n{file_text}"
    output = _run_agent(
        model,
        prompt,
        project,
        output_type=AgentOutput,
        instructions=INSTRUCTIONS,
        extra_images=images,
    )
    if output.question:
        apply_and_record(
            project,
            SchematicDiff(),
            user=text,
            message=output.message + f" [question: {output.question}]",
        )
        save_project(project, project_dir)
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
        output = _run_agent(
            model,
            retry_prompt,
            project,
            output_type=AgentOutput,
            instructions=INSTRUCTIONS,
            extra_images=images,
        )
        if output.question:
            apply_and_record(
                project,
                SchematicDiff(),
                user=text,
                message=output.message + f" [question: {output.question}]",
            )
            save_project(project, project_dir)
            return TurnResult(
                project=project,
                message=output.message,
                question=output.question,
                applied=False,
            )
        diff = output.diff or SchematicDiff()
        apply_and_record(project, diff, user=text, message=output.message)
    if output.reasons_patch:
        project.reasons = apply_reasons_patch(project.reasons, output.reasons_patch)
    save_project(project, project_dir)
    return TurnResult(project=project, message=output.message, applied=True)


class ReviewOutput(BaseModel):
    """Structured LLM output for an advisory review."""

    message: str


class ReviewResult(BaseModel):
    """Outcome of one review turn: LLM message plus deterministic ERC issues."""

    message: str
    issues: list[ErcIssue]


REVIEW_INSTRUCTIONS = """\
You review electrical schematics. Advisory only: do NOT propose applying a \
diff, just report issues. Components reference library ids; never invent \
pinouts. Open nets may be work in progress, flag them but do not treat them \
as errors.\
"""


def review_turn(project_dir: Path, *, model: Model | None = None) -> ReviewResult:
    """Run one read-only review turn: reasons, netlist, ERC, history, sheet PNGs."""
    project = load_project(project_dir)
    issues = run_erc(project.schematic, library_for(project))
    erc = "\n".join(f"{i.kind}: {i.detail}" for i in issues) or "(none)"
    numbered = format_numbered(split_paragraphs(project.reasons)) or "(none)"
    prompt = "\n".join(
        [
            "## reasons",
            numbered,
            "",
            "## netlist",
            netlist_text(project.schematic),
            "",
            library_text(project),
            "",
            "## erc",
            erc,
            "",
            "## recent",
            history_tail(project),
        ]
    )
    output = _run_agent(
        model,
        prompt,
        project,
        output_type=ReviewOutput,
        instructions=REVIEW_INSTRUCTIONS,
    )
    assert isinstance(output, ReviewOutput)
    return ReviewResult(message=output.message, issues=issues)
