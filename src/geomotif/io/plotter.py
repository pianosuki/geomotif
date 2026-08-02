"""Preparing a design for a pen plotter.

A plotter cares about three things this library otherwise does not: how big the
paper is, how far the pen travels while it is *up*, and which pen is drawing.
This module answers all three.

**A real size.** :func:`to_plotter_svg` writes the drawing at a named paper
size in millimeters -- ``width="210mm"``, not ``width="210"`` -- so what comes
out of the plotter is the size you asked for rather than whatever the receiving
software guessed.

**Fewer wasted moves.** :func:`optimize` joins strokes that end where another
begins and then orders them so the pen travels as little as possible between
them -- which on a plotted mandala is most of the drawing time.
:func:`pen_up_distance` measures the difference rather than asserting it.

**One pen at a time.** Everything here works layer by layer
(:mod:`geomotif.core.style`) and never joins or reorders across layers: two
strokes on different layers are drawn by different pens, and merging them would
mean drawing one of them in the wrong color.

::

    from geomotif.io.plotter import optimize, pen_up_distance, save_plotter_svg

    design = optimize(mandala.build())
    save_plotter_svg(design, "mandala.svg", paper="a4", margin=15.0)

For anything beyond this -- occlusion, hatching, HPGL -- reach for ``vpype``,
which does all of it and which :func:`to_vpype` hands a design to directly.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ..core.style import Style, by_layer, point_styles_of, styles_of
from ..core.types import PATH_STYLE_KEY, POINT_STYLE_KEY, Design, Path
from .svg import to_svg

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from os import PathLike

    from ..core.types import Point

__all__ = [
    "DEFAULT_PEN",
    "PAPER",
    "on_page",
    "optimize",
    "page_size",
    "pen_up_distance",
    "save_plotter_svg",
    "to_plotter_svg",
    "to_vpype",
]

#: Paper sizes in millimeters, portrait. The ISO A series plus the two North
#: American sizes anyone plots on.
PAPER: Mapping[str, tuple[float, float]] = MappingProxyType(
    {
        "a2": (420.0, 594.0),
        "a3": (297.0, 420.0),
        "a4": (210.0, 297.0),
        "a5": (148.0, 210.0),
        "a6": (105.0, 148.0),
        "letter": (215.9, 279.4),
        "legal": (215.9, 355.6),
        "tabloid": (279.4, 431.8),
    }
)

#: A fine liner, in millimeters. The default because it is what most plotter
#: pens are, and because a stroke width has to be *something* once the file is
#: measured in real units.
DEFAULT_PEN = 0.35


def page_size(paper: str = "a4", *, landscape: bool = False) -> tuple[float, float]:
    """Return a named paper's size in millimeters.

    Raises
    ------
    KeyError
        If the name is not one of :data:`PAPER`. The message lists what is.
    """
    key = paper.strip().lower()
    if key not in PAPER:
        raise KeyError(f"no paper size called {paper!r}; try one of {sorted(PAPER)}")
    width, height = PAPER[key]
    return (height, width) if landscape else (width, height)


def on_page(
    design: Design,
    *,
    paper: str = "a4",
    margin: float = 10.0,
    landscape: bool = False,
) -> Design:
    """Return ``design`` fitted to a sheet of paper, in millimeters, y-down.

    Scaling is uniform and the drawing is centered, so nothing is distorted and
    the margin is honored on all four sides. The result is in the coordinate
    space a plotter and an SVG both use -- y growing downward -- which is why
    it is worth doing once here rather than in each writer.
    """
    width, height = page_size(paper, landscape=landscape)
    return design.fit(width, height, padding=margin, flip_y=True)


def to_plotter_svg(
    design: Design,
    *,
    paper: str = "a4",
    margin: float = 10.0,
    landscape: bool = False,
    stroke_width: float = DEFAULT_PEN,
    **kwargs: Any,
) -> str:
    """Render a design as an SVG measured in real millimeters.

    Parameters
    ----------
    design : Design
        What to plot.
    paper : str
        A name from :data:`PAPER`.
    margin : float
        Border to leave unplotted, in millimeters. Worth more than you would
        think: most plotters cannot reach the last few millimeters of a sheet.
    landscape : bool
        Turn the paper on its side.
    stroke_width : float
        Pen width in millimeters. Only affects how the file *looks* -- a
        plotter draws with the pen it has -- but getting it right makes the
        preview honest.
    **kwargs
        Passed to :func:`~geomotif.io.svg.to_svg`.

    Returns
    -------
    str
        An SVG whose ``width`` and ``height`` carry ``mm``, whose ``viewBox``
        is the same numbers, and whose layers are the groups ``vpype`` and
        Inkscape read.
    """
    width, height = page_size(paper, landscape=landscape)
    # The writer does the placing. Fitting to the page here as well would only
    # be undone: to_svg fits whatever it is given into the canvas it is given,
    # so a margin applied first is scaled straight back out to the paper edge.
    return to_svg(
        design,
        width=width,
        height=height,
        padding=margin,
        stroke_width=stroke_width,
        units="mm",
        **kwargs,
    )


def save_plotter_svg(design: Design, path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Write a plotter-ready SVG and return the path written.

    Keyword arguments are passed straight through to :func:`to_plotter_svg`.
    """
    target = pathlib.Path(path)
    target.write_text(to_plotter_svg(design, **kwargs))
    return target


