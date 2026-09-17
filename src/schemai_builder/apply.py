"""Apply and revert schematic diffs."""

from __future__ import annotations

from copy import deepcopy

from .layout import relayout
from .library import LIBRARY, _part_entry, library_for
from .models import (
    AddComponent,
    Component,
    HistoryEntry,
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


def _add_component(
    schematic: Schematic, op: AddComponent, errors: list[str], lib: dict
) -> None:
    """Append a component; placement is derived by relayout, never stored in the op."""
    entry = lib.get(op.library_id)
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
    schematic.components.append(
        Component(
            id=comp_id,
            library_id=op.library_id,
            ref=ref,
            value=op.value,
            sheet=op.sheet,
        )
    )


def apply_diff(
    schematic: Schematic, diff: SchematicDiff, library: dict | None = None
) -> Schematic:
    """Apply a diff to a copy of the schematic; raises DiffError without partial application."""
    out = deepcopy(schematic)
    lib = library or LIBRARY
    errors: list[str] = []
    by_id = {c.id: c for c in out.components}
    by_ref = {c.ref.lower(): c for c in out.components}

    for sheet in diff.add_sheets:
        if sheet.number in {s.number for s in out.sheets}:
            errors.append(f"duplicate sheet number {sheet.number}")
        else:
            out.sheets.append(sheet)

    for op in diff.add_components:
        _add_component(out, op, errors, lib)
        by_id = {c.id: c for c in out.components}
        by_ref = {c.ref.lower(): c for c in out.components}

    for comp_id in diff.remove_ids:
        if comp_id not in by_id:
            errors.append(f"unknown component id {comp_id!r}")
        else:
            comp = by_id[comp_id]
            del out.components[out.components.index(comp)]
            del by_id[comp_id]
            del by_ref[comp.ref.lower()]
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
            comp = by_id.get(comp_id) or by_ref.get(comp_id.lower())
            entry = lib.get(comp.library_id) if comp else None
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
        comp.pinned = True  # explicit user placement survives relayout

    for op in diff.move_groups:
        for comp_id in op.ids:
            comp = by_id.get(comp_id)
            if comp is None:
                errors.append(f"unknown component id {comp_id!r}")
            else:
                comp.x += op.dx
                comp.y += op.dy
                comp.pinned = True

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
    relayout(out, lib)
    return out


def _validate_parts(project, diff: SchematicDiff, errors: list[str]) -> None:
    """Validate add_parts against built-ins and existing project parts."""
    for part in diff.add_parts:
        if part.id in LIBRARY:
            errors.append(f"part id {part.id!r} conflicts with built-in library")
        elif part.id in {p.id for p in project.parts}:
            errors.append(f"duplicate part id {part.id!r}")
        elif "." in part.id:
            errors.append(f"invalid part id {part.id!r}")
        elif not part.pins:
            errors.append(f"part {part.id!r} has no pins")
        elif len({p.name for p in part.pins}) != len(part.pins):
            errors.append(f"part {part.id!r} has duplicate pin names")


def apply_and_record(
    project: Project, diff: SchematicDiff, user: str = "", message: str = ""
) -> Project:
    """Apply a diff (parts first), relayout, and append a HistoryEntry."""
    errors: list[str] = []
    _validate_parts(project, diff, errors)
    if errors:
        raise DiffError(errors)
    library = library_for(project)
    library.update({p.id: _part_entry(p) for p in diff.add_parts})
    project.schematic = apply_diff(project.schematic, diff, library=library)
    project.parts += diff.add_parts
    project.history.append(HistoryEntry(diff=diff, user=user, message=message))
    return project


def revert(project: Project, n: int = 1) -> Project:
    """Drop the last n diffs and replay the remaining history from empty."""
    # reasons are not rolled back in M2
    if n < 0:
        raise ValueError(f"cannot revert {n} diffs")
    project.history = project.history[:-n] if n else project.history
    schematic = empty_schematic()
    project.parts = []
    for entry in project.history:
        errors: list[str] = []
        _validate_parts(project, entry.diff, errors)
        if errors:
            raise DiffError(errors)
        project.parts += entry.diff.add_parts
        schematic = apply_diff(schematic, entry.diff, library=library_for(project))
    project.schematic = schematic
    return project
