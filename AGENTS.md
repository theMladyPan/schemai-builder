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
- electrical scheme language will be defined for this project, translated to something like svg or other rendering format
- the LLM will always receive full schematic, prompt, textual information (short list of whys and ADRs) with few last actions, and will return a diff how to change schematic + message for user OR question if not 100% sure
- the tool for llm will apply diff to schematic, rerender it in real time, 
- versioning, in the schematic frame AND in project files, will be supported, so user can revert to previous versions - linear history
- different schematic types will have different templates/prompts. structure well

## implementation plan
remove implemented features from this list, add new ones as they are implemented, and keep the list up to date:
- draft an language suitable for LLM which will be translated to renderable format (svg, pdf, etc.) 
- create pydantic agents, openrouter, cartesia integrations for LLM and TTS
- create WEB UI
  - left panel is chat window with voice/text input, right panel is rendered scheme with realtime updates 1:4
  - console for tracking of changes, llm messages
  - possibility to attach files and pictures for LLM
- mock up of the system allowing to replay text-based conversation and rendering in real time with short sleeps (llm latency mock)
- ???

## rules
- keep this file concise and ai-slop/bloat free
- alert user for discrepancy, if requested modify as needed