def pen_up_distance(design: Design, *, start: Point = (0.0, 0.0)) -> float:
    """Return how far the pen travels while it is *not* drawing.

    Counted from ``start`` to the first stroke, then between the end of each
    stroke and the beginning of the next. This is the number :func:`optimize`
    exists to reduce, and the one to measure it by.
    """
    pen = start
    total = 0.0
    for path in design.paths:
        if not path.points:
            continue
        total += math.dist(pen, path.points[0])
        pen = path.points[0] if path.closed else path.points[-1]
    return total


def optimize(
    design: Design,
    *,
    tolerance: float = 0.1,
    merge: bool = True,
    sort: bool = True,
    start: Point = (0.0, 0.0),
) -> Design:
    """Return ``design`` with its strokes joined up and put in a sensible order.

    Two passes, both of which only ever move whole strokes about:

    1. **Merge.** Two open strokes whose ends meet within ``tolerance`` become
       one, reversing either if that is what makes them meet. A stroke whose
       own ends then meet is closed. This is where a tiling built cell by cell
       stops being four thousand separate edges.
    2. **Sort.** The strokes are ordered greedily from ``start``, always taking
       whichever begins nearest to where the pen just finished, and reversing
       an open stroke when its far end is the nearer one.

    Neither pass crosses a layer, for the reason this module opens with, and
    layers come out in the order they went in.

    Parameters
    ----------
    design : Design
        What to optimize.
    tolerance : float
        How close two ends must be to count as touching, in the design's own
        units. Must be >= 0; zero demands exactly equal coordinates.
    merge, sort : bool
        Run each pass. Both on by default.
    start : (float, float)
        Where the pen begins, for the sort.

    Returns
    -------
    Design
        The same ink in the same colors, drawn in a better order. Loose
        points and metadata are carried through untouched -- a dot is a dot
        wherever it is in the list.

    Notes
    -----
    Both passes are O(n²) in the number of strokes, which is nothing at the
    thousands a plotted design runs to and would matter at a million. Neither
    is optimal, and neither is trying to be: this is nearest-neighbour applied
    to the travelling salesman, which carries no bound on how far from the best
    answer it lands but is what ``vpype linesort`` does too. The suite measures
    the two against each other rather than taking either on trust.
    """
    if tolerance < 0:
        raise ValueError(f"tolerance must be >= 0, got {tolerance}")

    ordered: list[_Stroke] = []
    pen = start
    for part in by_layer(design).values():
        strokes = [
            _Stroke(list(path.points), path.closed, style)
            for path, style in zip(part.paths, styles_of(part), strict=True)
            if path.points
        ]
        if merge:
            strokes = _merged(strokes, tolerance)
        if sort:
            strokes, pen = _ordered(strokes, pen)
        ordered.extend(strokes)

    return _assembled(ordered, design)


@dataclass(slots=True)
class _Stroke:
    """One stroke while it is being rearranged: mutable, unlike a Path."""

    points: list[Point]
    closed: bool
    style: Style | None

    @property
    def start(self) -> Point:
        return self.points[0]

    @property
    def end(self) -> Point:
        return self.points[0] if self.closed else self.points[-1]


def _merged(strokes: list[_Stroke], tolerance: float) -> list[_Stroke]:
    """Join strokes whose ends meet, greedily and in the order they arrived."""
    pending = [stroke for stroke in strokes if not stroke.closed]
    out = [stroke for stroke in strokes if stroke.closed]
    order = {id(stroke): index for index, stroke in enumerate(strokes)}

    merged: list[_Stroke] = []
    while pending:
        current = pending.pop(0)
        while True:
            attached = _attach(current, pending, tolerance)
            if attached is None:
                break
            pending.remove(attached)
        # Ends that have come back round to meet: a loop, and worth saying so,
        # since a closed path is one stroke to a plotter rather than a line
        # that happens to finish where it started.
        if len(current.points) > 3 and math.dist(current.start, current.points[-1]) <= tolerance:
            current.points.pop()
            current.closed = True
        merged.append(current)

    out.extend(merged)
    # Closed strokes were set aside rather than reordered; putting everything
    # back the way it arrived keeps the result stable and readable.
    return sorted(out, key=lambda stroke: order.get(id(stroke), len(order)))


