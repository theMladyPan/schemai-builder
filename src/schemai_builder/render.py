"""SVG renderer with Manhattan routing and off-page connectors."""

from __future__ import annotations

from itertools import pairwise
from xml.sax.saxutils import escape

from .library import LIBRARY
from .models import Component, PinDef, Schematic

GRID = 20
_TICK = {"left": (-6, 0), "right": (6, 0), "top": (0, -6), "bottom": (0, 6)}
_DIR = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
_ROT_SIDE = {
    0: {"left": "left", "right": "right", "top": "top", "bottom": "bottom"},
    90: {"left": "top", "top": "right", "right": "bottom", "bottom": "left"},
    180: {"left": "right", "right": "left", "top": "bottom", "bottom": "top"},
    270: {"left": "bottom", "bottom": "right", "right": "top", "top": "left"},
}


def _pin_side_world(comp: Component, pin: PinDef) -> str:
    """Pin side after mirror+rotation; drives stub direction and label side."""
    side = pin.side
    if comp.mirror:
        side = {"left": "right", "right": "left", "top": "top", "bottom": "bottom"}[
            side
        ]
    return _ROT_SIDE[comp.rotation][side]


def _pin_world(comp: Component, pin: PinDef, lib: dict) -> tuple[int, int]:
    """World position of a pin: mirror, rotate, then translate to component origin."""
    entry = lib[comp.library_id]
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


def _bbox(comp: Component, lib: dict) -> tuple[int, int, int, int]:
    entry = lib[comp.library_id]
    w, h = entry.width, entry.height
    if comp.rotation in (90, 270):
        w, h = h, w
    return comp.x, comp.y, comp.x + w, comp.y + h


def _find_pin(comp: Component, name: str, lib: dict) -> PinDef | None:
    return next((p for p in lib[comp.library_id].pins if p.name == name), None)


def _pin_connect(comp: Component, pin: PinDef, lib: dict) -> tuple[int, int]:
    """Wire attach point: pin position plus tick length, i.e. outside the body."""
    px, py = _pin_world(comp, pin, lib)
    ddx, ddy = _TICK[_pin_side_world(comp, pin)]
    return px + ddx, py + ddy


def _resolve(schematic: Schematic, comp_id: str) -> Component | None:
    """Find a component by id or case-insensitive ref (same rules as apply.py)."""
    by_id = {c.id: c for c in schematic.components}
    comp = by_id.get(comp_id)
    if comp is None:
        comp = next(
            (c for c in schematic.components if c.ref.lower() == comp_id.lower()), None
        )
    return comp


