"""Turn a design into pixels, in pure standard library.

Everything else this library writes is vector, and for good reason: a design is
a set of curves and the formats that keep them curves are the ones worth
writing. This module exists for the pixels, which vector cannot be -- the
frames of an animation, and the stills of PNG and JPEG.

The picture is **drawn once as a full-color frame** -- one RGBA value per
pixel, palette-free -- so that antialiasing, styling and every ink land in one
place and every encoder reads the same quality. Two output shapes come out of
it, in the :class:`Raster` type:

- A **direct** RGBA (or RGB) bitmap, the natural input for PNG and JPEG, which
  keep all 255 levels of color and edge.
- An **indexed** bitmap -- one palette entry per pixel -- which is what GIF
  wants and what keeps a line drawing small. When antialiasing creates blends
  the index frame cannot hold on its own, the RGBA frame is run through
  :func:`quantize`, which shrinks it to a shared palette of at most 256
  colors (with optional error-diffusion dithering) and never drops an ink.

Index 0 of a palette is the background and the strokes take whatever indices
their styles worked out to, so a two-pen design rasterizes in two colors
without being told twice.

With antialiasing off (the default), rendering is just the whole-pixel,
hard-edged Bresenham draw this module has always done; antialiasing supersamples
and then blends by coverage, which is the only part that costs more than a
plain single paint.
"""

from __future__ import annotations

import itertools
import warnings
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.style import point_styles_of, styles_of
from ..core.types import Bounds
from ._color import rgb as _rgb

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ..core.style import Style
    from ..core.types import Design, Point

__all__ = ["Raster", "colors_in", "colours_in", "quantize", "rasterize", "rasterize_rgba"]

#: A design flat in one axis still needs somewhere to sit; see the SVG writer,
#: which resolves the same degeneracy the same way.
_MIN_EXTENT = 1.0

#: How many sub-pixels an antialiased edge is supersampled at. The default is
#: modest because supersampling costs O(scale**2); the non-antialiased path is
#: untouched by it.
_AA_SCALE = 4


@dataclass(frozen=True, slots=True)
class Raster:
    """An in-memory picture, top-left origin.

    A :class:`Raster` holds either an **indexed** bitmap -- one palette index
    per pixel, which is what GIF wants -- or a **direct** one -- RGB or RGBA
    bytes per pixel, which is what PNG and JPEG want. Everything downstream
    (antialiasing, styling, the encoders) feeds off one of the two, so the
    picture is drawn once and encoded many ways.

    Parameters
    ----------
    width, height : int
        Size in pixels.
    pixels : bytes
        ``width * height`` indices (indexed), or ``width * height * 4`` RGBA
        or ``width * height * 3`` RGB bytes (direct), row-major.
    palette : tuple of str, optional
        The colors an indexed bitmap's indices name, as ``#rrggbb``. Index 0
        is the background. Unused by a direct bitmap.
    mode : str
        ``"indexed"``, ``"rgb"`` or ``"rgba"``. Defaults to ``"indexed"`` so
        a bare four-argument :class:`Raster` is the picture it has always
        been.
    """

    width: int
    height: int
    pixels: bytes
    palette: tuple[str, ...] = ()
    mode: str = "indexed"

    def __post_init__(self) -> None:
        span = self.width * self.height
        expected = {"indexed": span, "rgb": span * 3, "rgba": span * 4}
        if self.mode not in expected:
            raise ValueError(f"mode must be one of {sorted(expected)}, got {self.mode!r}")
        if len(self.pixels) != expected[self.mode]:
            raise ValueError(
                f"a {self.width}x{self.height} {self.mode} raster needs "
                f"{expected[self.mode]} bytes, got {len(self.pixels)}"
            )


def colors_in(designs: Iterable[Design], *, ink: str, background: str) -> tuple[str, ...]:
    """Return the palette a set of designs needs, background first.

    Shared across every frame of an animation rather than worked out per frame:
    a GIF has one global color table, and an index that meant crimson in one
    frame and black in the next would make the whole thing flicker.
    """
    palette = [background, ink]
    for design in designs:
        for style in (*styles_of(design), *point_styles_of(design)):
            if style is not None and style.stroke is not None and style.stroke not in palette:
                palette.append(style.stroke)
    return tuple(palette)


