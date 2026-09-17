"""Layout quality gate — the bar for "looks like the Metrotech target sheets".

Run against the PSU fixture (F1, two PSUs, seven terminals, cross-sheet nets):
straight parallel lanes, no wire through a body, clearance between foreign
wires, few bends, deterministic output. Fails on the pre-rework engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemai_builder import quality
from schemai_builder.layout import relayout
from schemai_builder.library import library_for
from schemai_builder.models import Project
from schemai_builder.persist import save_project
from schemai_builder.render import render_sheet

FIXTURE = Path(__file__).parents[1] / "fixtures" / "psu_project.json"


@pytest.fixture()
def psu_project() -> Project:
    data = json.loads(FIXTURE.read_text())
    return Project(schematic=data["schematic"], parts=data["parts"])


def _sheet1_svg(tmp_path: Path, project: Project) -> str:
    save_project(project, tmp_path)  # relayouts + renders
    return (tmp_path / "render" / "sheet-1.svg").read_text()


def test_deterministic(tmp_path, psu_project):
    a = _sheet1_svg(tmp_path, psu_project)
    data = json.loads(FIXTURE.read_text())
    b = _sheet1_svg(tmp_path / "second", Project(schematic=data["schematic"], parts=data["parts"]))
    assert a == b


def test_no_wire_through_body(tmp_path, psu_project):
    svg = _sheet1_svg(tmp_path, psu_project)
    assert quality.body_intersections(svg) == 0


def test_lane_clearance(tmp_path, psu_project):
    svg = _sheet1_svg(tmp_path, psu_project)
    bad = quality.clearance_violations(svg)
    assert not bad, f"{len(bad)} clearance violations: {bad[:3]}"


def test_mostly_straight_lanes(tmp_path, psu_project):
    """Target style: few corners relative to wire volume."""
    svg = _sheet1_svg(tmp_path, psu_project)
    segs = quality.sheet_segments(svg)
    # 15+ nets on this sheet; a clean sheet needs far fewer bends than segments
    assert quality.bends(svg) <= len(segs) // 2, (
        f"{quality.bends(svg)} bends for {len(segs)} segments"
    )


def test_few_crossings(tmp_path, psu_project):
    svg = _sheet1_svg(tmp_path, psu_project)
    assert quality.crossings(svg) <= 10
