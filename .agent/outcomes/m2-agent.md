# m2-agent outcome

## Behavior
- Project is a folder: `schematic.json` (pre-svg source), `reasons.md`, `history.jsonl`, `render/sheet-N.svg`.
- `save_project` / `load_project` use that folder. Old single-file JSON is gone. Stale sheet SVGs deleted on save.
- `ReasonsPatch`: 1-based paragraph ids against the original file; delete / replace / append. LLM must prune stale ADRs.
- `run_turn(project_dir, text, model=...)` — create agent only. Prompt = reasons + netlist + last 5 history + user text + optional sheet PNGs. No ERC, no SVG markup.
- Structured `AgentOutput`: `message`, optional `question` (no apply), optional `diff`, optional `reasons_patch`.
- Invalid diff: one retry with error list, then `DiffError` to caller. Question on retry also skips apply.
- Default model: `OPENROUTER_MODEL` or `openrouter:openai/gpt-4.1-mini`. Tests use FunctionModel. No ask CLI.

## Architecture
`persist.py` folder I/O, `reasons.py` paragraph patch, `prompt.py` netlist/history/prompt, `agent.py` pydantic-ai `output_type`. HistoryEntry = diff + user + message (message is the why).

## ADRs
- Review/ERC is a separate later call; open nets during create are normal.
- Netlist derived at prompt time, not stored.
- PNG via cairosvg; skip if cairo missing.
- Structured output, not tools — apply happens in Python after validation.
