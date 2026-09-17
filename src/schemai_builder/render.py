"""SVG renderer with Manhattan routing and off-page connectors."""

from __future__ import annotations

from itertools import pairwise
from xml.sax.saxutils import escape

from .library import LIBRARY
from .models import Component, PinDef, Schematic

GRID = 20
_TICK = {"left": (-6, 0), "right": (6, 0), "top": (0, -6), "bottom": (0, 6)}


def _pin_world(comp: Component, pin: PinDef) -> tuple[int, int]:
    """World position of a pin: mirror, rotate, then translate to component origin."""
    entry = LIBRARY[comp.library_id]
    dx, dy = pin.dx, pin.dy
    if comp.mirror:
        dx = entry.width - dx
    if comp.rotation == 0:
        return comp.x + dx, comp.y + dy
    if comp.rotation == 90:
        return comp.x + entry.height - dy, comp.y + dx
    if comp.rotation == 180:
        return comp.x + entry.width - dx, comp.y + entry.height - dy
    return comp.x + dy, comp.y + entry.width - dx


def _bbox(comp: Component) -> tuple[int, int, int, int]:
    entry = LIBRARY[comp.library_id]
    w, h = entry.width, entry.height
    if comp.rotation in (90, 270):
        w, h = h, w
    return comp.x, comp.y, comp.x + w, comp.y + h


def _find_pin(comp: Component, name: str) -> PinDef | None:
    return next((p for p in LIBRARY[comp.library_id].pins if p.name == name), None)


def _net_pins(schematic: Schematic, net_name_pins: list[str], sheet: int):
    """Sorted [(x, y, comp_id)] for a net's pins located on this sheet."""
    by_id = {c.id: c for c in schematic.components}
    out = []
    for pref in net_name_pins:
        comp = by_id.get(pref.partition(".")[0])
        pin = _find_pin(comp, pref.partition(".")[2]) if comp else None
        if comp is not None and pin is not None and comp.sheet == sheet:
            out.append((*_pin_world(comp, pin), comp.id))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def _net_sheets(schematic: Schematic, net_name_pins: list[str]) -> set[int]:
    by_id = {c.id: c for c in schematic.components}
    return {
        by_id[p.partition(".")[0]].sheet
        for p in net_name_pins
        if p.partition(".")[0] in by_id
    }


def _seg_hits_rect(x1: int, y1: int, x2: int, y2: int, r: tuple) -> bool:
    if y1 == y2:
        return r[1] < y1 < r[3] and min(x1, x2) < r[2] and max(x1, x2) > r[0]
    if x1 == x2:
        return r[0] < x1 < r[2] and min(y1, y2) < r[3] and max(y1, y2) > r[1]
    return False


def _hits(pts: list[tuple[int, int]], rects: list[tuple]) -> bool:
    return any(
        _seg_hits_rect(*pts[i], *pts[i + 1], r)
        for i in range(len(pts) - 1)
        for r in rects
    )


def _zpath(ax, ay, bx, by, order: str, off: int) -> list[tuple[int, int]]:
    if order == "hv":
        m = ay + off
        pts = [(ax, ay), (ax, m), (bx, m), (bx, by)]
    else:
        m = ax + off
        pts = [(ax, ay), (m, ay), (m, by), (bx, by)]
    out = [pts[0]]
    for p in pts[1:]:
        if p != out[-1]:
            out.append(p)
    return out


def _route(ax, ay, bx, by, role: str, rects: list[tuple]) -> list[tuple[int, int]]:
    if role == "power":
        orders = ("vh", "hv")
    elif role == "ground":
        orders = ("vh", "hv") if by >= ay else ("hv", "vh")
    else:
        orders = ("hv", "vh")
    for off in (0, GRID, -GRID, 2 * GRID, -2 * GRID):
        for order in orders:
            pts = _zpath(ax, ay, bx, by, order, off)
            if not _hits(pts, rects):
                return pts
    # ponytail: no A*, accept leftover overlaps
    return _zpath(ax, ay, bx, by, orders[0], 0)


