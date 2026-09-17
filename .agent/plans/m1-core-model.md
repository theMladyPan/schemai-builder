# m1-core-model

## Goal
Ship M1: pydantic schematic + diff applier + tiny IEC starter library + JSON persistence + SVG renderer (Manhattan + bbox avoid) + multi-sheet off-page connectors + CLI mock replay. No LLM.

## Done when
- `uv run pytest tests/ -q` passes
- `uv run schemai-builder replay fixtures/rc.json --out /tmp/schemai-m1` writes `sheet-1.svg` containing R, C, GND and escaped text
- invalid diffs raise with field errors (unknown id / bad pin); revert rebuilds from remaining history
- nets on 2+ sheets draw off-page connector + net label

## Assumptions (signed off)
- Greenfield; only hello `main()`, empty deps
- M1 excludes LLM, FastAPI, voice, PDF, ERC, datasheet search
- Runtime dep: pydantic only. SVG = strings. Dev: pytest, ruff
- Persist = one JSON: schematic + linear `history` of diffs. Revert = drop last N diffs, replay rest from empty
- Coords = integer grid, SVG 1:1. Missing x,y → left-to-right grid
- Symbols: R, C, L, GND, VCC, BOX, OPC
- Router: Manhattan + skip component bboxes; role styles (power vertical, gnd down, signal L→R)
- CLI: `schemai-builder replay <script.json> --out DIR` writes `sheet-{n}.svg` after each step, optional sleep

## Touch (paths + callers)
New:
- `src/schemai_builder/models.py` — Schematic, Sheet, Component, Net, Pin, LibraryEntry, SchematicDiff, Project
- `src/schemai_builder/library.py` — frozen starter library dict
- `src/schemai_builder/apply.py` — validate/apply/revert/auto-ref/autoplace
- `src/schemai_builder/persist.py` — load/save Project JSON
- `src/schemai_builder/render.py` — escape, symbols, router, SVG
- `src/schemai_builder/cli.py` — argparse replay
- `src/schemai_builder/__init__.py` — `main()` → cli
- `tests/test_apply.py`, `tests/test_render.py`, `tests/test_replay.py`
- `fixtures/rc.json`
- `pyproject.toml` — add pydantic; dev pytest, ruff

No existing callers besides `schemai_builder:main`.

## Subtasks
1. models + library + apply + persist + tests
2. renderer + router + OPC + tests
3. CLI replay + rc fixture + tests

## Verify (exact command)
```
uv run pytest tests/ -q
uv run schemai-builder replay fixtures/rc.json --out /tmp/schemai-m1 --sleep 0
```

## Risks / out of scope
- Router will still overlap in dense layouts — accepted (`# ponytail: A* if spaghetti`)
- Not a full IEC library
- No ERC, UI, PDF, LLM
- Do not invent extra abstractions, config files, or symbol DSLs
