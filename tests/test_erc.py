"""Tests for advisory ERC checks."""

from __future__ import annotations

from schemai_builder.apply import apply_diff
from schemai_builder.erc import run_erc
from schemai_builder.models import AddComponent, Net, SchematicDiff, empty_schematic


def test_empty_schematic_no_issues():
    assert run_erc(empty_schematic()) == []


def test_resistor_without_nets():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(add_components=[AddComponent(library_id="R", id="r1")]),
    )
    assert [(i.kind, i.detail) for i in run_erc(sch)] == [
        ("unconnected_pin", "r1.A"),
        ("unconnected_pin", "r1.B"),
        ("unused_component", "r1"),
    ]


def test_single_ended_net():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="R", id="r1")],
            add_nets=[Net(name="n1", pins=["r1.A"])],
        ),
    )
    assert [("single_ended_net", "n1")] == [
        (i.kind, i.detail) for i in run_erc(sch) if i.kind == "single_ended_net"
    ]


def test_pin_on_two_nets_is_short():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="R", id="r1")],
            add_nets=[
                Net(name="n1", pins=["r1.A", "r1.B"]),
                Net(name="n2", pins=["r1.A"]),
            ],
        ),
    )
    assert [("short", "r1.A")] == [
        (i.kind, i.detail) for i in run_erc(sch) if i.kind == "short"
    ]


def test_fully_connected_rc_no_issues_for_those():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", id="r1"),
                AddComponent(library_id="C", id="c1"),
            ],
            add_nets=[Net(name="n1", pins=["r1.A", "r1.B", "c1.A"])],
        ),
    )
    assert [(i.kind, i.detail) for i in run_erc(sch)] == [("unconnected_pin", "c1.B")]
