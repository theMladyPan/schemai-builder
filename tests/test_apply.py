"""Tests for diff apply, revert, and persistence."""

from __future__ import annotations

import pytest

from schemai_builder.apply import DiffError, apply_and_record, apply_diff, revert
from schemai_builder.models import (
    AddComponent,
    Component,
    MoveComponent,
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
    project = Project(schematic=empty_schematic(), reasons="[1] use R\n")
    apply_and_record(
        project,
        SchematicDiff(add_components=[AddComponent(library_id="R", value="10k")]),
        user="add R",
        message="Added resistor.",
    )
    save_project(project, tmp_path)
    assert (tmp_path / "schematic.json").exists()
    assert (tmp_path / "reasons.md").exists()
    assert (tmp_path / "history.jsonl").exists()
    assert (tmp_path / "render" / "sheet-1.svg").exists()
    loaded = load_project(tmp_path)
    assert loaded == project


def test_save_project_clears_removed_sheet_svgs(tmp_path):
    sch2 = apply_diff(
        empty_schematic(), SchematicDiff(add_sheets=[Sheet(number=2, title="p2")])
    )
    save_project(Project(schematic=sch2), tmp_path)
    assert (tmp_path / "render" / "sheet-2.svg").exists()
    save_project(Project(schematic=empty_schematic()), tmp_path)
    assert not (tmp_path / "render" / "sheet-2.svg").exists()
    assert (tmp_path / "render" / "sheet-1.svg").exists()


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
    sch = empty_schematic()
    sch.components.append(Component(id="c1", library_id="NOPE", ref="R1"))
    (tmp_path / "schematic.json").write_text(sch.model_dump_json())
    with pytest.raises(ValueError, match="NOPE"):
        load_project(tmp_path)


def test_add_rotation_string_coerced():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(add_components=[AddComponent(library_id="BOX", rotation="0")]),
    )
    assert sch.components[0].rotation == 0


def test_move_rotation_string_coerced():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    sch = apply_diff(
        sch, SchematicDiff(move_components=[MoveComponent(id="c1", rotation="90")])
    )
    assert sch.components[0].rotation == 90


def test_net_pin_lookup_by_ref():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="BOX", ref="T1")],
            add_nets=[Net(name="n1", pins=["t1.1", "t1.5"])],
        ),
    )
    assert sch.nets[0].pins == ["t1.1", "t1.5"]


def test_net_pin_unknown_ref_or_component_rejected():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(add_components=[AddComponent(library_id="BOX", ref="T1")]),
    )
    with pytest.raises(DiffError):
        apply_diff(sch, SchematicDiff(add_nets=[Net(name="n1", pins=["t1.99"])]))
    with pytest.raises(DiffError):
        apply_diff(sch, SchematicDiff(add_nets=[Net(name="n2", pins=["xyz.1"])]))


def test_duplicate_ref_rejected():
    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    with pytest.raises(DiffError):
        apply_diff(
            sch, SchematicDiff(add_components=[AddComponent(library_id="R", ref="R1")])
        )
