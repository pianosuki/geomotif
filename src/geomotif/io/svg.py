"""Write a design as SVG, in pure standard library.

SVG is the format that goes everywhere from here: a browser, Illustrator or
Inkscape, a laser cutter, a pen plotter's toolchain, and the gallery in these
docs. Nothing is imported that is not already installed.

Two things about the output are worth knowing up front.

**Y points down.** SVG's origin is the top-left corner and y grows downward,
which is the opposite of the convention every motif here is written in. So
``flip_y`` defaults to true and a design comes out the way you drew it. Turn it
off only if you are feeding the result to something that shares SVG's axes
already.

**The coordinates are transformed, not the canvas.** The design is fitted into
the canvas before anything is written, rather than being scaled by a
``viewBox``. That way ``stroke_width`` means the same thing whatever the design
measured -- one unit of the file you are looking at -- and rounding coordinates
to ``precision`` actually shrinks the file rather than throwing away detail
that a later scale would have magnified.

A design carrying styles (:mod:`geomotif.core.style`) writes its layers as the
labelled groups Inkscape and ``vpype`` read, and its colours as attributes on
the individual elements. A design carrying none writes exactly the file it
always did.
"""

from __future__ import annotations

import itertools
import pathlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape, quoteattr

from ..core.registry import NAME_KEY
from ..core.style import by_layer, layer_names, point_styles_of, styles_of

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

    from ..core.style import Style
    from ..core.types import Design, Point

__all__ = ["save_svg", "to_svg"]

SVG_NS = "http://www.w3.org/2000/svg"

#: Where a layer's name lives. Inkscape's namespace rather than a geomotif one
#: because Inkscape got there first and everything downstream -- ``vpype``
#: included -- reads a layer by looking for exactly these two attributes.
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

#: A design flat in one axis -- a horizontal line, a single point -- still
#: needs a canvas taller than nothing to sit in. One unit holds a stroke.
_MIN_EXTENT = 1.0

#: Decimal places for a stroke width. Independent of the coordinate precision,
#: which is routinely zero for a plotter file and would round a 0.3mm pen away.
_WIDTH_PRECISION = 3


@dataclass(frozen=True, slots=True)
class _Ink:
    """What the document draws in, before any individual style overrides it."""

    stroke: str
    stroke_width: float
    fill: str
    radius: float


