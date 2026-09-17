# m1-core-model outcome

## Behavior
- Build a schematic with `apply_diff` / `apply_and_record`; `revert(n)` rebuilds from remaining history.
- Invalid diffs raise `DiffError` (unknown id/pin/library, duplicate ref/sheet). Negative `n` on revert raises `ValueError`.
- Save/load one JSON project (`schematic` + `history`). Load rejects unknown `library_id`.
- `render_sheet` / `render_all` emit SVG (escaped text, Manhattan routes with bbox avoid, off-page connectors for multi-sheet nets, labels on single-pin nets).
- CLI: `schemai-builder replay SCRIPT --out DIR [--sleep N]` applies scripted diffs and writes `sheet-{n}.svg`.
- Demo: `uv run schemai-builder replay fixtures/rc.json --out /tmp/schemai-m1 --sleep 0`

## Architecture
Modules: `models`, `library`, `apply`, `persist`, `render`, `cli`.
Library ids: R, C, L, GND, VCC, BOX, OPC.
Diff ops: `add_sheets`, `add_components`, `remove_ids`, `remove_nets`, `add_nets`, `move_components`, `move_groups`, `set_sheet`.
Sheet changes only via `set_sheet` / `add_sheets`. Removing a component prunes its net pins.

## ADRs
- Revert = drop last N diffs and replay from empty schematic (no inverse ops).
- OPC are render-only (not extra components).
- Router is Manhattan + bbox offset (`# ponytail: A* if spaghetti`).
- No LLM/UI/PDF/ERC in this slice.
