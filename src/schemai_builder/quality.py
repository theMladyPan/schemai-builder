"""Geometry quality metrics for rendered sheets — the layout quality gate.

Parses an SVG sheet and measures what "EPLAN-clean" means, numerically:
no wires through bodies, lane clearance between foreign wires, few bends,
many straight net spans, deterministic output.
"""

from __future__ import annotations

import re
from itertools import pairwise

SEG_RE = re.compile(r'<polyline points="([^"]+)"')


def sheet_segments(svg: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    segs = []
    for m in SEG_RE.finditer(svg):
        pts = [tuple(map(int, q.split(","))) for q in m.group(1).split()]
        segs.extend(pairwise(pts))
    return segs


def body_rects(svg: str) -> list[tuple[int, int, int, int]]:
    """Component body rectangles (everything except the white background)."""
    out = []
    for x, y, w, h in re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', svg
    ):
        if int(w) > 500:  # background
            continue
        out.append((int(x), int(y), int(x) + int(w), int(y) + int(h)))
    return out


def _seg_hits_rect(x1, y1, x2, y2, r) -> bool:
    if y1 == y2:
        return r[1] < y1 < r[3] and min(x1, x2) < r[2] and max(x1, x2) > r[0]
    if x1 == x2:
        return r[0] < x1 < r[2] and min(y1, y2) < r[3] and max(y1, y2) > r[1]
    return False


def body_intersections(svg: str, pad: int = 6) -> int:
    """Wire segments passing through inflated component bodies."""
    rects = [(a - pad, b - pad, c + pad, d + pad) for a, b, c, d in body_rects(svg)]
    return sum(
        1
        for (a, b) in sheet_segments(svg)
        for r in rects
        if _seg_hits_rect(*a, *b, r)
    )


def _orient(a, b) -> tuple[str, int, int, int] | None:
    if a[1] == b[1]:
        return ("h", a[1], min(a[0], b[0]), max(a[0], b[0]))
    if a[0] == b[0]:
        return ("v", a[0], min(a[1], b[1]), max(a[1], b[1]))
    return None


def clearance_violations(svg: str, min_gap: int = 20) -> list[tuple]:
    """Foreign wire pairs running parallel closer than min_gap with overlap."""
    segs = [o for o in (_orient(a, b) for a, b in sheet_segments(svg)) if o]
    bad = []
    for i, (o1, c1, l1, h1) in enumerate(segs):
        for o2, c2, l2, h2 in segs[:i]:
            if o1 != o2:
                continue
            if abs(c1 - c2) < min_gap and max(l1, l2) < min(h1, h2):
                bad.append(((o1, c1, l1, h1), (o2, c2, l2, h2)))
    return bad


def crossings(svg: str) -> int:
    """Perpendicular intersections between wires (should be rare)."""
    segs = [o for o in (_orient(a, b) for a, b in sheet_segments(svg)) if o]
    n = 0
    for i, (o1, c1, l1, h1) in enumerate(segs):
        for o2, c2, l2, h2 in segs[:i]:
            if o1 == o2:
                continue
            if l1 <= c2 <= h1 and l2 <= c1 <= h2:
                n += 1
    return n


def bends(svg: str) -> int:
    """Total corner count across all wire paths."""
    total = 0
    for m in SEG_RE.finditer(svg):
        pts = [tuple(map(int, q.split(","))) for q in m.group(1).split()]
        total += sum(
            1
            for a, b in pairwise(pairwise(pts))
            if (a[0][1] == a[1][1]) != (b[0][1] == b[1][1])
        )
    return total
