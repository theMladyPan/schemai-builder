# m4-layout-parts outcome

## Behavior
- Create-agent diffs are coordinate-free: `AddComponent(library_id, id?, ref?, value, sheet)`. Placement is derived on every apply and never stored in diffs. User `move_components`/`move_groups` set explicit coords and pin the component (survives relayout).
- LLM can create parts: `add_parts` with `PartDef {id, width?, height?, prefix?, description?, pins: [{name, side}]}`. Parts live in `project/parts.json`, validate against built-ins (no conflicts/dupes/dots/empty), become immediately usable as `library_id`, and are listed in the prompt catalog with description.
- Static library grew IEC pieces: FUSE(A,B), D(A,K), SW(1,2), TERM(1,2); inductor draws as three arcs; fuse rect+through-line; diode triangle+bar; switch contacts+lever; terminal circles. BOX/custom parts draw as generic rect blocks.
- Router: wire endpoints at stub tips outside bodies, every component bbox is an obstacle (no self-exclusion), z-path ±2·GRID sweep then U-path above/below obstacles then leftover fallback. Labels nudge out of bodies.
- relayout: networkx graph over comps (edges from shared nets, ref-aware), BFS depth from sorted roots → x layers (200px), y bands by dominant net role (power 100 / signal 300 / ground 560), slot spacing 180, y clamped to sheet height.

## Architecture
`layout.py` (new) = derived placement. `library_for(project)` merges static LIBRARY + parts; threaded through apply/erc/render/prompt/persist/cli. `Component.pinned` persisted in schematic.json. parts.json joins the project folder (schematic.json, reasons.md, history.jsonl, render/).

## ADRs
- ADR: placement is derived, not stored
  Status: accepted
  Context: LLM-emitted coords produced garbage (wires through bodies, invented rotations)
  Decision: strip coords from create diffs; relayout every apply; explicit user moves pin components
  Rejected: optional coord hints — models keep sending junk
  Consequence: layout heuristics own the look; move ops must set pinned
- ADR: project-extensible parts instead of bigger built-in library
  Status: accepted
  Context: PSU/GPIO/ICs vary per project (with/without PE etc.)
  Decision: static IEC core + PartDef parts.json; LLM creates parts, never pin dx/dy
  Rejected: large static catalog — cannot cover every vendor module
  Consequence: custom parts draw as generic blocks until a symbol-art milestone

## Invariants
- apply_diff/apply_and_record raise DiffError without partial application (incl. parts validation)
- revert replays parts from history; unknown part ids at load → ValueError
- prompt catalog lists built-ins + project parts with pins

## Checks
- `uv run pytest tests/ -q` → 81 passed
- replay rc.json + power_block.json → no body overlaps, 0 wire-crossings, nothing off-canvas
- gpt-5.6-sol render review applied: label occupancy engine, world-side stubs, route-based label spots, width-aware layers, nearest-free-slot placement → my-scheme4 re-render: 35 labels / 0 overlaps / 0 crossings
- gpt-5.6-sol round 3 applied: track registry (lane clearance, least-damage fallback w/ half-grid offsets), EPLAN frame + grid refs + title block, off-page flags with cross-ref text (sheet-zone), labels above longest span, pin names in bodies, thin lines/no text stroke, LAYER_GUTTER 120, x-clamp in frame → my-scheme4: 0 exact wire overlaps (was 12), 0 label overlaps, PNG eyeballed — boss target: Metrotech-style pages
- gpt-5.6-sol round 2 applied: two-pass routing (labels see all wires), GRID lead-outs with 10px body clearance, ≥3-aligned-body column envelopes, spiral label fallback → my-scheme4: 35 labels / 0 label-overlaps / 0 labels-on-wires; PNG eyeballed clean
- `/state` returns last 20 history entries; UI paints chat log + cache-busted SVG on load (resume after restart)

## Residual
- ponytail: fixed bands + y clamp, not real 2D packing — crowds need packing
- ponytail: no A* router; leftover overlaps accepted
- custom parts have no SVG art (generic block)