def colours_in(designs: Iterable[Design], *, ink: str, background: str) -> tuple[str, ...]:
    """Keep the British spelling working while it is phased out.

    :func:`colors_in` is the name of this function now; this alias exists so
    1.1.0 callers keep working, and it warns that it will go away in a future
    major release.
    """
    warnings.warn(
        "colours_in is deprecated; use colors_in instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return colors_in(designs, ink=ink, background=background)


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
        colors the indices name, background first. Defaults to
        ``(background, ink)`` plus whatever the design's styles add.
    ink, background : str
        Default stroke color and the color behind everything.
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
    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")

    entries = (
        tuple(palette)
        if palette is not None
        else colors_in([design], ink=ink, background=background)
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


def rasterize_rgba(
    design: Design,
    *,
    width: int = 480,
    height: int = 480,
    padding: float = 8.0,
    bounds: Bounds | None = None,
    ink: str = "#0b0b0b",
    background: str = "#ffffff",
    thickness: int = 1,
    dot_radius: int | None = None,
    scale: int = _AA_SCALE,
    aa_level: int | None = None,
    transparent: bool = False,
) -> Raster:
    """Draw a design into a full-color RGBA frame, supersampled and antialiased.

    Every pixel is a real (r, g, b, a) value rather than a palette index, so
    the edges can blend into the background -- which is the whole point of
    antialiasing. The design is painted ``scale`` times as large and each
    output pixel is the stroke color over the background weighted by the
    fraction of its sub-pixels the ink covered.

    Parameters
    ----------
    design : Design
        What to draw.
    width, height : int
        Canvas size in pixels.
    padding : float
        Margin reserved on all four sides, in pixels.
    bounds : Bounds, optional
        The world rectangle to map onto the canvas. Pass the same bounds to
        every frame of an animation or the drawing will swim about.
    ink, background : str
        Default stroke color and the color behind everything. When
        ``transparent`` is set, ``background`` is only what index 0 of an
        indexed result stands for -- it contributes no color at all.
    thickness : int
        Stroke width in pixels.
    dot_radius : int, optional
        Radius for loose points. Defaults to ``thickness``.
    scale : int
        Supersampling factor; ``1`` disables antialiasing. Must be >= 1.
    aa_level : int, optional
        If given, each sub-pixel coverage fraction is rounded to one of
        ``aa_level`` steps before blending, so an indexed frame later sees at
        most ``aa_level`` blended shades per color pair. Leave ``None`` for a
        PNG or JPEG, which keep full color depth.
    transparent : bool
        Leave the background empty rather than painting it. A pixel with no
        ink becomes ``alpha 0``; an antialiased edge becomes the stroke color
        with the coverage as its alpha, which is the straight alpha a PNG
        stores and the mask an indexed GIF flags. Off by default.

    Returns
    -------
    Raster
        An ``"rgba"`` frame, ready to hand to :func:`quantize` or an encoder.
    """
    if width < 1 or height < 1:
        raise ValueError(f"width and height must be >= 1, got {width}x{height}")
    if thickness < 1:
        raise ValueError(f"thickness must be >= 1, got {thickness}")
    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")
    if scale < 1:
        raise ValueError(f"scale must be >= 1, got {scale}")

    entries = colors_in([design], ink=ink, background=background)
    entry_rgb = [_rgb(color) for color in entries]
    sub_w, sub_h = width * scale, height * scale
    sub = bytearray(sub_w * sub_h)
    radius = thickness if dot_radius is None else dot_radius
    place = _placement(
        bounds if bounds is not None else _bounds_of(design), sub_w, sub_h, padding * scale
    )

    for path, style in zip(design.paths, styles_of(design), strict=True):
        index = _index_for(style, entries)
        pen = max(1, round(_pen(style, thickness) * scale))
        drawn = [place(p) for p in path.points]
        if path.closed and len(drawn) > 2:
            drawn.append(drawn[0])
        if len(drawn) == 1:
            _stamp(sub, sub_w, sub_h, drawn[0][0], drawn[0][1], index, pen)
        for first, second in itertools.pairwise(drawn):
            _line(sub, sub_w, sub_h, first, second, index, pen)

    for point, style in zip(design.points, point_styles_of(design), strict=True):
        index = _index_for(style, entries)
        _disc(sub, sub_w, sub_h, place(point), max(1, round(_pen(style, radius) * scale)), index)

    block = scale * scale
    out = bytearray(width * height * 4)
    for oy in range(height):
        sub_row = oy * scale
        for ox in range(width):
            counts = [0] * len(entry_rgb)
            for sy in range(scale):
                base = (sub_row + sy) * sub_w + ox * scale
                for sx in range(scale):
                    counts[sub[base + sx]] += 1
            at4 = 4 * (oy * width + ox)
            if transparent:
                # Index 0 (the background) covers nothing; alpha is the share
                # of the block the strokes actually paint, and the color is
                # that ink alone -- straight alpha, background-free.
                red = green = blue = norm = 0.0
                for index, count in enumerate(counts):
                    if count == 0 or index == 0:
                        continue
                    fraction = count / block
                    if aa_level is not None:
                        fraction = round(fraction * aa_level) / aa_level
                    norm += fraction
                    r, g, b = entry_rgb[index]
                    red += r * fraction
                    green += g * fraction
                    blue += b * fraction
                if aa_level is not None:
                    norm = round(norm * aa_level) / aa_level
                if norm <= 0:
                    out[at4 : at4 + 4] = (0, 0, 0, 0)
                    continue
                out[at4] = round(red / norm)
                out[at4 + 1] = round(green / norm)
                out[at4 + 2] = round(blue / norm)
                out[at4 + 3] = round(norm * 255)
                continue
            red = green = blue = 0.0
            for index, count in enumerate(counts):
                if count == 0:
                    continue
                fraction = count / block
                if aa_level is not None:
                    fraction = round(fraction * aa_level) / aa_level
                r, g, b = entry_rgb[index]
                red += r * fraction
                green += g * fraction
                blue += b * fraction
            out[at4 : at4 + 3] = (round(red), round(green), round(blue))
            out[at4 + 3] = 255
    return Raster(width, height, bytes(out), mode="rgba")


def quantize(
    frames: Sequence[Raster],
    *,
    seeds: Sequence[str] = (),
    max_colors: int = 256,
    dither: bool = True,
    transparent: bool = False,
) -> tuple[Raster, ...]:
    """Shrink RGBA frames to one shared indexed palette of at most ``max_colors``.

    The palette is built once across every frame -- so an animation does not
    flicker as the index a color means changes -- and is **seeded** with the
    colors given in ``seeds`` first, background first, keeping them exact. Any
    remaining color budget is filled from the blends the antialiasing made,
    cut down with median-cut when there are more of them than budget. A seed
    color is never dropped: asking for more seeds than ``max_colors`` raises
    instead.

    With ``transparent`` set, index 0 is reserved for empty space: a pixel
    whose alpha lies below the half point maps there instead of to a color,
    and the transparent slot does not count against the color budget.

    Parameters
    ----------
    frames : sequence of Raster
        ``"rgba"`` frames, all the same size, to share one palette.
    seeds : sequence of str
        colors that must survive exactly, background first, as ``#rrggbb`` or
        a name. These lead the palette, in order. The first -- the background
        -- is the reserved transparent slot when ``transparent`` is set.
    max_colors : int
        The largest palette the output may hold. Must be >= 1.
    dither : bool
        Whether to error-diffuse (Floyd-Steinberg) the rounding of each pixel
        onto its neighbours, which keeps antialiased gradients smooth within
        a small palette. On by default, since indexed output is where the
        color budget bites.
    transparent : bool
        Reserve index 0 for empty pixels and drop the background from the
        color budget. Off by default.

    Returns
    -------
    tuple of Raster
        One indexed :class:`Raster` per input frame, all sharing one
        ``palette``.
    """
    if not frames:
        raise ValueError("cannot quantize no frames")
    if max_colors < 1:
        raise ValueError(f"max_colors must be >= 1, got {max_colors}")
    for frame in frames:
        if frame.mode != "rgba":
            raise ValueError(
                f"quantize needs 'rgba' frames, got {frame.mode!r}; render with rasterize_rgba"
            )
        if (frame.width, frame.height) != (frames[0].width, frames[0].height):
            raise ValueError("all frames must share one size to share one palette")

    seed_rgb = []
    for seed in seeds:
        parsed = _rgb(seed)
        if parsed not in seed_rgb:
            seed_rgb.append(parsed)

    if transparent:
        if not seed_rgb:
            raise ValueError("a transparent palette needs a background seed to reserve")
        background_rgb = seed_rgb[0]
        color_seeds = seed_rgb[1:]
        budget = max_colors - 1
        if len(color_seeds) > budget:
            raise ValueError(
                f"a palette of {max_colors} colors cannot hold the "
                f"{len(color_seeds) + 1} colors requested (index 0 is transparent); "
                f"restyle the design onto fewer, or raise the budget"
            )
    else:
        background_rgb = seed_rgb[0] if seed_rgb else (255, 255, 255)
        color_seeds = seed_rgb
        budget = max_colors
        if len(color_seeds) > budget:
            raise ValueError(
                f"a palette of {max_colors} colors cannot hold the {len(color_seeds)} "
                f"colors requested; restyle the design onto fewer, or raise the budget"
            )

    counts = Counter[tuple[int, int, int]]()
    for frame in frames:
        buffer = frame.pixels
        for at in range(0, len(buffer), 4):
            if transparent and buffer[at + 3] < _EMPTY_ALPHA:
                continue
            source = (buffer[at], buffer[at + 1], buffer[at + 2])
            if source not in color_seeds:
                counts[source] += 1

    palette = [background_rgb] if transparent else []
    palette.extend(color_seeds)
    pairs = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    room = budget - len(color_seeds)
    if room <= 0:
        tail: list[tuple[int, int, int]] = []
    elif len(pairs) <= room:
        tail = [color for color, _ in pairs]
    else:
        tail = _median_cut([color for color, _ in pairs], counts, room)
    palette.extend(tail)

    hex_palette = tuple(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette)
    mapped = tuple(
        _map_to_palette(frame, palette, dither=dither, transparent=transparent) for frame in frames
    )
    return tuple(
        Raster(frame.width, frame.height, stride.pixels, hex_palette)
        for frame, stride in zip(frames, mapped, strict=True)
    )


#: A pixel with less than this alpha is treated as empty by :func:`quantize`.
_EMPTY_ALPHA = 128


def _median_cut(
    colors: Sequence[tuple[int, int, int]],
    weights: Counter[tuple[int, int, int]],
    target: int,
) -> list[tuple[int, int, int]]:
    """Split colors into ``target`` boxes, each averaged by its popularity.

    The standard algorithm: repeatedly split the box with the most members
    along its widest channel at the median, until there are ``target`` boxes,
    then take each box's weighted average as its representative. Splitting by
    median keeps every box a similar share of the histogram rather than letting
    one busy region steal the whole budget.
    """
    boxes: list[list[tuple[int, int, int]]] = [list(colors)]
    while len(boxes) < target:
        biggest = max((box for box in boxes if len(box) > 1), key=len, default=None)
        if biggest is None:
            break
        boxes.remove(biggest)
        lo, hi = _split_box(biggest)
        boxes.extend([lo, hi])

    result: list[tuple[int, int, int]] = []
    for box in boxes:
        total = sum(weights[color] for color in box) or 1
        r = sum(color[0] * weights[color] for color in box) // total
        g = sum(color[1] * weights[color] for color in box) // total
        b = sum(color[2] * weights[color] for color in box) // total
        result.append((r, g, b))
    return result


def _split_box(
    box: list[tuple[int, int, int]],
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """Split a box in half at the median of its widest channel."""
    channel, _ = max(
        (ch, max(color[ch] for color in box) - min(color[ch] for color in box)) for ch in range(3)
    )
    ordered = sorted(box, key=lambda color: color[channel])
    half = len(ordered) // 2
    return ordered[:half], ordered[half:]


def _map_to_palette(
    frame: Raster, palette: list[tuple[int, int, int]], *, dither: bool, transparent: bool = False
) -> Raster:
    """Map an RGBA frame's pixels onto ``palette``, optionally with error diffusion."""
    width, height = frame.width, frame.height
    pixels = frame.pixels
    color_entries = palette[1:] if transparent else palette
    shift = 1 if transparent else 0

    if not dither:
        out = bytearray(width * height)
        for oy in range(height):
            for ox in range(width):
                at = 4 * (oy * width + ox)
                if transparent and pixels[at + 3] < _EMPTY_ALPHA:
                    out[oy * width + ox] = 0
                    continue
                color = (pixels[at], pixels[at + 1], pixels[at + 2])
                out[oy * width + ox] = _nearest(color, color_entries) + shift
        return Raster(width, height, bytes(out))

    grid = [
        [float(pixels[4 * (y * width + x) + ch]) for ch in range(3) for x in range(width)]
        for y in range(height)
    ]
    alpha = [[pixels[4 * (y * width + x) + 3] for x in range(width)] for y in range(height)]
    out = bytearray(width * height)
    for oy in range(height):
        for ox in range(width):
            if transparent and alpha[oy][ox] < _EMPTY_ALPHA:
                out[oy * width + ox] = 0
                continue
            errant = (grid[oy][ox * 3], grid[oy][ox * 3 + 1], grid[oy][ox * 3 + 2])
            index = _nearest(errant, color_entries) + shift
            out[oy * width + ox] = index
            nearest = palette[index]
            error = (
                errant[0] - nearest[0],
                errant[1] - nearest[1],
                errant[2] - nearest[2],
            )
            _scatter(grid, alpha, width, height, oy, ox, error, transparent)
    return Raster(width, height, bytes(out))


def _scatter(
    grid: list[list[float]],
    alpha: list[list[int]] | None,
    width: int,
    height: int,
    y: int,
    x: int,
    error: tuple[float, float, float],
    transparent: bool,
) -> None:
    """Diffuse an RGB quantization error onto Floyd-Steinberg's four neighbours."""
    for dy, dx, weight in ((0, 1, 7), (1, -1, 3), (1, 0, 5), (1, 1, 1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < height and 0 <= nx < width:
            if transparent and alpha is not None and alpha[ny][nx] < _EMPTY_ALPHA:
                continue
            row = grid[ny]
            for ch in range(3):
                row[nx * 3 + ch] += error[ch] * weight / 16.0


def _nearest(color: tuple[float, float, float], palette: list[tuple[int, int, int]]) -> int:
    """Return the palette index closest to a color, ties to the earlier entry."""
    best, best_distance = 0, 1_000_000_000.0
    for index, entry in enumerate(palette):
        distance = (
            (color[0] - entry[0]) ** 2 + (color[1] - entry[1]) ** 2 + (color[2] - entry[2]) ** 2
        )
        if distance < best_distance:
            best, best_distance = index, distance
    return best


def _bounds_of(design: Design) -> Bounds:
    """Return a design's bounds, or a unit square if it has no points at all."""
    if not len(design):
        return Bounds(0.0, 0.0, _MIN_EXTENT, _MIN_EXTENT)
    return design.bounds


def _placement(
    bounds: Bounds, width: int, height: int, padding: float
) -> Callable[[Point], tuple[int, int]]:
    """Return the world-to-pixel mapping: uniform scale, centerd, y flipped."""
    extent_x = max(bounds.width, _MIN_EXTENT)
    extent_y = max(bounds.height, _MIN_EXTENT)
    # A w-pixel row addresses 0..w-1, so the span a drawing can occupy is one
    # short of the canvas. Scaling by the full width instead puts the far edge
    # on index w, which _stamp then discards -- invisible at the default
    # padding, and the right and bottom edges of the picture at padding=0.
    inner_w = max(width - 1 - 2.0 * padding, 1.0)
    inner_h = max(height - 1 - 2.0 * padding, 1.0)
    scale = min(inner_w / extent_x, inner_h / extent_y)
    offset_x = padding + (inner_w - extent_x * scale) / 2.0
    offset_y = padding + (inner_h - extent_y * scale) / 2.0

    def place(point: Point) -> tuple[int, int]:
        x = offset_x + (point[0] - bounds.min_x) * scale
        y = offset_y + (point[1] - bounds.min_y) * scale
        # Pixels grow downward and the maths does not, so y is flipped here for
        # the same reason the SVG writer flips it.
        return (round(x), round(height - 1 - y))

    return place


def _index_for(style: Style | None, palette: Sequence[str]) -> int:
    """Return the palette index a stroke draws in: its own color, or the default."""
    if style is None or style.stroke is None:
        return 1
    try:
        return palette.index(style.stroke)
    except ValueError:
        # A color the palette was not built from. Drawing it in the default
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
    pixels: bytearray, width: int, height: int, center: tuple[int, int], radius: int, index: int
) -> None:
    """Fill a circle, which is what a loose point looks like."""
    cx, cy = center
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