def _attach(current: _Stroke, pending: Sequence[_Stroke], tolerance: float) -> _Stroke | None:
    """Extend ``current`` with whichever pending stroke touches it, if any."""
    for other in pending:
        if other.style != current.style:
            continue
        if math.dist(current.points[-1], other.points[0]) <= tolerance:
            current.points.extend(other.points[1:])
            return other
        if math.dist(current.points[-1], other.points[-1]) <= tolerance:
            current.points.extend(reversed(other.points[:-1]))
            return other
        if math.dist(current.points[0], other.points[-1]) <= tolerance:
            current.points[:0] = other.points[:-1]
            return other
        if math.dist(current.points[0], other.points[0]) <= tolerance:
            current.points[:0] = list(reversed(other.points[1:]))
            return other
    return None


def _ordered(strokes: list[_Stroke], pen: Point) -> tuple[list[_Stroke], Point]:
    """Put strokes in the order that walks the pen least far between them."""
    remaining = list(strokes)
    out: list[_Stroke] = []
    while remaining:
        best = 0
        flip = False
        shortest = math.inf
        for index, stroke in enumerate(remaining):
            forward = math.dist(pen, stroke.points[0])
            if forward < shortest:
                best, flip, shortest = index, False, forward
            if not stroke.closed:
                backward = math.dist(pen, stroke.points[-1])
                if backward < shortest:
                    best, flip, shortest = index, True, backward
        chosen = remaining.pop(best)
        if flip:
            chosen.points.reverse()
        out.append(chosen)
        pen = chosen.end
    return out, pen


def _assembled(strokes: Iterable[_Stroke], original: Design) -> Design:
    """Rebuild a design from rearranged strokes, keeping every other part of it."""
    paths: list[Path] = []
    styles: list[Style | None] = []
    for stroke in strokes:
        paths.append(Path(tuple(stroke.points), closed=stroke.closed))
        styles.append(stroke.style)

    meta = dict(original.meta)
    # Written directly rather than through select_styles: merging is many
    # strokes to one, which no list of source indices can describe.
    if any(style is not None for style in styles):
        meta[PATH_STYLE_KEY] = tuple(styles)
    elif PATH_STYLE_KEY in meta:
        del meta[PATH_STYLE_KEY]
    if not any(style is not None for style in point_styles_of(original)):
        meta.pop(POINT_STYLE_KEY, None)
    return Design(tuple(paths), original.points, MappingProxyType(meta))


def to_vpype(
    design: Design,
    *,
    paper: str = "a4",
    margin: float = 10.0,
    landscape: bool = False,
) -> Any:
    """Return this design as a ``vpype`` document, fitted to a page.

    ``vpype`` is the pen-plotter toolchain -- occlusion, hatching, HPGL output,
    and a plotting pipeline this library is deliberately not trying to be. This
    is the door to it: one layer per :mod:`geomotif.core.style` layer, named the
    same, on a page of the size asked for.

    ::

        import vpype_cli

        document = to_vpype(design, paper="a3")
        vpype_cli.execute("linemerge linesort write out.svg", document)

    Returns
    -------
    vpype.Document
        Typed loosely because ``vpype`` is not a dependency and this module
        must stay importable without it.

    Raises
    ------
    ImportError
        If ``vpype`` is not installed, with the command that installs it.
    """
    try:
        import vpype
    except ImportError:
        raise ImportError(
            "geomotif.io.plotter.to_vpype requires vpype. Install it with: pip install vpype"
        ) from None

    width, height = page_size(paper, landscape=landscape)
    placed = on_page(design, paper=paper, margin=margin, landscape=landscape)
    # vpype measures everything in CSS pixels, so millimeters have to be said
    # in its units rather than assumed to be its units.
    per_mm = vpype.convert_length("1mm")

    document = vpype.Document()
    document.page_size = (width * per_mm, height * per_mm)
    for index, (name, part) in enumerate(by_layer(placed).items(), start=1):
        lines = vpype.LineCollection(
            [
                [complex(x * per_mm, y * per_mm) for x, y in _closed_points(path)]
                for path in part.paths
                if len(path.points) > 1
            ]
        )
        document.add(lines, layer_id=index)
        if name is not None:
            document.layers[index].set_property(vpype.METADATA_FIELD_NAME, name)
    return document


def _closed_points(path: Path) -> tuple[Point, ...]:
    """Return a path's points, repeating the first where the loop implies it.

    A closed path stores its seam implicitly; ``vpype`` has no closed flag and
    reads a loop as a line that comes back to where it started, so the vertex
    has to be written out on the way over.
    """
    if path.closed and len(path.points) > 2:
        return (*path.points, path.points[0])
    return path.points
