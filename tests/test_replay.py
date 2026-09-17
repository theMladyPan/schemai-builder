"""Tests for CLI mock replay."""

from __future__ import annotations

import json

from schemai_builder import cli


def _rc_fixture(tmp_path):
    fixture = tmp_path / "rc.json"
    fixture.write_text(
        json.dumps(
            {
                "sleep": 0.05,
                "steps": [
                    {
                        "message": "add R",
                        "diff": {
                            "add_components": [
                                {
                                    "library_id": "R",
                                    "id": "r1",
                                    "ref": "R1",
                                    "value": "10k",
                                    "sheet": 1,
                                    "x": 80,
                                    "y": 100,
                                }
                            ]
                        },
                    },
                    {
                        "message": "add C",
                        "diff": {
                            "add_components": [
                                {
                                    "library_id": "C",
                                    "id": "c1",
                                    "ref": "C1",
                                    "value": "100n",
                                    "sheet": 1,
                                    "x": 240,
                                    "y": 100,
                                }
                            ]
                        },
                    },
                    {
                        "message": "add GND",
                        "diff": {
                            "add_components": [
                                {
                                    "library_id": "GND",
                                    "id": "gnd1",
                                    "ref": "GND1",
                                    "sheet": 1,
                                    "x": 240,
                                    "y": 220,
                                }
                            ]
                        },
                    },
                    {
                        "message": "add nets",
                        "diff": {
                            "add_nets": [
                                {"name": "IN", "role": "signal", "pins": ["r1.A"]},
                                {
                                    "name": "N1",
                                    "role": "signal",
                                    "pins": ["r1.B", "c1.A"],
                                },
                                {
                                    "name": "GND",
                                    "role": "ground",
                                    "pins": ["c1.B", "gnd1.A"],
                                },
                            ]
                        },
                    },
                ],
            }
        )
    )
    return fixture


def test_replay_fixture(tmp_path):
    fixture = _rc_fixture(tmp_path)
    out = tmp_path / "out"
    project = cli.replay(fixture, out, sleep=0)
    svg = (out / "sheet-1.svg").read_text()
    assert "<svg" in svg
    assert "R1" in svg
    assert "C1" in svg
    assert "GND" in svg
    assert project.history


def test_replay_escapes_ref(tmp_path):
    script = tmp_path / "bad.json"
    script.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "message": "bad ref",
                        "diff": {
                            "add_components": [
                                {"library_id": "R", "id": "r1", "ref": "R<1"}
                            ]
                        },
                    }
                ]
            }
        )
    )
    out = tmp_path / "out"
    cli.replay(script, out, sleep=0)
    svg = (out / "sheet-1.svg").read_text()
    assert "&lt;" in svg


def test_main_replay(tmp_path):
    fixture = _rc_fixture(tmp_path)
    out = tmp_path / "out2"
    assert cli.main(["replay", str(fixture), "--out", str(out), "--sleep", "0"]) is None
    assert (out / "sheet-1.svg").exists()
