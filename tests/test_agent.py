"""Tests for the create agent (FunctionModel, no live API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart

from schemai_builder.agent import run_turn
from schemai_builder.models import Project, empty_schematic
from schemai_builder.persist import load_project, save_project


def _tmp_project(tmp_path: Path) -> Path:
    save_project(Project(schematic=empty_schematic()), tmp_path)
    return tmp_path


def _model(responses: list[str] | None = None, prompts: list[str] | None = None):
    """FunctionModel replaying canned AgentOutput JSONs; records prompt text."""
    calls = {"n": 0}

    def fn(messages: list[ModelMessage], info) -> ModelResponse:
        part = messages[-1].parts[-1]
        content = part.content
        if not isinstance(content, str):
            content = "".join(c for c in content if isinstance(c, str))
        if prompts is not None:
            prompts.append(content)
        i = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(content=responses[i])])

    return FunctionModel(fn), calls


_ADD_R = {
    "message": "added resistor",
    "diff": {
        "add_components": [
            {"library_id": "R", "id": "rx", "ref": "R9", "x": 80, "y": 200}
        ]
    },
}


def test_run_turn_applies_diff(tmp_path):
    dir_ = _tmp_project(tmp_path)
    model, _ = _model(responses=[json.dumps(_ADD_R)])
    result = run_turn(dir_, "add a resistor", model=model)
    assert result.applied
    assert result.message == "added resistor"
    assert result.question is None
    project = load_project(dir_)
    assert len(project.schematic.components) == 1
    c = project.schematic.components[0]
    assert (c.library_id, c.id, c.ref, c.x, c.y) == ("R", "rx", "R9", 80, 200)
    assert (dir_ / "render" / "sheet-1.svg").exists()
    assert len(project.history) == 1
    assert project.history[0].user == "add a resistor"


def test_run_turn_garbage_raises_after_output_retries(tmp_path):
    dir_ = _tmp_project(tmp_path)
    model, calls = _model(responses=["not json at all"])
    with pytest.raises(UnexpectedModelBehavior):
        run_turn(dir_, "add a resistor", model=model)
    assert calls["n"] == 4  # 1 initial + 3 output retries


def test_run_turn_invalid_output_then_valid(tmp_path):
    dir_ = _tmp_project(tmp_path)
    bad = {
        "message": "m",
        "diff": "not a diff",
    }  # type-invalid, fails output validation
    model, calls = _model(
        responses=[json.dumps(bad), json.dumps(bad), json.dumps(_ADD_R)]
    )
    result = run_turn(dir_, "add a resistor", model=model)
    assert result.applied
    assert calls["n"] == 3
    assert len(load_project(dir_).schematic.components) == 1


def test_run_turn_question_skips_diff(tmp_path):
    dir_ = _tmp_project(tmp_path)
    out = dict(_ADD_R, question="which sheet?")
    model, _ = _model(responses=[json.dumps(out)])
    result = run_turn(dir_, "add a thing", model=model)
    assert not result.applied
    assert result.question == "which sheet?"
    assert load_project(dir_).schematic.components == []


def test_run_turn_retries_bad_diff_once(tmp_path):
    dir_ = _tmp_project(tmp_path)
    bad = {"message": "add", "diff": {"add_components": [{"library_id": "NOPE"}]}}
    model, calls = _model(responses=[json.dumps(bad), json.dumps(_ADD_R)])
    result = run_turn(dir_, "add a resistor", model=model)
    assert calls["n"] == 2
    assert result.applied
    assert len(load_project(dir_).schematic.components) == 1


def test_run_turn_retry_question_skips_apply(tmp_path):
    dir_ = _tmp_project(tmp_path)
    bad = {"message": "add", "diff": {"add_components": [{"library_id": "NOPE"}]}}
    out = dict(_ADD_R, question="which sheet?")
    model, _ = _model(responses=[json.dumps(bad), json.dumps(out)])
    result = run_turn(dir_, "add a resistor", model=model)
    assert not result.applied
    assert result.question == "which sheet?"
    assert load_project(dir_).schematic.components == []


def test_prompt_has_no_erc_and_includes_user_text(tmp_path):
    dir_ = _tmp_project(tmp_path)
    prompts: list[str] = []
    model, calls = _model(responses=[json.dumps(_ADD_R)], prompts=prompts)
    run_turn(dir_, "add a resistor", model=model)
    assert calls["n"] == 1
    assert "ERC" not in prompts[0]
    assert "## user\nadd a resistor" in prompts[0]
    assert "## library" in prompts[0]
    assert "R: pins A,B" in prompts[0]


def test_run_turn_text_file_in_prompt(tmp_path):
    dir_ = _tmp_project(tmp_path)
    prompts: list[str] = []
    model, calls = _model(responses=[json.dumps(_ADD_R)], prompts=prompts)
    result = run_turn(
        dir_,
        "use the attached notes",
        model=model,
        files=[("notes.txt", "R1 goes to GND".encode(), "text/plain")],
    )
    assert calls["n"] == 1
    assert result.applied
    assert "## file notes.txt" in prompts[0]
    assert "R1 goes to GND" in prompts[0]
    assert "## user\nuse the attached notes" in prompts[0]
    assert len(load_project(dir_).schematic.components) == 1


def test_run_turn_binary_non_image_skipped(tmp_path):
    dir_ = _tmp_project(tmp_path)
    prompts: list[str] = []
    model, _ = _model(responses=[json.dumps(_ADD_R)], prompts=prompts)
    run_turn(
        dir_,
        "add a resistor",
        model=model,
        files=[("blob.bin", b"\x00\xff\xfe", "application/octet-stream")],
    )
    assert "## file blob.bin" not in prompts[0]


def test_run_turn_image_file_no_crash(tmp_path):
    dir_ = _tmp_project(tmp_path)
    prompts: list[str] = []
    model, _ = _model(responses=[json.dumps(_ADD_R)], prompts=prompts)
    result = run_turn(
        dir_,
        "what is this",
        model=model,
        files=[("pic.png", b"\x89PNG fake bytes", "image/png")],
    )
    assert result.applied
    assert len(load_project(dir_).schematic.components) == 1
