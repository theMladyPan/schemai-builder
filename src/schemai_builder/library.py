"""Static IEC core library plus LLM-extensible project part catalog."""

from __future__ import annotations

from .models import LibraryEntry, PartDef, PinDef

_R_C_L_PINS = [
    PinDef(name="A", dx=0, dy=0, side="left"),
    PinDef(name="B", dx=80, dy=0, side="right"),
]

LIBRARY: dict[str, LibraryEntry] = {
    entry.id: entry
    for entry in [
        LibraryEntry(id="R", prefix="R", width=80, height=20, pins=_R_C_L_PINS),
        LibraryEntry(id="C", prefix="C", width=80, height=20, pins=_R_C_L_PINS),
        LibraryEntry(id="L", prefix="L", width=80, height=20, pins=_R_C_L_PINS),
        LibraryEntry(
            id="FUSE",
            prefix="F",
            width=80,
            height=20,
            pins=[
                PinDef(name="A", dx=0, dy=10, side="left"),
                PinDef(name="B", dx=80, dy=10, side="right"),
            ],
        ),
        LibraryEntry(
            id="D",
            prefix="D",
            width=80,
            height=20,
            pins=[
                PinDef(name="A", dx=0, dy=10, side="left"),
                PinDef(name="K", dx=80, dy=10, side="right"),
            ],
        ),
        LibraryEntry(
            id="SW",
            prefix="S",
            width=80,
            height=20,
            pins=[
                PinDef(name="1", dx=0, dy=10, side="left"),
                PinDef(name="2", dx=80, dy=10, side="right"),
            ],
        ),
        LibraryEntry(
            id="GND",
            prefix="GND",
            width=40,
            height=40,
            pins=[PinDef(name="A", dx=0, dy=0, side="top")],
        ),
        LibraryEntry(
            id="VCC",
            prefix="VCC",
            width=40,
            height=40,
            pins=[PinDef(name="A", dx=0, dy=0, side="bottom")],
        ),
        LibraryEntry(
            id="TERM",
            prefix="X",
            width=80,
            height=40,
            pins=[
                PinDef(name="1", dx=0, dy=20, side="left"),
                PinDef(name="2", dx=80, dy=20, side="right"),
            ],
        ),
        LibraryEntry(
            id="BOX",
            prefix="U",
            width=120,
            height=160,
            pins=[
                PinDef(name=str(n), dx=0, dy=20 + (n - 1) * 40, side="left")
                for n in range(1, 5)
            ]
            + [
                PinDef(name=str(n), dx=120, dy=20 + (n - 5) * 40, side="right")
                for n in range(5, 9)
            ],
        ),
        LibraryEntry(
            id="OPC",
            prefix="OPC",
            width=40,
            height=20,
            pins=[PinDef(name="A", dx=0, dy=0, side="left")],
        ),
    ]
}

#: static drawing kinds handled by dedicated render branches; anything else draws generic
SYMBOL_KINDS = {"R", "C", "L", "FUSE", "D", "SW", "GND", "VCC", "TERM", "OPC", "BOX"}


def _part_entry(part: PartDef) -> LibraryEntry:
    """Convert a project PartDef into a drawable LibraryEntry; sides -> offsets."""
    left = [p for p in part.pins if p.side == "left"]
    right = [p for p in part.pins if p.side == "right"]
    top = [p for p in part.pins if p.side == "top"]
    bottom = [p for p in part.pins if p.side == "bottom"]
    width = part.width or 120
    height = part.height or max(len(left), len(right), 1) * 40 + 40
    pins = [
        PinDef(name=p.name, dx=0, dy=20 + i * 40, side="left")
        for i, p in enumerate(left)
    ]
    pins += [
        PinDef(name=p.name, dx=width, dy=20 + i * 40, side="right")
        for i, p in enumerate(right)
    ]
    pins += [
        PinDef(name=p.name, dx=width // 2, dy=0, side="top") for i, p in enumerate(top)
    ]
    pins += [
        PinDef(name=p.name, dx=width // 2, dy=height, side="bottom")
        for i, p in enumerate(bottom)
    ]
    return LibraryEntry(
        id=part.id,
        prefix=part.prefix or part.id.upper(),
        width=width,
        height=height,
        pins=pins,
    )


def library_for(project) -> dict[str, LibraryEntry]:
    """Static LIBRARY merged with the project's custom parts."""
    merged = dict(LIBRARY)
    for part in project.parts:
        merged[part.id] = _part_entry(part)
    return merged
