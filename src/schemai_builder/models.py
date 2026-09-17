"""Pydantic schematic model tree."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Side = Literal["left", "right", "top", "bottom"]
Role = Literal["power", "ground", "signal", "bus", "feedback"]


class PinDef(BaseModel):
    """A named pin on a library symbol, offset from the symbol origin."""

    name: str
    dx: int
    dy: int
    side: Side


class LibraryEntry(BaseModel):
    """A component library entry: symbol size and pinout."""

    id: str
    prefix: str
    width: int
    height: int
    pins: list[PinDef]


class Component(BaseModel):
    """A placed component instance on a sheet."""

    id: str
    library_id: str
    ref: str
    value: str = ""
    sheet: int = 1
    x: int = 0
    y: int = 0
    rotation: Literal[0, 90, 180, 270] = 0
    mirror: bool = False


class Net(BaseModel):
    """A global net connecting component pins."""

    name: str
    role: Role = "signal"
    pins: list[str] = []  # "component_id.pin"


class Sheet(BaseModel):
    """A drawing sheet."""

    number: int
    title: str = ""
    width: int = 1000
    height: int = 700


class Schematic(BaseModel):
    """A schematic: sheets, components, and global nets."""

    sheets: list[Sheet]
    components: list[Component]
    nets: list[Net]


def empty_schematic() -> Schematic:
    """Return a new schematic with a single sheet numbered 1."""
    return Schematic(sheets=[Sheet(number=1)], components=[], nets=[])


class AddComponent(BaseModel):
    """Diff op: add a component; missing id/ref/position get auto-assigned."""

    library_id: str
    id: str | None = None
    ref: str | None = None
    value: str = ""
    sheet: int = 1
    x: int | None = None
    y: int | None = None
    rotation: Literal[0, 90, 180, 270] = 0
    mirror: bool = False


class MoveComponent(BaseModel):
    """Diff op: move/rotate/mirror one component; None fields unchanged."""

    id: str
    x: int | None = None
    y: int | None = None
    rotation: Literal[0, 90, 180, 270] | None = None
    mirror: bool | None = None


class MoveGroup(BaseModel):
    """Diff op: translate a group of components by dx/dy."""

    ids: list[str]
    dx: int = 0
    dy: int = 0


class SetSheet(BaseModel):
    """Diff op: move a component to another sheet."""

    id: str
    sheet: int


class SchematicDiff(BaseModel):
    """A structured diff to apply to a schematic; empty lists by default."""

    add_sheets: list[Sheet] = []
    add_components: list[AddComponent] = []
    remove_ids: list[str] = []
    add_nets: list[Net] = []
    remove_nets: list[str] = []
    move_components: list[MoveComponent] = []
    move_groups: list[MoveGroup] = []
    set_sheet: list[SetSheet] = []


class HistoryEntry(BaseModel):
    """One recorded turn: applied diff plus user text and LLM message."""

    diff: SchematicDiff
    user: str = ""
    message: str = ""


class ReasonReplace(BaseModel):
    """Replace reasons.md paragraph at 1-based id with new text."""

    id: int
    text: str


class ReasonsPatch(BaseModel):
    """Structured edit of reasons.md: delete, replace, append paragraphs."""

    delete: list[int] = []
    replace: list[ReasonReplace] = []
    append: list[str] = []


class Project(BaseModel):
    """A project: current schematic, reasons, and linear history."""

    schematic: Schematic
    reasons: str = ""
    history: list[HistoryEntry] = []
