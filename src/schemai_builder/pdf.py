"""SVG-to-PDF conversion for export."""

from __future__ import annotations


def svg_to_pdf(svg: str) -> bytes | None:
    """Convert SVG to PDF via cairosvg; None if cairo is missing or fails."""
    # ponytail: skip PDF if cairo missing
    try:
        import cairosvg
    except ImportError:
        return None
    try:
        return cairosvg.svg2pdf(bytestring=svg.encode())
    except Exception:
        return None
