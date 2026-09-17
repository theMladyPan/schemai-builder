"""Tests for prompt builder and svg-to-png."""

from __future__ import annotations

from schemai_builder.apply import apply_diff
from schemai_builder.library import LIBRARY
from schemai_builder.models import (
    AddComponent,
    HistoryEntry,
    Net,
    Project,
    SchematicDiff,
    Sheet,
    empty_schematic,
)
from schemai_builder.prompt import (
    build_prompt,
    history_tail,
    netlist_text,
    sheet_pngs,
    svg_to_png,
)


def make_project() -> Project:
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(add_sheets=[Sheet(number=2, title="page 2")]),
    )
    sch = apply_diff(
        sch,
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", id="r1", value="10k", sheet=1),
                AddComponent(library_id="C", id="c1", value="100n", sheet=2),
            ],
            add_nets=[Net(name="VCC", role="power", pins=["r1.A", "c1.A"])],
        ),
    )
    return Project(schematic=sch, reasons="use IEC symbols\n\nground at bottom")


def test_netlist_contains_components_and_pins():
    text = netlist_text(make_project().schematic)
    assert "r1 R R1 10k sheet=1" in text
    assert "c1 C C1 100n sheet=2" in text
    assert "VCC power: r1.A, c1.A" in text
    assert "2 page 2" in text


def test_build_prompt_numbered_reasons_and_no_erc_or_svg():
    prompt = build_prompt(make_project(), "add a pull-up")
    assert "[1] use IEC symbols" in prompt
    assert "[2] ground at bottom" in prompt
    assert "## user\nadd a pull-up" in prompt
    assert "ERC" not in prompt
    assert "<svg" not in prompt


def test_build_prompt_lists_all_library_ids():
    prompt = build_prompt(make_project(), "add a pull-up")
    assert "## library" in prompt
    for lib_id in LIBRARY:
        assert lib_id in prompt


def test_build_prompt_empty_reasons():
    prompt = build_prompt(Project(schematic=empty_schematic()), "hi")
    assert "## reasons\n(none)" in prompt


def test_history_tail_last_n():
    project = Project(schematic=empty_schematic())
    for i in range(12):
        project.history.append(
            HistoryEntry(
                diff=SchematicDiff(add_components=[AddComponent(library_id="R")]),
                user=f"u{i}",
                message=f"m{i}",
            )
        )
    tail = history_tail(project)
    lines = tail.split("\n")
    assert len(lines) == 10
    assert "u11" in tail
    assert "u2" in tail
    assert "user='u0'" not in tail
    assert "user='u1'" not in tail
    assert "+1c -0c +0n" in lines[0]


def test_svg_to_png_magic_or_none():
    from schemai_builder.render import render_all

    sch = apply_diff(
        empty_schematic(), SchematicDiff(add_components=[AddComponent(library_id="R")])
    )
    svg = render_all(sch)[1]
    png = svg_to_png(svg)
    if png is not None:
        assert png.startswith(b"\x89PNG")


def test_sheet_pngs_dict():
    sch = make_project().schematic
    pngs = sheet_pngs(sch)
    for number, png in pngs.items():
        assert number in {1, 2}
        assert png.startswith(b"\x89PNG")
