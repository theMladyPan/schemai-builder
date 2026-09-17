"""Tiny built-in component library."""

from __future__ import annotations

from .models import LibraryEntry, PinDef

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
            id="BOX",
            prefix="U",
            width=120,
            height=160,
            pins=[
                PinDef(name=str(n), dx=0, dy=n * 40, side="left") for n in range(1, 5)
            ]
            + [
                PinDef(name=str(n), dx=120, dy=(n - 5) * 40, side="right")
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
