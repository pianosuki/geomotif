"""Turn a design into pixels, in pure standard library.

Everything else this library writes is vector, and for good reason: a design is
a set of curves and the formats that keep them curves are the ones worth
writing. This module exists for the one thing vector cannot do on its own --
:mod:`animation <geomotif.io.gif>`, which needs frames, and a frame is pixels.

The output is an **indexed** image: one palette entry per pixel rather than a
colour per pixel, which is what GIF wants and what keeps a line drawing small.
Index 0 is the background and the strokes take whatever indices their styles
worked out to, so a two-pen design rasterizes in two colours without being told
twice.

Lines are drawn with Bresenham's algorithm, which is exactly right here: the
output is a handful of colours with no blending between them, so there is
nothing for antialiasing to blend *with*.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.style import point_styles_of, styles_of
from ..core.types import Bounds

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ..core.style import Style
    from ..core.types import Design, Point

__all__ = ["Raster", "colours_in", "rasterize"]

#: A design flat in one axis still needs somewhere to sit; see the SVG writer,
#: which resolves the same degeneracy the same way.
_MIN_EXTENT = 1.0


@dataclass(frozen=True, slots=True)
class Raster:
    """An indexed bitmap: one palette index per pixel, top-left origin.

    Parameters
    ----------
    width, height : int
        Size in pixels.
    pixels : bytes
        ``width * height`` palette indices, row-major.
    palette : tuple of str
        The colours those indices name, as ``#rrggbb``. Index 0 is the
        background.
    """

    width: int
    height: int
    pixels: bytes
    palette: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.pixels) != self.width * self.height:
            raise ValueError(
                f"a {self.width}x{self.height} raster needs "
                f"{self.width * self.height} pixels, got {len(self.pixels)}"
            )


def colours_in(designs: Iterable[Design], *, ink: str, background: str) -> tuple[str, ...]:
    """Return the palette a set of designs needs, background first.

    Shared across every frame of an animation rather than worked out per frame:
    a GIF has one global colour table, and an index that meant crimson in one
    frame and black in the next would make the whole thing flicker.
    """
    palette = [background, ink]
    for design in designs:
        for style in (*styles_of(design), *point_styles_of(design)):
            if style is not None and style.stroke is not None and style.stroke not in palette:
                palette.append(style.stroke)
    return tuple(palette)


def rasterize(
    design: Design,
    *,
    width: int = 480,
    height: int = 480,
    padding: float = 8.0,
    bounds: Bounds | None = None,
    palette: Sequence[str] | None = None,
    ink: str = "#0b0b0b",
    background: str = "#ffffff",
    thickness: int = 1,
    dot_radius: int | None = None,
) -> Raster:
    """Draw a design into an indexed bitmap.

    Parameters
    ----------
    design : Design
        What to draw.
    width, height : int
        Canvas size in pixels.
    padding : float
        Margin reserved on all four sides, in pixels.
    bounds : Bounds, optional
        The world rectangle to map onto the canvas. Defaults to the design's
        own, which is right for a single image and wrong for a frame of an
        animation -- there, pass the same bounds to every frame or the drawing
        will swim about as its extent changes.
    palette : sequence of str, optional
        Colours the indices name, background first. Defaults to
        ``(background, ink)`` plus whatever the design's styles add.
    ink, background : str
        Default stroke colour and the colour behind everything.
    thickness : int
        Stroke width in pixels.
    dot_radius : int, optional
        Radius for loose points. Defaults to ``thickness``.

    Returns
    -------
    Raster
        Ready to hand to :func:`geomotif.io.gif.to_gif`.
    """
    if width < 1 or height < 1:
        raise ValueError(f"width and height must be >= 1, got {width}x{height}")
    if thickness < 1:
        raise ValueError(f"thickness must be >= 1, got {thickness}")

    entries = (
        tuple(palette)
        if palette is not None
        else colours_in([design], ink=ink, background=background)
    )
    pixels = bytearray(width * height)
    radius = thickness if dot_radius is None else dot_radius
    place = _placement(bounds if bounds is not None else _bounds_of(design), width, height, padding)

    for path, style in zip(design.paths, styles_of(design), strict=True):
        index = _index_for(style, entries)
        pen = _pen(style, thickness)
        drawn = [place(p) for p in path.points]
        if path.closed and len(drawn) > 2:
            drawn.append(drawn[0])
        if len(drawn) == 1:
            _stamp(pixels, width, height, drawn[0][0], drawn[0][1], index, pen)
        for a, b in itertools.pairwise(drawn):
            _line(pixels, width, height, a, b, index, pen)

    for point, style in zip(design.points, point_styles_of(design), strict=True):
        index = _index_for(style, entries)
        _disc(pixels, width, height, place(point), _pen(style, radius), index)

    return Raster(width, height, bytes(pixels), entries)


def _bounds_of(design: Design) -> Bounds:
    """Return a design's bounds, or a unit square if it has no points at all."""
    if not len(design):
        return Bounds(0.0, 0.0, _MIN_EXTENT, _MIN_EXTENT)
    return design.bounds