def _draw_component(comp: Component, parts: list[str]) -> None:
    entry = LIBRARY[comp.library_id]
    x, y, x2, y2 = _bbox(comp)
    kind = comp.library_id
    if kind in ("R", "L", "BOX"):
        parts.append(f'<rect x="{x}" y="{y}" width="{x2 - x}" height="{y2 - y}"/>')
    elif kind == "C":
        cx = (x + x2) // 2
        parts.append(f'<line x1="{cx - 4}" y1="{y}" x2="{cx - 4}" y2="{y2}"/>')
        parts.append(f'<line x1="{cx + 4}" y1="{y}" x2="{cx + 4}" y2="{y2}"/>')
    elif kind == "GND":
        px, py = comp.x, comp.y
        for i, half in enumerate((20, 12, 4)):
            yy = py + i * 6
            parts.append(
                f'<line x1="{px - half}" y1="{yy}" x2="{px + half}" y2="{yy}"/>'
            )
    elif kind == "VCC":
        px, py = comp.x, comp.y
        parts.append(f'<line x1="{px}" y1="{py}" x2="{px}" y2="{py - 12}"/>')
        parts.append(
            f'<line x1="{px - 12}" y1="{py - 12}" x2="{px + 12}" y2="{py - 12}"/>'
        )
    elif kind == "OPC":
        parts.append(f'<polygon points="{x},{y} {x},{y2} {x2},{(y + y2) // 2}"/>')
    for pin in entry.pins:
        px, py = _pin_world(comp, pin)
        ddx, ddy = _TICK[pin.side]
        parts.append(f'<line x1="{px}" y1="{py}" x2="{px + ddx}" y2="{py + ddy}"/>')
    parts.append(
        f'<text x="{(x + x2) // 2}" y="{y - 4}" text-anchor="middle" fill="black">'
        f"{escape(comp.ref)}</text>"
    )
    if comp.value:
        parts.append(
            f'<text x="{(x + x2) // 2}" y="{y2 + 14}" text-anchor="middle" fill="black">'
            f"{escape(comp.value)}</text>"
        )


def render_sheet(schematic: Schematic, sheet_number: int) -> str:
    """Render one sheet to SVG; raises ValueError for an unknown sheet."""
    sheet = next((s for s in schematic.sheets if s.number == sheet_number), None)
    if sheet is None:
        raise ValueError(f"unknown sheet {sheet_number}")
    comps = [c for c in schematic.components if c.sheet == sheet_number]
    bboxes = {c.id: _bbox(c) for c in comps}

    header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet.width}" '
        f'height="{sheet.height}" viewBox="0 0 {sheet.width} {sheet.height}">'
    )
    group = (
        '<g stroke="black" fill="none" stroke-width="2" font-family="sans-serif" '
        'font-size="12">'
    )
    parts = [
        header,
        f'<rect x="0" y="0" width="{sheet.width}" height="{sheet.height}" fill="white"/>',
        group,
    ]
    if sheet.title:
        parts.append(f'<text x="20" y="24" fill="black">{escape(sheet.title)}</text>')

    for comp in comps:
        _draw_component(comp, parts)

    for net in schematic.nets:
        pins = _net_pins(schematic, net.pins, sheet_number)
        offpage = len(_net_sheets(schematic, net.pins)) >= 2 and bool(pins)
        if offpage:
            ox, oy = sheet.width - 40, pins[0][1]
            parts.append(
                f'<polygon points="{ox},{oy - 8} {ox},{oy + 8} {ox + 16},{oy}"/>'
            )
            parts.append(
                f'<text x="{ox - 6}" y="{oy + 4}" text-anchor="end" fill="black">'
                f"{escape(net.name)}</text>"
            )
        if len(pins) == 1:
            if not offpage:
                px, py, _ = pins[0]
                parts.append(
                    f'<text x="{px}" y="{py - 6}" text-anchor="middle" fill="black">'
                    f"{escape(net.name)}</text>"
                )
            continue
        if len(pins) < 2:
            continue
        for (x1, y1, ida), (x2, y2, idb) in pairwise(pins):
            rects = [
                (bx0 - 4, by0 - 4, bx1 + 4, by1 + 4)
                for cid, (bx0, by0, bx1, by1) in bboxes.items()
                if cid not in (ida, idb)
            ]
            pts = _route(x1, y1, x2, y2, net.role, rects)
            parts.append(
                f'<polyline points="{" ".join(f"{px},{py}" for px, py in pts)}"/>'
            )
        mx = (pins[0][0] + pins[1][0]) // 2
        my = (pins[0][1] + pins[1][1]) // 2 - 6
        parts.append(
            f'<text x="{mx}" y="{my}" text-anchor="middle" fill="black">'
            f"{escape(net.name)}</text>"
        )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_all(schematic: Schematic) -> dict[int, str]:
    """Render every sheet, keyed by sheet number."""
    return {s.number: render_sheet(schematic, s.number) for s in schematic.sheets}
