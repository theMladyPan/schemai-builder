this project's purpose is to provide speech and LLM assisted creating and modifying electrical schemes and rendering them in real time.

## desired functionality
keep them in mind when designing the system:
- The system should allow users to create electrical schemes using natural language commands.
- agent should browse web for datasheets when components are chosen, make sure to steer user if they are choosing wrong design - forget about something
- input is text with speech (transcribed to text, text for components, files, models, pictures, etc.) and output is a rendered electrical scheme along message for user
- web UI with realtime adjustments
- support multiple sheets
- support auto-routing and auto-labeling of connections
- europe (slovak) standard for electrical schemes should be followed
- support export to PDF
- support for low power (electronics) and high power (electrical) schemes standards

## core concepts 
- schematic is a pydantic model tree (sheets, components, nets). LLM returns a structured diff via pydantic-ai tool call (`SchematicDiff`: add/remove components, add/remove nets, layout ops) + message for user — no free-form text format, no custom parser
- components in a diff reference a component library entry (symbol, pinout, package) — LLM never invents pinouts. missing part -> web datasheet search -> proposed library entry needs user confirm. ref designators auto-assigned, unique, renumbered on demand
- invalid diff (unknown id, bad pin) is rejected; errors go back to LLM for one retry, then to the user. renderer escapes all user/LLM text — SVG reaches browser raw
- the LLM always receives full schematic state, whys/ADR notes, few last actions; returns a diff + message OR a question if not 100% sure. applied diff re-renders in real time
- nets are global across sheets: net label = identity everywhere, off-page connector symbols (IEC 60617) auto-drawn at sheet edge
- layout control is coarse: LLM diff may contain `move_component(x, y)`, `move_group(region)`, `set_sheet`, component `rotation`/`mirror` — renderer and auto-router draw everything. LLM never emits SVG, wire waypoints or route geometry (too many tokens, no validation possible)
- LLM sets semantics, router sets geometry: nets carry roles (`power|ground|signal|bus|feedback`), router translates roles into route styles via per-schematic-type conventions (signals left→right, power vertical, ground to bottom bus, 3-phase top-down for high power). If router output proves bad later, add optional pin-level side hints — not now
- LLM prompt about schematic = compact netlist text (authoritative channel) + layout summary + ERC results + rendered PNG attached for multimodal models (layout quality review, reading user images). LLM never gets schematic *only* as an image
- if layout instructions unclear (which sheet/net(group)/component), LLM concisely asks before changing anything
- electrical/physical rules: two layers. deterministic ERC in code (single-ended nets, unconnected pins, shorts...) — advisory only, results go to LLM prompt + console, LLM explains and prompts user for fix. LLM bystander review (electrical + physical rules per schematic type) is advisory, never the only check
- rendering: custom SVG generator — IEC 60617 (EN) symbol library, auto-layout, auto-router -> `<svg>` markup for web UI, PDF export via cairosvg
- web stack: FastAPI backend + htmx/vanilla JS single page; WebSocket pushes schematic SVG updates; everything Python, no separate frontend codebase
- voice deferred — no STT/TTS in first versions. when added: STT placeholder is google/chirp-3 via openrouter, TTS via cartesia
- versioning, in the schematic frame AND in project files, will be supported, so user can revert to previous versions - linear history
- different schematic types (low power electronics / high power electrical) will have different templates/prompts and symbol subsets. structure well

## implementation plan
ordered by milestones (remove implemented features, add new ones, keep up to date):

M1 — done (dev): pydantic schematic, library, apply/revert, JSON persist, SVG renderer, CLI replay.

M2 — agent:
- pydantic-ai agent + openrouter LLM integration (multimodal model for PNG input)
- LLM prompt builder: netlist text + layout summary + ERC results + rendered PNG
- invalid diff retry policy

M3 — UI + checks:
- FastAPI web UI (htmx/vanilla, WebSocket push)
  - left panel is chat window with text input, right panel is rendered scheme with realtime updates 1:4
  - console for tracking of changes, llm messages
  - possibility to attach files and pictures for LLM
- ERC checks: single-ended net detection, unconnected pins, shorts (advisory)
- LLM bystander review pass (electrical + physical rules per schematic type)
- PDF export (cairosvg)

later:
- voice — STT (google/chirp-3 via openrouter) + cartesia TTS
- web search for datasheets when components are chosen

## rules
- keep this file concise and ai-slop/bloat free
- alert user for discrepancy, if requested modify as needed