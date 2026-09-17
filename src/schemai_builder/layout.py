"""Derived layout: place unpinned components by graph structure and net roles."""

from __future__ import annotations

import networkx as nx

from .models import Schematic

MARGIN_X = 60
LAYER_GUTTER = 80
SLOT_H = 180
BAND_Y = {"power": 100, "signal": 300, "ground": 560}
# ponytail: fixed bands for the default 1000x700 sheet; per-sheet bands if crowds


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _resolve(comps: dict[str, object], comp_id: str):
    """Find a component by id or case-insensitive ref, same rule as apply.py."""
    if comp_id in comps:
        return comps[comp_id]
    low = comp_id.lower()
    return next((c for c in comps.values() if c.ref.lower() == low), None)


def _rot_size(comp, library) -> tuple[int, int]:
    entry = library[comp.library_id]
    w, h = entry.width, entry.height
    return (h, w) if comp.rotation in (90, 270) else (w, h)


def relayout(schematic, library) -> None:
    """Reposition every unpinned component in place; pinned components stay."""
    comps = {c.id: c for c in schematic.components if not c.pinned}
    if not comps:
        return
    by_id = {c.id: c for c in schematic.components}
    G = nx.Graph()
    G.add_nodes_from(by_id)
    for net in schematic.nets:
        ids = []
        for p in net.pins:
            comp = _resolve(by_id, p.partition(".")[0])
            if comp is not None:
                ids.append(comp.id)
        for a, b in zip(ids, ids[1:]):
            if a != b:
                G.add_edge(a, b)
    depth: dict[str, int] = {}
    for root in sorted(G.nodes):
        if root not in depth:
            for n, d in nx.single_source_shortest_path_length(G, root).items():
                depth[n] = max(depth.get(n, 0), d)

    # layer origins from the widest body per depth, not a fixed column pitch
    maxw: dict[int, int] = {}
    for comp in comps.values():
        d = depth.get(comp.id, 0)
        maxw[d] = max(maxw.get(d, 0), _rot_size(comp, library)[0])
    layer_x: dict[int, int] = {}
    cur = MARGIN_X
    for d in sorted(maxw):
        layer_x[d] = cur
        cur += maxw[d] + LAYER_GUTTER

    def band(comp) -> str:
        roles = []
        for net in schematic.nets:
            for p in net.pins:
                c = _resolve(by_id, p.partition(".")[0])
                if c is not None and c.id == comp.id:
                    roles.append(net.role)
                    break
        if "power" in roles:
            return "power"
        if "ground" in roles:
            return "ground"
        return "signal"

    sheet_h = {s.number: s.height for s in schematic.sheets}
    placed = [
        (
            c.x - 4,
            c.y - 4,
            c.x + _rot_size(c, library)[0] + 4,
            c.y + _rot_size(c, library)[1] + 4,
        )
        for c in schematic.components
        if c.pinned
    ]
    slots: dict[tuple[str, int], int] = {}
    for comp in sorted(comps.values(), key=lambda c: (depth.get(c.id, 0), c.id)):
        b = band(comp)
        key = (b, depth.get(comp.id, 0))
        slot = slots.get(key, 0)
        slots[key] = slot + 1
        w, h = _rot_size(comp, library)
        comp.x = layer_x.get(depth.get(comp.id, 0), MARGIN_X)
        pref = BAND_Y[b] + slot * SLOT_H
        limit = sheet_h.get(comp.sheet, 700) - 20
        # nearest slot position whose body box does not collide with placed bodies
        chosen = None
        for k in range(6):
            for yy in (pref + k * SLOT_H, None if k == 0 else pref - k * SLOT_H):
                if yy is None:
                    continue
                if yy < 40 or yy + h > limit:
                    continue
                rect = (comp.x - 4, yy - 4, comp.x + w + 4, yy + h + 4)
                if not any(_overlap(rect, o) for o in placed):
                    chosen = yy
                    break
            if chosen is not None:
                break
        # ponytail: clamp fallback instead of real 2D packing; crowds need packing
        comp.y = chosen if chosen is not None else min(max(pref, 40), limit - h)
        placed.append((comp.x - 4, comp.y - 4, comp.x + w + 4, comp.y + h + 4))
