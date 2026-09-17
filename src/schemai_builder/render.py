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
    ax,
    ay,
    bx,
    by,
    role: str,
    rects: list[tuple],
    ylimit: tuple[int, int] | None = None,
    tracks: list[tuple] | None = None,
    net: str = "",
    ends: tuple | None = None,
) -> list[tuple[int, int]]:
    if role == "power":
        orders = ("vh", "hv")
    elif role == "ground":
        orders = ("vh", "hv") if by >= ay else ("hv", "vh")
    else:
        orders = ("hv", "vh")

    def lane_ok(y: int) -> bool:
        return ylimit is None or ylimit[0] <= y <= ylimit[1]

    def clean(pts) -> bool:
        if _hits(pts, rects) or not all(lane_ok(p[1]) for p in pts):
            return False
        if tracks is None:
            return True
        full = pts
        if ends:  # include the pin lead-out segments in the track check
            full = (
                [(ends[0], ends[1]), (ax, ay)]
                + pts[1:-1]
                + [
                    (bx, by),
                    (ends[2], ends[3]),
                ]
            )
        return not _lane_conflict(full, net, tracks)

    offsets = tuple(o * GRID for o in range(9)) + tuple(-o * GRID for o in range(1, 9))
    for off in offsets:
        for order in orders:
            pts = _zpath(ax, ay, bx, by, order, off)
            if clean(pts):
                return pts
    if ylimit:
        lo = max(min(r[1] for r in rects) - GRID, ylimit[0])
        hi = min(max(r[3] for r in rects) + GRID, ylimit[1])
        for y in (lo, hi):
            pts = [(ax, ay), (ax, y), (bx, y), (bx, by)]
            if clean(pts):
                return pts
    # ponytail: no A*; pick the least-damage candidate when exhausted.
    # half-grid offsets let squeezed nets separate instead of overlapping
    best = _zpath(ax, ay, bx, by, orders[0], 0)
    best_score = None
    tl = tracks or []
    half: tuple = tuple(o * GRID // 2 for o in range(1, 18, 2))
    half += tuple(-o for o in half)
    for off in offsets + half:
        for order in orders:
            pts = _zpath(ax, ay, bx, by, order, off)
            score = (
                100
                * sum(
                    _seg_hits_rect(*pts[i], *pts[i + 1], r)
                    for i in range(len(pts) - 1)
                    for r in rects
                )
                + sum(
                    _lane_penalty(pts[i], pts[i + 1], net, tl)
                    for i in range(len(pts) - 1)
                )
                + 10 * sum(not lane_ok(p[1]) for p in pts)
            )
            if best_score is None or score < best_score:
                best, best_score = pts, score
        if best_score == 0:
            break
    return best


def _lane_penalty(a: tuple, b: tuple, net: str, tracks: list[tuple]) -> int:
    """0 when clear; exact overlap costs most, near-parallel scales with distance."""
    horiz = a[1] == b[1]
    if not (horiz or a[0] == b[0]):
        return 0
    if horiz:
        c, lo, hi = a[1], min(a[0], b[0]), max(a[0], b[0])
    else:
        c, lo, hi = a[0], min(a[1], b[1]), max(a[1], b[1])
    want = "h" if horiz else "v"
    worst = 0
    for o, cc, l, h, n in tracks:
        if o == want and n != net and abs(cc - c) < GRID and max(lo, l) < min(hi, h):
            d = abs(cc - c)
            worst = max(worst, 100 if d == 0 else GRID - d)
    return worst


def _lane_conflict(pts: list[tuple], net: str, tracks: list[tuple]) -> bool:
    """True if any segment runs within GRID of a foreign parallel track that overlaps."""
    for a, b in pairwise(pts):
        horiz = a[1] == b[1]
        if horiz:
            c, lo, hi = a[1], min(a[0], b[0]), max(a[0], b[0])
        else:
            c, lo, hi = a[0], min(a[1], b[1]), max(a[1], b[1])
        want = "h" if horiz else "v"
        for o, cc, l, h, n in tracks:
            if (
                o == want
                and n != net
                and abs(cc - c) < GRID
                and max(lo, l) < min(hi, h)
            ):
                return True
    return False


def _reserve(pts: list[tuple], net: str, tracks: list[tuple]) -> None:
    """Claim every routed segment so later nets keep GRID clearance."""
    for a, b in pairwise(pts):
        if a[1] == b[1] and a[0] != b[0]:
            tracks.append(("h", a[1], min(a[0], b[0]), max(a[0], b[0]), net))
        elif a[0] == b[0] and a[1] != b[1]:
            tracks.append(("v", a[0], min(a[1], b[1]), max(a[1], b[1]), net))


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
    """Inflated bodies; labels must avoid these (placed labels append themselves)."""
    return [
        (x - 4, y - 4, x2 + 4, y2 + 4)
        for c in comps
        for x, y, x2, y2 in [_bbox(c, lib)]
    ]


def _place_label(
    occupied: list[tuple],
    candidates: list[tuple],
    text: str,
    bounds: tuple | None = None,
) -> tuple:
    """First collision-free candidate wins; else spiral outward to a free box."""

    def free(box: tuple) -> bool:
        grown = (box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2)
        return not any(_overlap(grown, o) for o in occupied)

    def in_bounds(box: tuple) -> bool:
        return bounds is None or (
            box[0] >= bounds[0]
            and box[1] >= bounds[1]
            and box[2] <= bounds[2]
            and box[3] <= bounds[3]
        )

    for x, y, anchor in candidates:
        box = _text_box(x, y, text, anchor)
        if free(box) and in_bounds(box):
            occupied.append(box)
            return x, y, anchor
    x, y, anchor = candidates[-1]
    w = max(12, len(text) * 7)
    # ponytail: coarse spiral; real overflow packing if sheets get crowded
    best_box, best_spot, best_cost = None, None, None
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
            if not in_bounds(box):
                continue
            if free(box):
                occupied.append(box)
                return nx, ny, anchor
            cost = sum(
                max(0, min(box[2], o[2]) - max(box[0], o[0]))
                * max(0, min(box[3], o[3]) - max(box[1], o[1]))
                for o in occupied
            )
            if best_cost is None or cost < best_cost:
                best_box, best_spot, best_cost = box, (nx, ny, anchor), cost
    if best_spot is not None:
        occupied.append(best_box)
        return best_spot
    occupied.append(_text_box(x, y, text, anchor))
    return x, y, anchor


_COLS, _ROWS, _ROW_LETTERS = 17, 8, "ABCDEFGH"


def _plot_area(w: int, h: int) -> tuple[int, int, int, int]:
    """Routing/drawing area inside the sheet frame."""
    return 60, 50, w - 60, h - 95


def _zone(plot: tuple, x: float, y: float) -> str:
    """Grid reference like B16 for a point inside the plot area."""
    x0, y0, x1, y1 = plot
    col = max(1, min(_COLS, 1 + int((x - x0) / ((x1 - x0) / _COLS))))
    row = max(0, min(_ROWS - 1, int((y - y0) / ((y1 - y0) / _ROWS))))
    return f"{_ROW_LETTERS[row]}{col}"


def _draw_frame(parts: list[str], sheet, total: int) -> tuple:
    """EPLAN-style border, grid reference bands, title block; returns plot area."""
    w, h = sheet.width, sheet.height
    plot = _plot_area(w, h)
    x0, y0, x1, y1 = plot
    parts.append(f'<rect x="16" y="16" width="{w - 32}" height="{h - 32}" class="f"/>')
    parts.append(
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" class="f"/>'
    )
    cw, rh = (x1 - x0) / _COLS, (y1 - y0) / _ROWS
    for i in range(1, _COLS):
        cx = x0 + i * cw
        parts.append(f'<line x1="{cx}" y1="16" x2="{cx}" y2="{y0}" class="f"/>')
        parts.append(f'<line x1="{cx}" y1="{y1}" x2="{w - 16}" y2="{y1}" class="f"/>')
    for i in range(_COLS):
        parts.append(
            f'<text x="{x0 + (i + 0.5) * cw}" y="{y0 - 8}" text-anchor="middle" '
            f'font-size="10">{i + 1}</text>'
        )
    for i in range(1, _ROWS):
        ry = y0 + i * rh
        parts.append(f'<line x1="16" y1="{ry}" x2="{x0}" y2="{ry}" class="f"/>')
        parts.append(f'<line x1="{x1}" y1="{ry}" x2="{w - 16}" y2="{ry}" class="f"/>')
    for i in range(_ROWS):
        parts.append(
            f'<text x="38" y="{y0 + (i + 0.5) * rh + 4}" text-anchor="middle" '
            f'font-size="10">{_ROW_LETTERS[i]}</text>'
        )
    # title block, bottom right
    tx = x1 - 420
    parts.append(
        f'<rect x="{tx}" y="{y1}" width="420" height="{h - 16 - y1}" class="f"/>'
    )
    parts.append(
        f'<line x1="{tx + 250}" y1="{y1}" x2="{tx + 250}" y2="{h - 16}" class="f"/>'
    )
    parts.append(
        f'<line x1="{tx + 335}" y1="{y1}" x2="{tx + 335}" y2="{h - 16}" class="f"/>'
    )
    parts.append(
        f'<text x="{tx + 10}" y="{y1 + 44}" font-size="14">{escape(sheet.title or "")}</text>'
    )
    parts.append(f'<text x="{tx + 260}" y="{y1 + 22}" font-size="10">sheet</text>')
    parts.append(
        f'<text x="{tx + 260}" y="{y1 + 44}" font-size="13">{sheet.number} / {total}</text>'
    )
    return plot


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
        dx, dy = _DIR[_pin_side_world(comp, pin)]
        if dx:
            anchor = "end" if dx > 0 else "start"
            parts.append(
                f'<text x="{px - dx * 8}" y="{py + 4}" text-anchor="{anchor}" '
                f'font-size="9">{escape(pin.name)}</text>'
            )
        else:
            ty = py + 14 if dy < 0 else py - 6
            parts.append(
                f'<text x="{px}" y="{ty}" text-anchor="middle" '
                f'font-size="9">{escape(pin.name)}</text>'
            )
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
        '<g stroke="black" fill="none" stroke-width="1.5" font-family="sans-serif" '
        'font-size="12">'
    )
    parts = [
        header,
        "<style>text{stroke:none;fill:black}</style>",
        f'<rect x="0" y="0" width="{sheet.width}" height="{sheet.height}" fill="white"/>',
        group,
    ]
    plot = _draw_frame(parts, sheet, len(schematic.sheets))

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

    # pass 1: route longest nets first on a shared track registry, then flags
    ylimit = (plot[1] + GRID, plot[3] - GRID)
    infl = [(a - 10, b - 10, c + 10, d + 10) for a, b, c, d in bboxes.values()]
    pinsets = {
        net.name: _net_pins(schematic, net.pins, sheet_number, lib)
        for net in schematic.nets
    }
    nets = sorted(
        schematic.nets,
        key=lambda n: (
            -max(
                (
                    abs(p[0] - q[0]) + abs(p[1] - q[1])
                    for p, q in pairwise(pinsets[n.name])
                ),
                default=0,
            )
        ),
    )
    tracks: list[tuple] = []
    wire_boxes: list[tuple] = []
    routed: list[tuple] = []  # (net, pts_all, flag or None)
    for net in nets:
        pins = pinsets[net.name]
        offpage = len(_net_sheets(schematic, net.pins)) >= 2 and bool(pins)
        pts_all = []
        for (x1, y1, _ida, sa), (x2, y2, _idb, sb) in pairwise(pins):
            d1, d2 = _DIR[sa], _DIR[sb]
            sx, sy = x1 + GRID * d1[0], y1 + GRID * d1[1]
            ex, ey = x2 + GRID * d2[0], y2 + GRID * d2[1]
            body = _route(
                sx,
                sy,
                ex,
                ey,
                net.role,
                infl + envelopes,
                ylimit,
                tracks,
                net.name,
                (x1, y1, x2, y2),
            )
            pts = [(x1, y1), (sx, sy), *body[1:-1], (ex, ey), (x2, y2)]
            pts_all.append(pts)
            _reserve(pts, net.name, tracks)
        flag = None
        if offpage:
            fx = plot[2] - 1
            oy = max(plot[1] + 10, min(plot[3] - 10, pins[0][1]))
            px, py, _ida, sa = pins[0]
            dx, dy = _DIR[sa]
            sx, sy = px + GRID * dx, py + GRID * dy
            body = _route(
                sx,
                sy,
                fx,
                oy,
                net.role,
                infl + envelopes,
                ylimit,
                tracks,
                net.name,
                (px, py, fx, oy),
            )
            pts_all.append([(px, py), (sx, sy), *body[1:]])
            _reserve(pts_all[-1], net.name, tracks)
            refs = []
            for s in sorted(_net_sheets(schematic, net.pins) - {sheet_number}):
                rc = next(
                    c
                    for c in schematic.components
                    if c.sheet == s
                    and any(
                        (_resolve(schematic, p.partition(".")[0]) or c).id == c.id
                        for p in net.pins
                    )
                )
                bx0, by0, bx1, by1 = _bbox(rc, lib)
                refs.append((s, _zone(plot, (bx0 + bx1) / 2, (by0 + by1) / 2)))
            flag = (fx, oy, refs)
        for pts in pts_all:
            for p, q in zip(pts, pts[1:]):
                wire_boxes.append(_segment_box(p, q))
        routed.append((net, pts_all, flag))

    # pass 2: component bodies + ref/value labels (they must avoid wires too)
    occupied += wire_boxes
    for comp in comps:
        _draw_component(comp, parts, lib, occupied, plot)

    for _net, pts_all, flag in routed:
        if flag:
            fx, oy, _refs = flag
            parts.append(
                f'<polygon points="{fx},{oy - 7} {fx},{oy + 7} {fx + 13},{oy}"/>'
            )
        for pts in pts_all:
            parts.append(
                f'<polyline points="{" ".join(f"{px},{py}" for px, py in pts)}"/>'
            )

    # pass 3: net labels see bodies, every wire, and each other
    for net, pts_all, flag in routed:
        pins = pinsets[net.name]
        if flag:
            fx, oy, refs = flag
            for k, (s, z) in enumerate(refs):
                parts.append(
                    f'<text x="{fx - 8}" y="{oy - 14 - k * 13}" text-anchor="end" '
                    f'font-size="10">{s}-{escape(z)}</text>'
                )
        if not pins:
            continue
        cands = []
        if len(pins) == 1 and flag is None:
            px, py, _, side = pins[0]
            dx, dy = _DIR[side]
            anchor = "start" if dx > 0 else "end" if dx < 0 else "middle"
            cands = [
                (px + 12 * dx, py + 12 * dy, anchor),
                (px + 26 * dx, py + 26 * dy, anchor),
                (px + 12 * dx - 18 * dy, py + 12 * dy + 18 * dx, anchor),
                (px + 12 * dx + 18 * dy, py + 12 * dy - 18 * dx, anchor),
                (px, py - 6, "middle"),
            ]
            if dx > 0 and px > plot[2] - 120:  # dead-end hugging the right frame
                cands.append((plot[2] - 6, py - 6, "end"))
        else:
            horiz = []
            for pts in pts_all:
                for (ax, ay), (bx, by) in pairwise(pts):
                    if ay == by:
                        horiz.append((abs(bx - ax), (ax + bx) // 2, ay - 8))
            for _len, x, y in sorted(horiz, reverse=True):
                cands.append((x, y, "middle"))
            for pts in pts_all:
                for (ax, ay), (bx, by) in pairwise(pts):
                    if ax == bx:
                        cands.append((ax - 10, (ay + by) // 2, "end"))
            if len(pins) >= 2:
                mx = (pins[0][0] + pins[1][0]) // 2
                cands.append((mx, (pins[0][1] + pins[1][1]) // 2 - 6, "middle"))
        lx, ly, la = _place_label(occupied, cands, net.name, plot)
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
