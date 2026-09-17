"""Tests for the FastAPI app (FunctionModel, no live API)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart

from schemai_builder.app import create_app


def _model(responses: list[str]):
    """FunctionModel replaying canned JSON outputs in order."""
    calls = {"n": 0}

    def fn(messages: list[ModelMessage], info) -> ModelResponse:
        i = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(content=responses[i])])

    return FunctionModel(fn)


_ADD_R = {
    "message": "added <script>alert(1)</script> resistor",
    "diff": {
        "add_components": [
            {"library_id": "R", "id": "rx", "ref": "R9", "x": 80, "y": 200}
        ]
    },
}


def test_index_and_empty_state(tmp_path):
    client = TestClient(create_app(tmp_path))
    r = client.get("/")
    assert r.status_code == 200
    assert "grid-template-columns" in r.text
    st = client.get("/state").json()
    assert st["sheets"] == [1]
    assert st["sheet"] == 1
    assert (tmp_path / "schematic.json").exists()


def test_chat_applies_diff_and_renders(tmp_path):
    model = _model([json.dumps(_ADD_R)])
    client = TestClient(create_app(tmp_path, model=model))
    r = client.post("/chat", data={"text": "add a resistor"})
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is True
    assert body["message"].startswith("added")
    assert body["sheets"] == [1]
    assert body["sheet"] == 1
    assert isinstance(body["erc"], list)
    svg = client.get("/sheet/1.svg")
    assert svg.status_code == 200
    assert "<svg" in svg.text


def test_chat_diff_error_returns_200(tmp_path):
    bad = json.dumps(
        {
            "message": "trying",
            "diff": {
                "add_components": [
                    {"library_id": "NOPE", "id": "x1", "ref": "X1", "x": 80, "y": 200}
                ]
            },
        }
    )
    model = _model([bad, bad])  # invalid twice -> retry also fails
    client = TestClient(create_app(tmp_path, model=model))
    r = client.post("/chat", data={"text": "add junk"})
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is False
    assert "unknown library_id" in body["message"]
    assert client.get("/state").json()["sheets"] == [1]  # schematic unchanged


def test_chat_with_file(tmp_path):
    model = _model([json.dumps(_ADD_R)])
    client = TestClient(create_app(tmp_path, model=model))
    r = client.post(
        "/chat",
        data={"text": "use notes"},
        files={"files": ("notes.txt", b"R1 to GND", "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["applied"] is True


def test_review(tmp_path):
    model = _model([json.dumps({"message": "looks ok"})])
    client = TestClient(create_app(tmp_path, model=model))
    r = client.post("/review")
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "looks ok"
    assert body["issues"] == []
    assert client.get("/state").json()["sheets"] == [1]  # schematic unchanged


def test_pdf(tmp_path):
    model = _model([json.dumps(_ADD_R)])
    client = TestClient(create_app(tmp_path, model=model))
    client.post("/chat", data={"text": "add a resistor"})
    r = client.get("/sheet/1.pdf")
    assert r.status_code in (200, 404)  # 404 only if cairosvg import fails
    if r.status_code == 200:
        assert r.content.startswith(b"%PDF")
    assert client.get("/sheet/2.svg").status_code == 404
    assert client.get("/sheet/2.pdf").status_code == 404


def test_xss_message_not_escaped_in_json_static_page(tmp_path):
    model = _model([json.dumps(_ADD_R)])
    client = TestClient(create_app(tmp_path, model=model))
    r = client.post("/chat", data={"text": "add a resistor"})
    assert (
        "<script>alert(1)</script>" in r.json()["message"]
    )  # verbatim, client escapes
    page = client.get("/").text
    assert "<script>alert(1)</script>" not in page  # static page, nothing injected
