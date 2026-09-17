# m3-ui-checks outcome

## Behavior
- `schemai-builder serve --project DIR` — chat 1:4 SVG, console, file attach, Review, PDF.
- ERC advisory: short, unconnected_pin, single_ended_net, unused_component. Console + review prompt, never create-agent prompt.
- `review_turn` is read-only. Review is a button, not auto.
- `GET /sheet/{n}.svg` and `/sheet/{n}.pdf`. PDF None/404 if cairo missing.
- Invalid diff after one retry returns 200 to the UI (`applied: false`, error text), not 500.
- Chat/console use textContent; SVG via `<img src>`.

## Architecture
`erc.py`, `pdf.py`, `app.py`, `static/index.html`. Create `run_turn` unchanged besides `files=`. In-process WebSocket set.

## ADRs
- Vanilla fetch, not htmx (unused CDN was supply-chain noise).
- Schematic-type-specific review rules not modeled yet.
- Uploads not stored on disk.
- Concurrent chats can clobber (`# ponytail` ceiling: single-user).