def to_svg(
    design: Design,
    *,
    width: float | None = None,
    height: float | None = None,
    padding: float = 8.0,
    stroke: str = "#0b0b0b",
    stroke_width: float = 1.0,
    fill: str = "none",
    background: str | None = None,
    dot_radius: float | None = None,
    flip_y: bool = True,
    precision: int = 3,
    group_by_path: bool = True,
    title: str | None = None,
) -> str:
    """Render a design as an SVG document.

    Parameters
    ----------
    design : Design
        What to draw. Its strokes become ``<path>`` elements and its loose
        points become ``<circle>`` elements.
    width, height : float, optional
        Canvas size in user units. Give both to fit the design into exactly
        that rectangle; give one and the other follows from the design's own
        proportions; give neither and the design keeps its own measurements,
        with ``padding`` added around it.
    padding : float, optional
        Margin reserved on all four sides.
    stroke, stroke_width, fill : str, float, str, optional
        Applied to the group holding the strokes. ``fill="none"`` is the
        default because most of this catalogue is line work; name a colour to
        fill the closed paths instead.
    background : str, optional
        Draw a filled rectangle behind everything. Omitted by default, which
        leaves the canvas transparent.
    dot_radius : float, optional
        Radius for the loose points. Defaults to ``stroke_width``, so dots
        read about as heavy as lines; pass ``0`` to leave them out entirely.
    flip_y : bool, optional
        Mirror vertically, so a design drawn y-up appears the right way up in
        SVG's y-down space. On by default.
    precision : int, optional
        Decimal places for coordinates. Trailing zeros are dropped, so a whole
        number costs one character rather than five.
    group_by_path : bool, optional
        Give every stroke its own ``<path>`` element, so an editor treats them
        as separate objects. Turn it off to merge them into one element with
        several subpaths, which is smaller but arrives as a single shape.
    title : str, optional
        The document's ``<title>``. Defaults to the motif recorded in the
        design's metadata, which is what makes a gallery file self-labelling.

    Returns
    -------
    str
        A complete SVG document, ending in a newline.

    Raises
    ------
    ValueError
        If the design has no points, or ``padding`` leaves no room inside the
        canvas asked for.
    """
    if not len(design):
        raise ValueError("cannot write an empty design to SVG: there is nothing to draw")
    if padding < 0:
        raise ValueError(f"padding must be >= 0, got {padding}")
    if precision < 0:
        raise ValueError(f"precision must be >= 0, got {precision}")

    canvas_w, canvas_h = _canvas(design, width, height, padding)
    placed = design.fit(canvas_w, canvas_h, padding=padding, flip_y=flip_y)
    radius = stroke_width if dot_radius is None else dot_radius
    layers = by_layer(placed) if layer_names(placed) else {None: placed}

    def num(value: float) -> str:
        return _num(value, precision)

    namespaces = f'xmlns="{SVG_NS}"'
    if any(name is not None for name in layers):
        namespaces += f' xmlns:inkscape="{INKSCAPE_NS}"'
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg {namespaces} width="{num(canvas_w)}" '
        f'height="{num(canvas_h)}" viewBox="0 0 {num(canvas_w)} {num(canvas_h)}">',
    ]

    label = title if title is not None else str(design.meta.get(NAME_KEY, "") or "")
    if label:
        lines.append(f"  <title>{escape(label)}</title>")
    if background is not None:
        lines.append(
            f'  <rect width="{num(canvas_w)}" height="{num(canvas_h)}" '
            f"fill={quoteattr(background)}/>"
        )

    defaults = _Ink(stroke=stroke, stroke_width=stroke_width, fill=fill, radius=radius)
    for name, part in layers.items():
        body = _elements(
            part,
            defaults,
            indent=1 if name is None else 2,
            precision=precision,
            group_by_path=group_by_path,
        )
        if name is None:
            lines.extend(body)
            continue
        # Inkscape's own attributes, which is also what vpype reads a layer
        # from. Anything else opens the file as a plain group and loses only
        # the name.
        lines.append(
            f'  <g inkscape:groupmode="layer" inkscape:label={quoteattr(name)} '
            f"id={quoteattr(name)}>"
        )
        lines.extend(body)
        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def save_svg(design: Design, path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Write a design to an SVG file and return the path written.

    Keyword arguments are passed straight through to :func:`to_svg`.
    """
    target = pathlib.Path(path)
    target.write_text(to_svg(design, **kwargs))
    return target


def _elements(
    design: Design,
    defaults: _Ink,
    *,
    indent: int,
    precision: int,
    group_by_path: bool,
) -> list[str]:
    """Return the stroke group and the dot group for one layer's geometry."""
    pad = "  " * indent
    lines: list[str] = []

    if design.paths:
        lines.append(
            f"{pad}<g fill={quoteattr(defaults.fill)} stroke={quoteattr(defaults.stroke)} "
            f'stroke-width="{_num(defaults.stroke_width, _WIDTH_PRECISION)}" '
            'stroke-linecap="round" stroke-linejoin="round">'
        )
        lines.extend(
            _strokes(
                design, defaults, indent=indent + 1, precision=precision, merge=not group_by_path
            )
        )
        lines.append(f"{pad}</g>")

    if design.points and defaults.radius > 0:
        inner = "  " * (indent + 1)
        lines.append(f'{pad}<g fill={quoteattr(defaults.stroke)} stroke="none">')
        for (x, y), style in zip(design.points, point_styles_of(design), strict=True):
            # A dot's colour is a fill here, and its own width -- how heavy the
            # mark is -- is its radius, which is the same reading that makes
            # dot_radius default to stroke_width.
            radius = (
                style.width if style is not None and style.width is not None else defaults.radius
            )
            colour = (
                f" fill={quoteattr(style.stroke)}"
                if style is not None
                and style.stroke is not None
                and style.stroke != defaults.stroke
                else ""
            )
            lines.append(
                f'{inner}<circle cx="{_num(x, precision)}" cy="{_num(y, precision)}" '
                f'r="{_num(radius, _WIDTH_PRECISION)}"{colour}/>'
            )
        lines.append(f"{pad}</g>")
    return lines


def _strokes(
    design: Design,
    defaults: _Ink,
    *,
    indent: int,
    precision: int,
    merge: bool,
) -> list[str]:
    """Return one ``<path>`` per stroke, or as few as their styles allow."""
    pad = "  " * indent
    drawn = [
        (
            _subpath(path.points, closed=path.closed, precision=precision),
            _overrides(style, defaults),
        )
        for path, style in zip(design.paths, styles_of(design), strict=True)
    ]
    if not merge:
        return [f'{pad}<path d="{d}"{attributes}/>' for d, attributes in drawn]
    # One element can carry one set of attributes, so merging stops wherever
    # the styling changes -- and never reorders, since order is drawing order.
    return [
        f'{pad}<path d="{" ".join(d for d, _ in run)}"{attributes}/>'
        for attributes, run in itertools.groupby(drawn, key=lambda item: item[1])
    ]


def _overrides(style: Style | None, defaults: _Ink) -> str:
    """Return the attributes a style adds to one element, or ``""`` for none.

    Only what actually differs from the group is written: a style that names
    the colour the document already draws in should not cost an attribute on
    every one of four thousand strokes.
    """
    if style is None:
        return ""
    parts: list[str] = []
    if style.stroke is not None and style.stroke != defaults.stroke:
        parts.append(f"stroke={quoteattr(style.stroke)}")
    if style.width is not None and style.width != defaults.stroke_width:
        parts.append(f'stroke-width="{_num(style.width, _WIDTH_PRECISION)}"')
    if style.fill is not None and style.fill != defaults.fill:
        parts.append(f"fill={quoteattr(style.fill)}")
    return f" {' '.join(parts)}" if parts else ""


def _canvas(
    design: Design, width: float | None, height: float | None, padding: float
) -> tuple[float, float]:
    """Return the canvas to fit into, filling in whichever side was left out.

    A side derived from the other keeps the design's own proportions, so
    ``to_svg(design, width=800)`` never squashes anything.
    """
    bounds = design.bounds
    inner_w = max(bounds.width, _MIN_EXTENT)
    inner_h = max(bounds.height, _MIN_EXTENT)
    margins = 2.0 * padding
    if width is not None and height is not None:
        return float(width), float(height)
    if width is not None:
        return float(width), margins + (width - margins) * inner_h / inner_w
    if height is not None:
        return margins + (height - margins) * inner_w / inner_h, float(height)
    return inner_w + margins, inner_h + margins


def _subpath(points: Iterable[Point], *, closed: bool, precision: int) -> str:
    """Return one ``M ... L ...`` subpath for a polyline."""
    coords = [f"{_num(x, precision)} {_num(y, precision)}" for x, y in points]
    # `L` takes as many pairs as you give it, so naming it once per stroke
    # rather than once per point roughly halves the size of a dense curve.
    drawn = f"M {coords[0]}" if len(coords) == 1 else f"M {coords[0]} L {' '.join(coords[1:])}"
    return f"{drawn} Z" if closed and len(coords) > 2 else drawn


def _num(value: float, precision: int) -> str:
    """Format a coordinate, dropping the zeros nobody needs to read."""
    text = f"{value:.{precision}f}"
    if precision > 0:
        text = text.rstrip("0").rstrip(".")
    # -0 is a real float and a silly thing to write down.
    return "0" if text in {"-0", "", "-"} else text
