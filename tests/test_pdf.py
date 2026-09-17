"""Tests for SVG-to-PDF export."""

from __future__ import annotations

from schemai_builder.models import empty_schematic
from schemai_builder.pdf import svg_to_pdf
from schemai_builder.render import render_sheet


def test_svg_to_pdf():
    svg = render_sheet(empty_schematic(), 1)
    pdf = svg_to_pdf(svg)
    if pdf is not None:
        assert pdf.startswith(b"%PDF")
