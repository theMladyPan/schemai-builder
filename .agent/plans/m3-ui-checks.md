# m3-ui-checks

## Goal
FastAPI UI (chat 1:4 SVG, console, attach files) + advisory ERC + separate review agent + PDF. No voice, no datasheet search.

## Done when
- `uv run pytest tests/ -q` passes
- `schemai-builder serve --project DIR` serves UI
- chat POST runs create `run_turn` (no ERC in that prompt), WebSocket pushes SVG + message + ERC
- Review button runs `review_turn` (ERC + netlist + PNG + reasons, advisory, no auto-apply)
- attach images/text files to create turn
- `GET /sheet/{n}.pdf` via cairosvg (None/404 if cairo missing)

## Locked
- Review is explicit, never auto after create (open nets are normal).
- ERC kinds: unconnected pin, single-ended net (0–1 pin), short (same pin on two nets), unused component (no pins on any net). Advisory lists.
- No jinja: one `src/schemai_builder/static/index.html`.
- No auth. One project dir per process (`--project`).
- Uploads live only in the request; not written into the project folder.
- XSS: chat/console via textContent; SVG via `<img src="/sheet/N.svg">` (already escaped at render).

## Subtasks
1. `erc.py` + tests
2. `review_turn` + `run_turn(..., files=)` + PDF helper + tests
3. FastAPI app + `serve` CLI + TestClient tests

## Verify
```
uv run pytest tests/ -q
```

## Out of scope
Voice, datasheets, project picker, React, auto-review.
