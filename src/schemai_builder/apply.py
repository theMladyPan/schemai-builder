"""Apply and revert schematic diffs."""

from __future__ import annotations

from copy import deepcopy

from .library import LIBRARY
from .models import (
    AddComponent,
    Component,
    Project,
    Schematic,
    SchematicDiff,
    empty_schematic,
)

GRID = 80


class DiffError(ValueError):
    """Raised when a diff cannot be applied; .errors lists all problems."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _next_ref(schematic: Schematic, prefix: str) -> str:
    taken = {c.ref for c in schematic.components}
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def _autoplaced(schematic: Schematic) -> tuple[int, int]:
    occupied = {(c.x, c.y) for c in schematic.components}
    k = 0
    while (100 + k * GRID, 100) in occupied:
        k += 1
    return 100 + k * GRID, 100


def _add_component(schematic: Schematic, op: AddComponent, errors: list[str]) -> None:
    entry = LIBRARY.get(op.library_id)
    if entry is None:
        errors.append(f"unknown library_id {op.library_id!r}")
        return
    if op.sheet not in {s.number for s in schematic.sheets}:
        errors.append(f"sheet {op.sheet} does not exist")
        return
    comp_id = op.id
    if comp_id is None:
        taken = {c.id for c in schematic.components}
        n = 1
        while f"c{n}" in taken:
            n += 1
        comp_id = f"c{n}"
    elif comp_id in {c.id for c in schematic.components}:
        errors.append(f"duplicate component id {comp_id!r}")
        return
    ref = op.ref
    if ref is None:
        ref = _next_ref(schematic, entry.prefix)
    elif ref in {c.ref for c in schematic.components}:
        errors.append(f"duplicate ref {ref!r}")
        return
    x, y = op.x, op.y
    if x is None or y is None:
        ax, ay = _autoplaced(schematic)
        x = x if x is not None else ax
        y = y if y is not None else ay
    schematic.components.append(
        Component(
            id=comp_id,
            library_id=op.library_id,
            ref=ref,
            value=op.value,
            sheet=op.sheet,
            x=x,
            y=y,
            rotation=op.rotation,
            mirror=op.mirror,
        )
    )


def apply_diff(schematic: Schematic, diff: SchematicDiff) -> Schematic:
    """Apply a diff to a copy of the schematic; raises DiffError without partial application."""
    out = deepcopy(schematic)
    errors: list[str] = []
    by_id = {c.id: c for c in out.components}

    for sheet in diff.add_sheets:
        if sheet.number in {s.number for s in out.sheets}:
            errors.append(f"duplicate sheet number {sheet.number}")
        else:
            out.sheets.append(sheet)

    for op in diff.add_components:
        _add_component(out, op, errors)
        by_id = {c.id: c for c in out.components}

    for comp_id in diff.remove_ids:
        if comp_id not in by_id:
            errors.append(f"unknown component id {comp_id!r}")
        else:
            del out.components[out.components.index(by_id[comp_id])]
            del by_id[comp_id]
            for net in out.nets:
                net.pins = [p for p in net.pins if not p.startswith(f"{comp_id}.")]

    net_names = {n.name for n in out.nets}
    for name in diff.remove_nets:
        if name not in net_names:
            errors.append(f"unknown net {name!r}")
        else:
            out.nets = [n for n in out.nets if n.name != name]
            net_names.discard(name)

    for net in diff.add_nets:
        if net.name in net_names:
            errors.append(f"duplicate net name {net.name!r}")
            continue
        before = len(errors)
        for pin in net.pins:
            comp_id, _, pin_name = pin.partition(".")
            comp = by_id.get(comp_id)
            entry = LIBRARY.get(comp.library_id) if comp else None
            if (
                comp is None
                or entry is None
                or pin_name not in {p.name for p in entry.pins}
            ):
                errors.append(f"net {net.name!r}: bad pin {pin!r}")
        if len(errors) == before:
            out.nets.append(net)
            net_names.add(net.name)

    for op in diff.move_components:
        comp = by_id.get(op.id)
        if comp is None:
            errors.append(f"unknown component id {op.id!r}")
            continue
        if op.x is not None:
            comp.x = op.x
        if op.y is not None:
            comp.y = op.y
        if op.rotation is not None:
            comp.rotation = op.rotation
        if op.mirror is not None:
            comp.mirror = op.mirror

    for op in diff.move_groups:
        for comp_id in op.ids:
            comp = by_id.get(comp_id)
            if comp is None:
                errors.append(f"unknown component id {comp_id!r}")
            else:
                comp.x += op.dx
                comp.y += op.dy

    for op in diff.set_sheet:
        comp = by_id.get(op.id)
        if comp is None:
            errors.append(f"unknown component id {op.id!r}")
        elif op.sheet not in {s.number for s in out.sheets}:
            errors.append(f"sheet {op.sheet} does not exist")
        else:
            comp.sheet = op.sheet

    if errors:
        raise DiffError(errors)
    return out


def apply_and_record(project: Project, diff: SchematicDiff) -> Project:
    """Apply a diff and append it to the project history."""
    project.schematic = apply_diff(project.schematic, diff)
    project.history.append(diff)
    return project


def revert(project: Project, n: int = 1) -> Project:
    """Drop the last n diffs and replay the remaining history from empty."""
    if n < 0:
        raise ValueError(f"cannot revert {n} diffs")
    project.history = project.history[:-n] if n else project.history
    schematic = empty_schematic()
    for diff in project.history:
        schematic = apply_diff(schematic, diff)
    project.schematic = schematic
    return project
