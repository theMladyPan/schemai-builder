"""Tests for diff apply, revert, and persistence."""

from __future__ import annotations

import pytest

from schemai_builder.apply import DiffError, apply_and_record, apply_diff, revert
from schemai_builder.models import (
    AddComponent,
    Component,
    Net,
    Project,
    SchematicDiff,
    Sheet,
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


def test_add_sheet_then_component():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_sheets=[Sheet(number=2, title="page 2")])
    )
    assert [s.number for s in sch.sheets] == [1, 2]
    sch = apply_diff(
        sch, SchematicDiff(add_components=[AddComponent(library_id="R", sheet=2)])
    )
    assert sch.components[0].sheet == 2
    with pytest.raises(DiffError):
        apply_diff(sch, SchematicDiff(add_sheets=[Sheet(number=1)]))


def test_remove_component_prunes_net_pins():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", id="r1"),
                AddComponent(library_id="C", id="c1"),
            ],
            add_nets=[Net(name="n1", pins=["r1.B", "c1.A"])],
        ),
    )
    sch = apply_diff(sch, SchematicDiff(remove_ids=["c1"]))
    assert sch.nets[0].pins == ["r1.B"]


def test_remove_and_readd_same_net():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="R", id="r1")],
            add_nets=[Net(name="n1", pins=["r1.B"])],
        ),
    )
    sch = apply_diff(
        sch,
        SchematicDiff(remove_nets=["n1"], add_nets=[Net(name="n1", pins=["r1.A"])]),
    )
    assert sch.nets[0].pins == ["r1.A"]


def test_revert_negative_raises():
    project = Project(schematic=empty_schematic())
    with pytest.raises(ValueError):
        revert(project, -1)


def test_load_project_bad_library_id(tmp_path):
    project = Project(schematic=empty_schematic())
    project.schematic.components.append(Component(id="c1", library_id="NOPE", ref="R1"))
    path = tmp_path / "proj.json"
    path.write_text(project.model_dump_json())
    with pytest.raises(ValueError, match="NOPE"):
        load_project(path)


def test_duplicate_ref_rejected():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    with pytest.raises(DiffError):
        apply_diff(
            sch, SchematicDiff(add_components=[AddComponent(library_id="R", ref="R1")])
        )