def _placement(
    bounds: Bounds, width: int, height: int, padding: float
) -> Callable[[Point], tuple[int, int]]:
    """Return the world-to-pixel mapping: uniform scale, centred, y flipped."""
    extent_x = max(bounds.width, _MIN_EXTENT)
    extent_y = max(bounds.height, _MIN_EXTENT)
    inner_w = max(width - 2.0 * padding, 1.0)
    inner_h = max(height - 2.0 * padding, 1.0)
    scale = min(inner_w / extent_x, inner_h / extent_y)
    offset_x = padding + (inner_w - extent_x * scale) / 2.0
    offset_y = padding + (inner_h - extent_y * scale) / 2.0

    def place(point: Point) -> tuple[int, int]:
        x = offset_x + (point[0] - bounds.min_x) * scale
        y = offset_y + (point[1] - bounds.min_y) * scale
        # Pixels grow downward and the maths does not, so y is flipped here for
        # the same reason the SVG writer flips it.
        return (round(x), round(height - y))

    return place


def _index_for(style: Style | None, palette: Sequence[str]) -> int:
    """Return the palette index a stroke draws in: its own colour, or the default."""
    if style is None or style.stroke is None:
        return 1
    try:
        return palette.index(style.stroke)
    except ValueError:
        # A colour the palette was not built from. Drawing it in the default
        # ink is better than dropping the stroke or growing the table here.
        return 1


def _pen(style: Style | None, fallback: int) -> int:
    """Return how many pixels wide a stroke is drawn."""
    if style is None or style.width is None:
        return fallback
    return max(1, round(style.width))


def _line(
    pixels: bytearray,
    width: int,
    height: int,
    a: tuple[int, int],
    b: tuple[int, int],
    index: int,
    pen: int,
) -> None:
    """Draw one segment with Bresenham's algorithm."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    step_x = 1 if x0 < x1 else -1
    step_y = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        _stamp(pixels, width, height, x0, y0, index, pen)
        if x0 == x1 and y0 == y1:
            return
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += step_x
        if doubled <= dx:
            error += dx
            y0 += step_y


def _stamp(
    pixels: bytearray, width: int, height: int, x: int, y: int, index: int, pen: int
) -> None:
    """Set one pixel, or a square of them for a wider pen."""
    if pen <= 1:
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = index
        return
    half = pen // 2
    for oy in range(y - half, y - half + pen):
        if not 0 <= oy < height:
            continue
        row = oy * width
        for ox in range(x - half, x - half + pen):
            if 0 <= ox < width:
                pixels[row + ox] = index


def _disc(
    pixels: bytearray, width: int, height: int, centre: tuple[int, int], radius: int, index: int
) -> None:
    """Fill a circle, which is what a loose point looks like."""
    cx, cy = centre
    if radius <= 1:
        _stamp(pixels, width, height, cx, cy, index, 1)
        return
    limit = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        if not 0 <= y < height:
            continue
        row = y * width
        span = (y - cy) ** 2
        for x in range(cx - radius, cx + radius + 1):
            if 0 <= x < width and span + (x - cx) ** 2 <= limit:
                pixels[row + x] = index
