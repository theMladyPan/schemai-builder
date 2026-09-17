"""Tests for project parts (LLM-created) and derived layout."""

from __future__ import annotations

import pytest

from schemai_builder.apply import DiffError, apply_and_record, apply_diff, revert
from schemai_builder.layout import relayout
from schemai_builder.models import (
    AddComponent,
    LibraryEntry,
    Net,
    PartDef,
    PartPin,
    PinDef,
    Project,
    Schematic,
    SchematicDiff,
    Sheet,
    empty_schematic,
)
from schemai_builder.persist import load_project, save_project
from schemai_builder.render import render_sheet


def _psu() -> PartDef:
    return PartDef(
        id="PSU",
        description="AC/DC module",
        prefix="PS",
        pins=[
            PartPin(name="L", side="left"),
            PartPin(name="PE", side="left"),
            PartPin(name="+V", side="right"),
        ],
    )


def _entry() -> LibraryEntry:
    return LibraryEntry(
        id="X",
        prefix="X",
        width=80,
        height=40,
        pins=[
            PinDef(name="A", dx=0, dy=20, side="left"),
            PinDef(name="+V", dx=80, dy=20, side="right"),
        ],
    )


def test_add_part_and_use_it():
    project = Project(schematic=empty_schematic())
    apply_and_record(
        project,
        SchematicDiff(
            add_parts=[_psu()], add_components=[AddComponent(library_id="PSU")]
        ),
    )
    assert [p.id for p in project.parts] == ["PSU"]
    comp = project.schematic.components[0]
    assert comp.library_id == "PSU"
    assert comp.ref == "PS1"  # prefix from the part definition


def test_add_part_conflicts():
    project = Project(schematic=empty_schematic())
    with pytest.raises(DiffError):
        apply_and_record(
            project,
            SchematicDiff(
                add_parts=[PartDef(id="R", pins=[PartPin(name="A", side="left")])]
            ),
        )
    apply_and_record(project, SchematicDiff(add_parts=[_psu()]))
    with pytest.raises(DiffError):
        apply_and_record(project, SchematicDiff(add_parts=[_psu()]))
    with pytest.raises(DiffError):
        apply_and_record(
            project,
            SchematicDiff(
                add_parts=[PartDef(id="no.pins", pins=[PartPin(name="A", side="left")])]
            ),
        )


def test_parts_persist_roundtrip(tmp_path):
    project = Project(schematic=empty_schematic())
    apply_and_record(project, SchematicDiff(add_parts=[_psu()]))
    apply_and_record(
        project,
        SchematicDiff(add_components=[AddComponent(library_id="PSU")]),
    )
    save_project(project, tmp_path)
    loaded = load_project(tmp_path)
    assert [p.id for p in loaded.parts] == ["PSU"]
    assert loaded.schematic.components[0].library_id == "PSU"


def test_revert_replays_parts():
    project = Project(schematic=empty_schematic())
    apply_and_record(project, SchematicDiff(add_parts=[_psu()]))
    apply_and_record(
        project, SchematicDiff(add_components=[AddComponent(library_id="PSU")])
    )
    revert(project, 1)  # drop the component, keep the part
    assert [p.id for p in project.parts] == ["PSU"]
    assert project.schematic.components == []


def test_relayout_bands_by_role():
    sch = empty_schematic()
    library = {"PSU": _entry(), "GND": _entry()}
    sch = apply_diff(
        sch,
        SchematicDiff(
            add_components=[
                AddComponent(library_id="PSU", id="ps1"),
                AddComponent(library_id="GND", id="g1"),
                AddComponent(library_id="PSU", id="ps2"),
            ],
            add_nets=[
                Net(name="+24V", role="power", pins=["ps1.+V"]),
                Net(name="gndnet", role="ground", pins=["g1.A"]),
                Net(name="sig", role="signal", pins=["ps2.+V"]),
            ],
        ),
        library=library,
    )
    by_id = {c.id: c for c in sch.components}
    assert by_id["ps1"].y == 100  # power band
    assert by_id["g1"].y == 560  # ground band
    assert by_id["ps2"].y == 300  # signal band


def test_pinned_component_survives_relayout():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="R", id="r1")],
            move_components=[{"id": "r1", "x": 500, "y": 100}],
        ),
    )
    by_r1 = sch.components[0]
    assert by_r1.pinned and (by_r1.x, by_r1.y) == (500, 100)
    relayout(sch, {"R": _entry()})
    assert (by_r1.x, by_r1.y) == (500, 100)
    by_r1.pinned = False
    relayout(sch, {"R": _entry()})
    assert (by_r1.x, by_r1.y) == (60, 300)  # back to derived placement


def test_part_symbol_renders_generic_block():
    project = Project(schematic=empty_schematic())
    apply_and_record(
        project,
        SchematicDiff(
            add_parts=[_psu()],
            add_components=[
                AddComponent(library_id="PSU", id="ps1", value="230V->24V")
            ],
            add_nets=[Net(name="mains", role="power", pins=["ps1.L"])],
        ),
    )
    from schemai_builder.library import library_for

    svg = render_sheet(project.schematic, 1, library_for(project))
    assert "<rect" in svg
    assert ">PS1<" in svg
    assert "mains" in svg


def test_static_symbol_render_kinds():
    sch = apply_diff(
        Schematic(sheets=[Sheet(number=1)], components=[], nets=[]),
        SchematicDiff(
            add_components=[
                AddComponent(library_id=k, id=f"k{i}")
                for i, k in enumerate(["R", "L", "FUSE", "D", "SW", "TERM"])
            ]
        ),
    )
    svg = render_sheet(sch, 1)
    assert "<path" in svg  # L arcs
    assert svg.count("<polygon") >= 1  # D triangle
    assert svg.count("<circle") >= 4  # SW dots + TERM circles
