"""color parsing shared by the raster-side writers.

Everything on the raster side ends in literal red, green and blue bytes, so a
name has to be resolved here or refused here -- unlike the SVG writer, which
can hand a color to the renderer to interpret. The names match the ones the
DXF writer can put a name to, and the :data:`NAMED` table is the same list the
GIF writer always kept.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["NAMED", "rgb"]

#: A color as three channel bytes. ``#rrggbb``.
type RGB = tuple[int, int, int]

#: color names this side of the library understands, matching the ones the DXF
#: writer can put a name to. A raster canvas holds literal red, green and blue,
#: so a name it does not know cannot be passed downstream the way the SVG
#: writer passes one -- it has to be resolved here or refused here.
NAMED: Mapping[str, RGB] = MappingProxyType(
    {
        "black": (0x00, 0x00, 0x00),
        "white": (0xFF, 0xFF, 0xFF),
        "red": (0xFF, 0x00, 0x00),
        "green": (0x00, 0x80, 0x00),
        "blue": (0x00, 0x00, 0xFF),
        "yellow": (0xFF, 0xFF, 0x00),
        "cyan": (0x00, 0xFF, 0xFF),
        "aqua": (0x00, 0xFF, 0xFF),
        "magenta": (0xFF, 0x00, 0xFF),
        "fuchsia": (0xFF, 0x00, 0xFF),
    }
)


def rgb(color: str) -> RGB:
    """Parse ``#rgb``, ``#rrggbb`` or a name from :data:`NAMED` into three bytes."""
    text = color.strip().lower()
    if text in NAMED:
        return NAMED[text]
    text = text.lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        raise ValueError(_unreadable(color))
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        raise ValueError(_unreadable(color)) from None


def _unreadable(color: str) -> str:
    """Say what went wrong, and what this side of the library can read instead."""
    return (
        f"cannot read {color!r} as a color: expected '#3366ff', '#36f', "
        f"or one of {sorted(NAMED)}. Unlike the SVG writer, a raster canvas "
        f"holds literal red, green and blue, so it cannot pass a color "
        f"through to something else to interpret"
    )
