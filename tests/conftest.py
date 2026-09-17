"""Shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _no_logfire_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank token wins over .env so tests never send telemetry."""
    monkeypatch.setenv("LOGFIRE_TOKEN", "")