def _net_pins(schematic: Schematic, net_name_pins: list[str], sheet: int, lib: dict):
    """Sorted [(x, y, comp_id, world_side)] for a net's pins located on this sheet."""
    out = []
    for pref in net_name_pins:
        comp = _resolve(schematic, pref.partition(".")[0])
        pin = _find_pin(comp, pref.partition(".")[2], lib) if comp else None
        if comp is not None and pin is not None and comp.sheet == sheet:
            out.append(
                (*_pin_connect(comp, pin, lib), comp.id, _pin_side_world(comp, pin))
            )
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def _net_sheets(schematic: Schematic, net_name_pins: list[str]) -> set[int]:
    return {
        comp.sheet
        for p in net_name_pins
        if (comp := _resolve(schematic, p.partition(".")[0])) is not None
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


def _route(
    ax, ay, bx, by, role: str, rects: list[tuple], ylimit: tuple[int, int] | None = None
) -> list[tuple[int, int]]:
    if role == "power":
        orders = ("vh", "hv")
    elif role == "ground":
        orders = ("vh", "hv") if by >= ay else ("hv", "vh")
    else:
        orders = ("hv", "vh")

    def lane_ok(y: int) -> bool:
        return ylimit is None or ylimit[0] <= y <= ylimit[1]

    for off in (0, GRID, -GRID, 2 * GRID, -2 * GRID):
        for order in orders:
            pts = _zpath(ax, ay, bx, by, order, off)
            if not _hits(pts, rects) and all(lane_ok(p[1]) for p in pts):
                return pts
    lo = max((min(r[1] for r in rects) - GRID), ylimit[0] if ylimit else 0)
    hi = min(max(r[3] for r in rects) + GRID, ylimit[1] if ylimit else 10**6)
    for y in (lo, hi):
        if not lane_ok(y):
            continue
        pts = [(ax, ay), (ax, y), (bx, y), (bx, by)]
        if not _hits(pts, rects):
            return pts
    # ponytail: no A*, accept leftover overlaps
    return _zpath(ax, ay, bx, by, orders[0], 0)


def _segment_box(p1: tuple, p2: tuple, pad: int = 3) -> tuple:
    """Thin obstacle rectangle along one wire segment; labels avoid these."""
    (x1, y1), (x2, y2) = p1, p2
    if y1 == y2:
        return (min(x1, x2) - 2, y1 - pad, max(x1, x2) + 2, y1 + pad)
    return (x1 - pad, min(y1, y2) - 2, x1 + pad, max(y1, y2) + 2)


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _text_box(x: int, y: int, text: str, anchor: str) -> tuple:
    """Estimated label rectangle (baseline y, anchor start/middle/end)."""
    w = max(12, len(text) * 7)
    x0 = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
    return (x0, y - 12, x0 + w, y + 2)


def _seed_occupied(comps, lib: dict) -> list[tuple]:
    """Inflated bodies plus ref/value text boxes; labels must avoid all of these."""
    occ = []
    for c in comps:
        x, y, x2, y2 = _bbox(c, lib)
        occ.append((x - 4, y - 4, x2 + 4, y2 + 4))
        cx = (x + x2) / 2
        rw = max(12, len(c.ref) * 7)
        occ.append((cx - rw / 2, y - 20, cx + rw / 2, y - 2))
        if c.value:
            vw = max(12, len(c.value) * 7)
            occ.append((cx - vw / 2, y2 + 2, cx + vw / 2, y2 + 18))
    return occ


def _place_label(
    occupied: list[tuple],
    candidates: list[tuple],
    text: str,
    bounds: tuple | None = None,
) -> tuple:
    """First collision-free candidate wins; else spiral outward to a free box."""

    def free(box: tuple) -> bool:
        return not any(_overlap(box, o) for o in occupied)

    def in_bounds(box: tuple) -> bool:
        return bounds is None or (
            box[0] >= 2
            and box[1] >= 2
            and box[2] <= bounds[0] - 2
            and box[3] <= bounds[1] - 2
        )

    for x, y, anchor in candidates:
        box = _text_box(x, y, text, anchor)
        if free(box) and in_bounds(box):
            occupied.append(box)
            return x, y, anchor
    x, y, anchor = candidates[-1]
    w = max(12, len(text) * 7)
    # ponytail: coarse spiral; real overflow packing if sheets get crowded
    for r in range(1, 9):
        for dx, dy in (
            (0, -r),
            (-r, 0),
            (r, 0),
            (0, r),
            (-r, -r),
            (r, -r),
            (-r, r),
            (r, r),
        ):
            nx, ny = x + dx * 14, y + dy * 14
            box = _text_box(nx, ny, text, anchor)
            if free(box) and in_bounds(box):
                occupied.append(box)
                return nx, ny, anchor
    occupied.append(_text_box(x, y, text, anchor))
    return x, y, anchor


def _draw_component(
    comp: Component, parts: list[str], lib: dict, occupied: list, bounds: tuple
) -> None:
    entry = lib[comp.library_id]
    x, y, x2, y2 = _bbox(comp, lib)
    kind = comp.library_id
    cy = (y + y2) // 2
    if kind == "C":
        cx = (x + x2) // 2
        parts.append(f'<line x1="{cx - 4}" y1="{y}" x2="{cx - 4}" y2="{y2}"/>')
        parts.append(f'<line x1="{cx + 4}" y1="{y}" x2="{cx + 4}" y2="{y2}"/>')
    elif kind == "L":
        # ponytail: three fixed arcs, proper IEC humps if density matters
        parts.append(
            f'<path d="M {x},{cy} a 13,13 0 0 1 26,0 a 13,13 0 0 1 26,0 a 13,13 0 0 1 26,0"/>'
        )
    elif kind == "FUSE":
        parts.append(f'<rect x="{x}" y="{y}" width="{x2 - x}" height="{y2 - y}"/>')
        parts.append(f'<line x1="{x - 6}" y1="{cy}" x2="{x2 + 6}" y2="{cy}"/>')
    elif kind == "D":
        parts.append(f'<polygon points="{x + 15},{y} {x + 15},{y2} {x + 50},{cy}"/>')
        parts.append(f'<line x1="{x + 50}" y1="{y}" x2="{x + 50}" y2="{y2}"/>')
    elif kind == "SW":
        parts.append(f'<circle cx="{x + 12}" cy="{cy}" r="3"/>')
        parts.append(f'<circle cx="{x + 68}" cy="{cy}" r="3"/>')
        parts.append(f'<line x1="{x + 12}" y1="{cy}" x2="{x + 62}" y2="{cy - 18}"/>')
        parts.append(f'<line x1="{x + 68}" y1="{cy}" x2="{x2}" y2="{cy}"/>')
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
    elif kind == "TERM":
        parts.append(f'<circle cx="{x + 20}" cy="{cy}" r="8"/>')
        parts.append(f'<circle cx="{x + 60}" cy="{cy}" r="8"/>')
        parts.append(f'<line x1="{x + 28}" y1="{cy}" x2="{x + 52}" y2="{cy}"/>')
    elif kind == "OPC":
        parts.append(f'<polygon points="{x},{y} {x},{y2} {x2},{cy}"/>')
    else:
        # R, BOX, and custom project parts draw as a generic block
        parts.append(f'<rect x="{x}" y="{y}" width="{x2 - x}" height="{y2 - y}"/>')
    for pin in entry.pins:
        px, py = _pin_world(comp, pin, lib)
        ddx, ddy = _TICK[_pin_side_world(comp, pin)]
        parts.append(f'<line x1="{px}" y1="{py}" x2="{px + ddx}" y2="{py + ddy}"/>')
    rx, ry, ra = _place_label(
        occupied,
        [((x + x2) / 2, y - 8, "middle"), (x - 10, cy, "end"), (x2 + 10, cy, "start")],
        comp.ref,
        bounds,
    )
    parts.append(
        f'<text x="{rx}" y="{ry}" text-anchor="{ra}" fill="black">{escape(comp.ref)}</text>'
    )
    if comp.value:
        vx, vy, va = _place_label(
            occupied,
            [
                ((x + x2) / 2, y2 + 16, "middle"),
                (x2 + 10, cy, "start"),
                (x - 10, cy, "end"),
            ],
            comp.value,
            bounds,
        )
        parts.append(
            f'<text x="{vx}" y="{vy}" text-anchor="{va}" fill="black">{escape(comp.value)}</text>'
        )


def render_sheet(
    schematic: Schematic, sheet_number: int, lib: dict | None = None
) -> str:
    """Render one sheet to SVG; raises ValueError for an unknown sheet."""
    lib = lib or LIBRARY
    sheet = next((s for s in schematic.sheets if s.number == sheet_number), None)
    if sheet is None:
        raise ValueError(f"unknown sheet {sheet_number}")
    comps = [c for c in schematic.components if c.sheet == sheet_number]
    bboxes = {c.id: _bbox(c, lib) for c in comps}

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

    occupied = _seed_occupied(comps, lib)

    # column envelope: >=3 near-aligned bodies act as one routing obstacle,
    # so trunks go around terminal banks instead of threading their gaps
    cols: dict[int, list[tuple]] = {}
    for bx0, by0, bx1, by1 in bboxes.values():
        cols.setdefault(round(bx0 / 20), []).append((bx0, by0, bx1, by1))
    envelopes = [
        (
            min(x[0] for x in g) - 10,
            min(x[1] for x in g) - 10,
            max(x[2] for x in g) + 10,
            max(x[3] for x in g) + 10,
        )
        for g in cols.values()
        if len(g) >= 3
    ]

    # pass 1: route every multi-pin net; collect wire boxes
    ylimit = (GRID, sheet.height - GRID)
    infl = [(a - 10, b - 10, c + 10, d + 10) for a, b, c, d in bboxes.values()]
    net_wires: dict[str, list] = {}
    wire_boxes: list[tuple] = []
    for net in schematic.nets:
        pins = _net_pins(schematic, net.pins, sheet_number, lib)
        if len(pins) < 2:
            continue
        pts_all = []
        for (x1, y1, _ida, sa), (x2, y2, _idb, sb) in pairwise(pins):
            d1, d2 = _DIR[sa], _DIR[sb]
            sx, sy = x1 + GRID * d1[0], y1 + GRID * d1[1]
            ex, ey = x2 + GRID * d2[0], y2 + GRID * d2[1]
            body = _route(sx, sy, ex, ey, net.role, infl + envelopes, ylimit)
            pts = [(x1, y1), (sx, sy), *body[1:-1], (ex, ey), (x2, y2)]
            pts_all.append(pts)
            for p, q in zip(pts, pts[1:]):
                wire_boxes.append(_segment_box(p, q))
        net_wires[net.name] = pts_all

    # pass 2: component bodies + ref/value labels (they must avoid wires too)
    occupied += wire_boxes
    for comp in comps:
        _draw_component(comp, parts, lib, occupied, (sheet.width, sheet.height))

    for pts_all in net_wires.values():
        for pts in pts_all:
            parts.append(
                f'<polyline points="{" ".join(f"{px},{py}" for px, py in pts)}"/>'
            )

    # pass 3: net labels see bodies, every wire, and each other
    for net in schematic.nets:
        pins = _net_pins(schematic, net.pins, sheet_number, lib)
        offpage = len(_net_sheets(schematic, net.pins)) >= 2 and bool(pins)
        if offpage:
            ox, oy = sheet.width - 40, pins[0][1]
            parts.append(
                f'<polygon points="{ox},{oy - 8} {ox},{oy + 8} {ox + 16},{oy}"/>'
            )
            lx, ly, _ = _place_label(
                occupied,
                [(ox - 6, oy + 4, "end"), (ox - 6, oy + 20, "end")],
                net.name,
                (sheet.width, sheet.height),
            )
            parts.append(
                f'<text x="{lx}" y="{ly}" text-anchor="end" fill="black">'
                f"{escape(net.name)}</text>"
            )
        if len(pins) == 1:
            if not offpage:
                px, py, _, side = pins[0]
                dx, dy = _DIR[side]
                anchor = "start" if dx > 0 else "end" if dx < 0 else "middle"
                lx, ly, la = _place_label(
                    occupied,
                    [
                        (px + 12 * dx, py + 12 * dy, anchor),
                        (px + 26 * dx, py + 26 * dy, anchor),
                        (px + 12 * dx - 18 * dy, py + 12 * dy + 18 * dx, anchor),
                        (px + 12 * dx + 18 * dy, py + 12 * dy - 18 * dx, anchor),
                        (px, py - 6, "middle"),
                    ],
                    net.name,
                    (sheet.width, sheet.height),
                )
                parts.append(
                    f'<text x="{lx}" y="{ly}" text-anchor="{la}" fill="black">'
                    f"{escape(net.name)}</text>"
                )
            continue
        if len(pins) < 2:
            continue
        cands = []
        for pts in net_wires[net.name]:
            for (ax, ay), (bx, by) in pairwise(pts):
                if ay == by:
                    cands.append(((ax + bx) // 2, ay - 8, "middle"))
                elif ax == bx:
                    cands.append((ax - 10, (ay + by) // 2, "end"))
        mx = (pins[0][0] + pins[1][0]) // 2
        cands.append((mx, (pins[0][1] + pins[1][1]) // 2 - 6, "middle"))
        lx, ly, la = _place_label(
            occupied, cands, net.name, (sheet.width, sheet.height)
        )
        parts.append(
            f'<text x="{lx}" y="{ly}" text-anchor="{la}" fill="black">'
            f"{escape(net.name)}</text>"
        )

    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_all(schematic: Schematic, lib: dict | None = None) -> dict[int, str]:
    """Render every sheet, keyed by sheet number."""
    return {s.number: render_sheet(schematic, s.number, lib) for s in schematic.sheets}
