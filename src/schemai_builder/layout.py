"""Derived layout: place unpinned components by graph structure and net roles."""

from __future__ import annotations

import networkx as nx

from .models import Schematic

MARGIN_X = 60
LAYER_W = 200
SLOT_H = 180  # tallest body is 160; leave a gap
BAND_Y = {"power": 100, "signal": 300, "ground": 560}
# ponytail: fixed bands for the default 1000x700 sheet; per-sheet bands if crowds


def _resolve(comps: dict[str, object], comp_id: str):
    """Find a component by id or case-insensitive ref, same rule as apply.py."""
    if comp_id in comps:
        return comps[comp_id]
    low = comp_id.lower()
    return next((c for c in comps.values() if c.ref.lower() == low), None)


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

    slots: dict[tuple[str, int], int] = {}
    sheet_h = {s.number: s.height for s in schematic.sheets}
    for comp in sorted(comps.values(), key=lambda c: (depth.get(c.id, 0), c.id)):
        b = band(comp)
        key = (b, depth.get(comp.id, 0))
        slot = slots.get(key, 0)
        slots[key] = slot + 1
        comp.x = MARGIN_X + depth.get(comp.id, 0) * LAYER_W
        # ponytail: clamp instead of reflowing bands; crowds need real 2D packing
        comp.y = min(BAND_Y[b] + slot * SLOT_H, sheet_h.get(comp.sheet, 700) - 60)
