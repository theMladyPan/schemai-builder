"""Deterministic advisory ERC checks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .library import LIBRARY
from .models import Schematic

_KIND_ORDER = ("short", "unconnected_pin", "single_ended_net", "unused_component")


class ErcIssue(BaseModel):
    """One advisory ERC finding."""

    kind: Literal["unconnected_pin", "single_ended_net", "short", "unused_component"]
    detail: str


def run_erc(schematic: Schematic, lib: dict | None = None) -> list[ErcIssue]:
    """Return advisory ERC issues, ordered shorts, unconnected, single-ended, unused."""
    lib = lib or LIBRARY
    pin_nets: dict[str, list[str]] = {}
    for net in schematic.nets:
        for pin in net.pins:
            pin_nets.setdefault(pin, []).append(net.name)
    connected = set(pin_nets)

    issues: dict[str, list[ErcIssue]] = {kind: [] for kind in _KIND_ORDER}
    for pin, nets in pin_nets.items():
        if len(nets) > 1:
            issues["short"].append(ErcIssue(kind="short", detail=pin))
    for comp in schematic.components:
        entry = lib.get(comp.library_id)
        if entry is None:
            continue
        used = False
        for p in entry.pins:
            pin = f"{comp.id}.{p.name}"
            if pin in connected:
                used = True
            else:
                issues["unconnected_pin"].append(
                    ErcIssue(kind="unconnected_pin", detail=pin)
                )
        if not used:
            issues["unused_component"].append(
                ErcIssue(kind="unused_component", detail=comp.id)
            )
    for net in schematic.nets:
        if len(net.pins) <= 1:
            issues["single_ended_net"].append(
                ErcIssue(kind="single_ended_net", detail=net.name)
            )
    return [
        issue
        for kind in _KIND_ORDER
        for issue in sorted(issues[kind], key=lambda i: i.detail)
    ]
