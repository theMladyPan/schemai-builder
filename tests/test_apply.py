"""Tests for diff apply, revert, and persistence."""

from __future__ import annotations

import pytest

from schemai_builder.apply import DiffError, apply_and_record, apply_diff, revert
from schemai_builder.models import (
    AddComponent,
    Net,
    Project,
    SchematicDiff,
    empty_schematic,
)
from schemai_builder.persist import load_project, save_project


def test_add_auto_ref_and_place():
    sch = empty_schematic()
    sch = apply_diff(
        sch,
        SchematicDiff(
            add_components=[AddComponent(library_id="R"), AddComponent(library_id="C")]
        ),
    )
    refs = [c.ref for c in sch.components]
    assert refs == ["R1", "C1"]
    assert (sch.components[0].x, sch.components[0].y) == (100, 100)
    assert (sch.components[1].x, sch.components[1].y) == (180, 100)


def test_unknown_library_id():
    with pytest.raises(DiffError):
        apply_diff(
            empty_schematic(),
            SchematicDiff(add_components=[AddComponent(library_id="ZZZ")]),
        )


def test_bad_net_pin():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    with pytest.raises(DiffError):
        apply_diff(sch, SchematicDiff(add_nets=[Net(name="n1", pins=["c1.ZZZ"])]))


def test_remove_unknown_id():
    with pytest.raises(DiffError):
        apply_diff(empty_schematic(), SchematicDiff(remove_ids=["nope"]))


def test_persist_roundtrip(tmp_path):
    project = Project(schematic=empty_schematic())
    apply_and_record(
        project,
        SchematicDiff(add_components=[AddComponent(library_id="R", value="10k")]),
    )
    path = tmp_path / "proj.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded == project


def test_revert_undoes_last_add():
    project = Project(schematic=empty_schematic())
    apply_and_record(
        project, SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    apply_and_record(
        project, SchematicDiff(add_components=[AddComponent(library_id="C")])
    )
    revert(project)
    assert [c.ref for c in project.schematic.components] == ["R1"]
    assert len(project.history) == 1


def test_duplicate_ref_rejected():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    with pytest.raises(DiffError):
        apply_diff(
            sch, SchematicDiff(add_components=[AddComponent(library_id="R", ref="R1")])
        )
