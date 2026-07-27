"""Write a design as DXF R12, in pure standard library.

DXF is what CAD, CAM and most laser and CNC toolchains read, and R12 is the
version of it worth hand-writing: small, frozen since 1992, exhaustively
documented, and accepted by everything that reads DXF at all. That keeps the
core dependency-free all the way out to the file.

The format is a flat stream of *group codes*: an integer on one line saying
what the next line means, then the value. A polyline is not one entity but
several -- a ``POLYLINE`` header, a ``VERTEX`` per point, and a ``SEQEND`` to
close the run. R12 has no ``LWPOLYLINE``; that arrived with R14, and using it
would give up the compatibility R12 was chosen for.

Unlike SVG, DXF is y-up, the same convention the motifs are written in, so
nothing is mirrored on the way out and a design keeps its own measurements. If
you want it scaled, scale the design -- :meth:`Design.fit` -- and the file will
say so in its own units.
"""

from __future__ import annotations

import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from os import PathLike

    from ..core.types import Design, Point

__all__ = ["save_dxf", "to_dxf"]

#: R12 layer names: letters, digits and a few punctuation marks, at most 31
#: characters. Enforced here rather than left to the reader, because a file
#: with an illegal layer name fails to open with no explanation of why.
_LAYER = re.compile(r"^[A-Za-z0-9_$\-.]{1,31}$")

#: Group code for the layer an entity sits on.
_LAYER_CODE = 8


def to_dxf(design: Design, *, layer: str = "0", precision: int = 4) -> str:
    """Render a design as a DXF R12 document.

    Parameters
    ----------
    design : Design
        What to write. Strokes become ``POLYLINE`` entities -- closed ones
        carry the closed flag rather than a repeated final vertex -- and loose
        points become ``POINT`` entities.
    layer : str, optional
        Layer for every entity. ``"0"`` is the layer every DXF file already
        has; any other name is declared in the file's layer table, so the
        result is valid on its own rather than relying on the reader to invent
        the layer.
    precision : int, optional
        Decimal places for coordinates.

    Returns
    -------
    str
        A complete DXF R12 document.

    Raises
    ------
    ValueError
        If the design is empty, the precision is negative, or the layer name
        is not one R12 permits.
    """
    if not len(design):
        raise ValueError("cannot write an empty design to DXF: there is nothing to draw")
    if precision < 0:
        raise ValueError(f"precision must be >= 0, got {precision}")
    if not _LAYER.match(layer):
        raise ValueError(
            f"{layer!r} is not a DXF R12 layer name: at most 31 characters from "
            f"letters, digits and _$-."
        )

    bounds = design.bounds

    def num(value: float) -> str:
        return f"{value:.{precision}f}"

    parts = [
        *_section(
            "HEADER",
            _tag(9, "$ACADVER"),
            _tag(1, "AC1009"),
            # The drawing extents: what "zoom to fit" uses when the file opens.
            _tag(9, "$EXTMIN"),
            _point(bounds.min_x, bounds.min_y, num),
            _tag(9, "$EXTMAX"),
            _point(bounds.max_x, bounds.max_y, num),
        ),
        *_section("TABLES", *_layer_table(layer)),
        *_section("ENTITIES", *_entities(design, layer, num)),
        _tag(0, "EOF"),
    ]
    return "".join(parts)


def save_dxf(
    design: Design,
    path: str | PathLike[str],
    *,
    layer: str = "0",
    precision: int = 4,
) -> pathlib.Path:
    """Write a design to a DXF file and return the path written.

    See :func:`to_dxf` for what the options mean.
    """
    target = pathlib.Path(path)
    target.write_text(to_dxf(design, layer=layer, precision=precision))
    return target


def _tag(code: int, value: object) -> str:
    """One group code and its value: the whole of DXF's syntax."""
    return f"{code}\n{value}\n"


def _point(x: float, y: float, num: Callable[[float], str]) -> str:
    """Write a coordinate as the x/y/z triple DXF expects."""
    # Z is not optional even in a drawing that is entirely flat; readers that
    # tolerate its absence are being generous, not correct.
    return _tag(10, num(x)) + _tag(20, num(y)) + _tag(30, num(0.0))


def _section(name: str, *body: str) -> Iterator[str]:
    """Wrap a run of tags in the SECTION/ENDSEC pair that delimits it."""
    yield _tag(0, "SECTION")
    yield _tag(2, name)
    yield from body
    yield _tag(0, "ENDSEC")


def _layer_table(layer: str) -> Iterator[str]:
    """Declare the layer, so the file does not lean on the reader to invent it."""
    yield _tag(0, "TABLE")
    yield _tag(2, "LAYER")
    yield _tag(70, 1)
    yield _tag(0, "LAYER")
    yield _tag(2, layer)
    yield _tag(70, 0)  # not frozen, not locked
    yield _tag(62, 7)  # colour index 7: white on dark, black on light
    yield _tag(6, "CONTINUOUS")
    yield _tag(0, "ENDTAB")


def _entities(design: Design, layer: str, num: Callable[[float], str]) -> Iterator[str]:
    """Emit one entity per stroke, then one per loose point."""
    for stroke in design.paths:
        yield from _polyline(stroke.points, closed=stroke.closed, layer=layer, num=num)
    for x, y in design.points:
        yield _tag(0, "POINT")
        yield _tag(_LAYER_CODE, layer)
        yield _point(x, y, num)


def _polyline(
    points: Iterable[Point], *, closed: bool, layer: str, num: Callable[[float], str]
) -> Iterator[str]:
    """Emit one POLYLINE, its VERTEX run, and the SEQEND that ends it."""
    yield _tag(0, "POLYLINE")
    yield _tag(_LAYER_CODE, layer)
    yield _tag(66, 1)  # vertices follow -- required in R12
    # Bit 1 of the flags is "closed": the closing segment is the reader's job,
    # which is why a closed path never repeats its first point here either.
    yield _tag(70, 1 if closed else 0)
    yield _point(0.0, 0.0, num)  # the polyline's own elevation, always flat
    for x, y in points:
        yield _tag(0, "VERTEX")
        yield _tag(_LAYER_CODE, layer)
        yield _point(x, y, num)
    yield _tag(0, "SEQEND")
    yield _tag(_LAYER_CODE, layer)
