"""FastAPI web UI: chat + real-time sheet rendering over WebSocket."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, WebSocket
from fastapi.responses import FileResponse, HTMLResponse
import logfire
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import Model
from starlette.concurrency import run_in_threadpool

from .agent import run_turn, review_turn
from .apply import DiffError
from .erc import run_erc
from .models import Project, empty_schematic
from .pdf import svg_to_pdf
from .persist import load_project, save_project

STATIC_DIR = Path(__file__).parent / "static"


def create_app(project_dir: Path, *, model: Model | None = None) -> FastAPI:
    """Create the web app for a project folder, initializing it if empty."""
    if not (project_dir / "schematic.json").exists():
        save_project(Project(schematic=empty_schematic()), project_dir)
    app = FastAPI()
    websockets: set[WebSocket] = set()  # ponytail: in-process WS set

    async def broadcast(payload: dict[str, Any]) -> None:
        for ws in list(websockets):
            try:
                await ws.send_json({"type": "update", **payload})
            except Exception:
                websockets.discard(ws)

    def state() -> dict[str, Any]:
        """Current sheet numbers, active sheet, and advisory ERC issues."""
        schematic = load_project(project_dir).schematic
        sheets = [s.number for s in schematic.sheets]
        return {
            "sheets": sheets,
            "sheet": sheets[0] if sheets else 1,
            "erc": [i.model_dump() for i in run_erc(schematic)],
        }

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse((STATIC_DIR / "index.html").read_text())

    @app.get("/state")
    def get_state() -> dict[str, Any]:
        return state()

    @app.get("/sheet/{n}.svg")
    def sheet_svg(n: int) -> FileResponse:
        path = project_dir / "render" / f"sheet-{n}.svg"
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/svg+xml")

    @app.get("/sheet/{n}.pdf")
    def sheet_pdf(n: int) -> Response:
        path = project_dir / "render" / f"sheet-{n}.svg"
        if not path.is_file():
            raise HTTPException(404)
        pdf = svg_to_pdf(path.read_text())
        if pdf is None:
            raise HTTPException(404)
        return Response(pdf, media_type="application/pdf")

    @app.post("/chat")
    async def chat(
        text: str = Form(...),
        files: list[UploadFile] = File(default=[]),
    ) -> dict[str, Any]:
        uploads = [
            (f.filename or "file", await f.read(), f.content_type or "") for f in files
        ]
        try:
            result = await run_in_threadpool(
                run_turn, project_dir, text, model=model, files=uploads
            )
        except (DiffError, UnexpectedModelBehavior) as e:
            if isinstance(e, UnexpectedModelBehavior):
                msg = "model output invalid after retries, try again"
            else:
                msg = "diff rejected: " + "; ".join(e.errors)
            payload = state() | {
                "message": msg,
                "question": None,
                "applied": False,
            }
        else:
            payload = state() | {
                "message": result.message,
                "question": result.question,
                "applied": result.applied,
            }
        await broadcast(payload)
        return payload

    @app.post("/review")
    async def review() -> dict[str, Any]:
        result = await run_in_threadpool(review_turn, project_dir, model=model)
        payload = state() | {"message": result.message}
        await broadcast(payload)  # issues already in state().erc, no duplicate
        return payload | {"issues": [i.model_dump() for i in result.issues]}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        websockets.add(websocket)
        try:
            while True:
                await websocket.receive_text()  # ignore client pings; disconnect raises
        except Exception:
            websockets.discard(websocket)

    logfire.instrument_fastapi(app)  # request spans + exceptions to logfire

    return app
