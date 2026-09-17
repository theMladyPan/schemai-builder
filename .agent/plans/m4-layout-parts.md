# m4-layout-parts

## Goal
Schematic must look right: LLM emits graph only (no coordinates), code owns placement + rectilinear routing, static IEC core symbols plus LLM-extensible project part catalog.

## Done when
- create diffs have no x/y/rotation/mirror fields; placement derived on every apply
- `add_parts` diff op stores LLM parts in `parts.json`, reusable, drawn as generic blocks
- static symbols: FUSE, D, SW, TERM + inductor arcs; stub-tip wires; all bodies are router obstacles
- relayout bands by net role, layers by connectivity; pinned components survive
- both fixtures replay clean: no body overlaps, no wire-through-body, nothing off-canvas
- `uv run pytest tests/ -q` green

## Assumptions (signed off)
- Strip create coords entirely (boss choice); MoveComponent keeps explicit x/y/rotation/mirror, pins the component
- networkx for placement + our Manhattan router (boss choice; libavoid/graphviz rejected)
- Static core: R C L FUSE D SW GND VCC TERM BOX OPC; custom parts via add_parts (pin names + sides only, geometry derived)
- PSU with/without PE = custom part, not built-in

## Touch
models.py (PartDef/PartPin/pinned/add_parts), library.py (library_for, _part_entry, FUSE/D/SW/TERM), layout.py (new, networkx), apply.py (library param, parts validation, relayout, revert parts replay), render.py (lib threading + symbols), erc.py, persist.py (parts.json), prompt.py (library_text(project)), agent.py (instructions), app.py, cli.py, fixtures/rc.json + power_block.json, tests.

## Verify
```
uv run pytest tests/ -q
uv run schemai-builder replay fixtures/power_block.json --out /tmp/m4 --sleep 0
```

## Risks / out of scope
- Layout is heuristic (fixed bands, clamp instead of 2D packing) — crowds need real packing later
- No A* router yet; leftover overlaps accepted
- Custom parts have no SVG art (generic block)
