"""Tests for the review agent (FunctionModel, no live API)."""

from __future__ import annotations

import json
from pathlib import Path

from schemai_builder.agent import review_turn
from schemai_builder.models import Net, Project, empty_schematic
from schemai_builder.persist import load_project, save_project

from test_agent import _model


def test_review_turn_reports_erc_and_is_read_only(tmp_path: Path):
    sch = empty_schematic()
    sch.nets.append(Net(name="A", pins=["r1.1"]))
    save_project(Project(schematic=sch, reasons="keep it simple"), tmp_path)
    prompts: list[str] = []
    model, calls = _model(
        responses=[json.dumps({"message": "looks fine"})], prompts=prompts
    )
    result = review_turn(tmp_path, model=model)
    assert calls["n"] == 1
    assert result.message == "looks fine"
    assert any(i.kind == "single_ended_net" for i in result.issues)
    assert "## erc" in prompts[0]
    assert "## library" in prompts[0]
    assert "single_ended_net: A" in prompts[0]
    assert "[1] keep it simple" in prompts[0]
    project = load_project(tmp_path)
    assert project.history == []
    assert project.reasons == "keep it simple"
    assert len(project.schematic.nets) == 1


def test_review_turn_no_issues(tmp_path: Path):
    save_project(Project(schematic=empty_schematic()), tmp_path)
    prompts: list[str] = []
    model, calls = _model(
        responses=[json.dumps({"message": "empty, fine"})], prompts=prompts
    )
    result = review_turn(tmp_path, model=model)
    assert result.message == "empty, fine"
    assert result.issues == []
    assert calls["n"] == 1
    assert "## erc\n(none)" in prompts[0]
