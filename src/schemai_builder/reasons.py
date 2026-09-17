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
    """Apply deletes/replaces against original 1-based ids, then append."""
    original = split_paragraphs(text)
    deleted = set(patch.delete)
    for i in deleted | {r.id for r in patch.replace}:
        if not 1 <= i <= len(original):
            raise ValueError(f"unknown paragraph id {i}")
    replacements = {r.id: r.text for r in patch.replace}
    paragraphs = [
        replacements[i] if i in replacements else p
        for i, p in enumerate(original, 1)
        if i not in deleted
    ]
    paragraphs.extend(patch.append)
    return "\n\n".join(paragraphs)
