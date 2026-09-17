"""reasons.md paragraph helpers and ReasonsPatch application."""

from __future__ import annotations

from .models import ReasonsPatch


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, strip whitespace, drop empty paragraphs."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def format_numbered(paragraphs: list[str]) -> str:
    """Format paragraphs as '[1] ...' lines joined by blank lines."""
    return "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paragraphs, 1))


def apply_reasons_patch(text: str, patch: ReasonsPatch) -> str:
    """Apply deletes (highest id first), then replaces, then appends; 1-based ids."""
    paragraphs = split_paragraphs(text)
    for i in sorted(patch.delete, reverse=True):
        if not 1 <= i <= len(paragraphs):
            raise ValueError(f"unknown paragraph id {i}")
        del paragraphs[i - 1]
    for r in patch.replace:
        if not 1 <= r.id <= len(paragraphs):
            raise ValueError(f"unknown paragraph id {r.id}")
        paragraphs[r.id - 1] = r.text
    paragraphs.extend(patch.append)
    return "\n\n".join(paragraphs)
