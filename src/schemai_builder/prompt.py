"""Prompt builder and SVG-to-PNG conversion for the create agent."""

from __future__ import annotations

from .library import LIBRARY
from .models import Project, Schematic
from .reasons import format_numbered, split_paragraphs
from .render import render_all


def netlist_text(schematic: Schematic) -> str:
    """Compact netlist: sheets, components, nets."""
    lines = ["sheets:"]
    lines += [f"{s.number} {s.title}" for s in schematic.sheets]
    lines.append("components:")
    lines += [
        f"{c.id} {c.library_id} {c.ref} {c.value} sheet={c.sheet} @{c.x},{c.y} rot={c.rotation}"
        for c in schematic.components
    ]
    lines.append("nets:")
    lines += [f"{n.name} {n.role}: {', '.join(n.pins)}" for n in schematic.nets]
    return "\n".join(lines)


def library_text() -> str:
    """Catalog of valid library ids and their pin names."""
    lines = ["## library", "components must use these ids; pins per part:"]
    lines += [
        f"{entry.id}: pins {','.join(p.name for p in entry.pins)}"
        for entry in LIBRARY.values()
    ]
    lines.append('net pin refs use "component_id.pin", e.g. r1.A')
    return "\n".join(lines)


def history_tail(project: Project, n: int = 10) -> str:
    """Last n history entries, one line each."""
    lines = []
    for e in project.history[-n:]:
        d = e.diff
        lines.append(
            f"user={e.user!r} message={e.message!r}"
            f" +{len(d.add_components)}c -{len(d.remove_ids)}c"
            f" +{len(d.add_nets)}n"
        )
    return "\n".join(lines)


def build_prompt(project: Project, user_text: str) -> str:
    """Full create-agent prompt: reasons, netlist, history, user text."""
    numbered = format_numbered(split_paragraphs(project.reasons)) or "(none)"
    return "\n".join(
        [
            "## reasons",
            numbered,
            "",
            "## netlist",
            netlist_text(project.schematic),
            "",
            library_text(),
            "",
            "## recent",
            history_tail(project),
            "",
            "## user",
            user_text,
        ]
    )


def svg_to_png(svg: str) -> bytes | None:
    """Rasterize SVG via cairosvg; None if cairo is missing or fails."""
    # ponytail: skip PNG if cairo missing
    try:
        import cairosvg
    except ImportError:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode())
    except Exception:
        return None


def sheet_pngs(schematic: Schematic) -> dict[int, bytes]:
    """Render every sheet to PNG; omit sheets that fail to rasterize."""
    pngs = {}
    for number, svg in render_all(schematic).items():
        png = svg_to_png(svg)
        if png is not None:
            pngs[number] = png
    return pngs
