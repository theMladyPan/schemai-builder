"""Tests for SVG renderer and Manhattan router."""

from __future__ import annotations

import re
from itertools import pairwise

import pytest

from schemai_builder.apply import apply_diff
from schemai_builder.models import (
    AddComponent,
    Net,
    SchematicDiff,
    Sheet,
    empty_schematic,
)
from schemai_builder.render import render_all, render_sheet


def test_escapes_ref():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(add_components=[AddComponent(library_id="R", ref="R<1")]),
    )
    svg = render_sheet(sch, 1)
    assert "R&lt;1" in svg
    assert "R<1" not in svg


def test_two_pin_net_wire_and_label():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", x=100, y=100),
                AddComponent(library_id="C", x=400, y=100),
            ],
            add_nets=[Net(name="n1", pins=["c1.B", "c2.A"])],
        ),
    )
    svg = render_sheet(sch, 1)
    assert "<polyline" in svg
    assert ">n1<" in svg


def test_two_sheet_net_offpage():
    sch = empty_schematic()
    sch.sheets.append(Sheet(number=2))
    sch = apply_diff(
        sch,
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", x=100, y=100),
                AddComponent(library_id="C", x=100, y=100, sheet=2),
            ],
            add_nets=[Net(name="LINK", pins=["c1.B", "c2.A"])],
        ),
    )
    for number in (1, 2):
        svg = render_sheet(sch, number)
        assert "LINK" in svg
        assert "<polygon" in svg


def test_router_avoids_box():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[
                AddComponent(library_id="R", x=40, y=100),
                AddComponent(library_id="C", x=400, y=100),
                AddComponent(library_id="BOX", x=180, y=80),
            ],
            add_nets=[Net(name="n1", pins=["c1.B", "c2.A"])],
        ),
    )
    svg = render_sheet(sch, 1)
    m = re.search(r'<polyline points="([^"]+)"', svg)
    assert m
    pts = [tuple(map(int, p.split(","))) for p in m.group(1).split()]
    # not a single horizontal through the box band (box 180..300 x 80..240, +4px)
    assert not (len({y for _, y in pts}) == 1 and 76 < pts[0][1] < 244)
    # no leg crosses the inflated box
    for (x1, y1), (x2, y2) in pairwise(pts):
        if y1 == y2:
            assert not (76 < y1 < 244 and min(x1, x2) < 304 and max(x1, x2) > 176)
        else:
            assert not (176 < x1 < 304 and min(y1, y2) < 244 and max(y1, y2) > 76)


def test_single_pin_net_label():
    sch = apply_diff(
        empty_schematic(),
        SchematicDiff(
            add_components=[AddComponent(library_id="R", x=100, y=100)],
            add_nets=[Net(name="n1", pins=["c1.B"])],
        ),
    )
    svg = render_sheet(sch, 1)
    assert ">n1<" in svg
    assert "<polyline" not in svg


def test_render_all_keys_and_unknown_sheet():
    sch = empty_schematic()
    sch.sheets.append(Sheet(number=2))
    out = render_all(sch)
    assert set(out) == {1, 2}
    with pytest.raises(ValueError):
        render_sheet(sch, 3)
