# m2-agent

## Goal
Create-agent Python API + project folder persist + reasons patch. No UI, no ERC in create, no review agent, no ask CLI.

## Done when
- `uv run pytest tests/ -q` passes
- `save_project` / `load_project` use a directory: `schematic.json`, `reasons.md`, `history.jsonl`, `render/sheet-N.svg`
- `run_turn(project_dir, text)` with pydantic-ai TestModel applies a diff, optional ReasonsPatch, writes folder
- invalid diff: one retry then error to caller
- create prompt contains reasons + netlist + last 5 history + PNG bytes, not ERC, not SVG markup

## Assumptions (signed off)
- Review agent is a separate later call (M3). Create prompt has no ERC (open nets during create are normal).
- Python API only: `run_turn(project_dir, text)`. Replay CLI stays as-is.
- Datasheet web search later.
- PNG via cairosvg.
- `schematic.json` is the stored pre-svg. Netlist derived at prompt time.
- `ReasonsPatch`: 1-based paragraph ids; delete / replace / append. Not full rewrite.

## Touch
- `src/schemai_builder/models.py` — HistoryEntry, ReasonsPatch, Project.reasons
- `src/schemai_builder/apply.py` — apply_and_record user/message; revert uses entry.diff
- `src/schemai_builder/persist.py` — folder I/O
- `src/schemai_builder/reasons.py` — split/apply/number paragraphs
- `src/schemai_builder/prompt.py` — netlist + prompt pack
- `src/schemai_builder/agent.py` — run_turn
- tests: persist, reasons, prompt, agent (TestModel)
- `pyproject.toml` — pydantic-ai, cairosvg, openai/httpx as pydantic-ai needs
- do not add ask CLI

## Subtasks
1. folder persist + HistoryEntry + ReasonsPatch + update M1 tests
2. prompt builder + svg-to-png
3. run_turn + retry + TestModel tests

## Verify
```
uv run pytest tests/ -q
```

## Risks / out of scope
- No FastAPI, ERC, review agent, datasheet search, voice
- OpenRouter live calls not required for tests
