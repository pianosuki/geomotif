"""Write coordinates out, and read a structured design back in.

Two writers, and the difference between them is strokes:

* :func:`save_points` flattens everything to one list of ``x, y`` pairs. It is
  what you want for a spreadsheet, a game map, or anything that just needs the
  coordinates.
* :func:`save_design` keeps the paths apart, so a plotter knows where to lift
  the pen and a reader knows which points belong to the same stroke.

Only the JSON form of :func:`save_design` reads back, via :func:`load_design`.
CSV and TXT are export formats: they are shaped for whatever tool is going to
consume them, and both flatten metadata away. If you want the design back, use
JSON -- and if you want the *recipe* back rather than the points, that is
:mod:`geomotif.io.spec`, which writes a file a hundred times smaller.
"""

from __future__ import annotations

import csv
import json
import pathlib
from typing import TYPE_CHECKING, Literal

from ..core.types import EMPTY_META, Design, Path
from .spec import VERSION_KEY, _meta_from_spec, to_spec

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from os import PathLike

    from ..core.types import Point

__all__ = ["PointFormat", "load_design", "save_design", "save_points"]

type PointFormat = Literal["csv", "txt", "json"]

_SUFFIX_FORMATS: dict[str, PointFormat] = {
    ".csv": "csv",
    ".txt": "txt",
    ".tsv": "txt",
    ".json": "json",
}


def save_points(
    points: Iterable[Point],
    path: str | PathLike[str],
    *,
    fmt: PointFormat | None = None,
    precision: int | None = None,
) -> pathlib.Path:
    """Write points to a file and return the path written.

    Parameters
    ----------
    points : iterable of (float, float)
        The points to export. A :class:`~geomotif.Design` is itself an
        iterable of points, so it can be passed directly.
    path : str or path-like
        Destination file.
    fmt : {"csv", "txt", "json"}, optional
        Output format. Inferred from the file suffix when omitted
        (``.csv``, ``.txt``/``.tsv``, ``.json``).

        * ``csv``  -- an ``x,y`` header followed by one ``x,y`` row per point
        * ``txt``  -- one tab-separated ``x<TAB>y`` line per point, no header
        * ``json`` -- a JSON array of ``[x, y]`` pairs
    precision : int, optional
        Round coordinates to this many decimal places. ``0`` and below write
        whole integers, each further step back rounding to tens, hundreds and
        so on. Default keeps full float precision.

        This rounds the *file* rather than the design, so it says nothing about
        what the other writers do with the same points.
        :meth:`~geomotif.Design.snapped` rounds the geometry itself -- onto any
        grid, not only powers of ten -- and every writer then agrees.

    Returns
    -------
    pathlib.Path
        The file that was written.
    """
    target = pathlib.Path(path)
    chosen = _format_for(target, fmt)
    round_to = _rounder(precision)
    rows = [(round_to(x), round_to(y)) for x, y in points]

    match chosen:
        case "csv":
            with target.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(("x", "y"))
                writer.writerows(rows)
        case "txt":
            target.write_text("".join(f"{x}\t{y}\n" for x, y in rows))
        case "json":
            target.write_text(json.dumps([[x, y] for x, y in rows]) + "\n")
    return target


def save_design(
    design: Design,
    path: str | PathLike[str],
    *,
    fmt: PointFormat | None = None,
    precision: int | None = None,
    meta: bool = True,
) -> pathlib.Path:
    """Write a design, strokes kept apart, and return the path written.

    Parameters
    ----------
    design : Design
        What to write.
    path : str or path-like
        Destination file.
    fmt : {"csv", "txt", "json"}, optional
        Output format, inferred from the suffix when omitted.

        * ``csv``  -- a ``path,x,y`` header, then one row per point carrying
          the index of the stroke it belongs to. A design's loose points
          belong to no stroke, so their ``path`` cell is left empty.
        * ``txt``  -- one tab-separated ``x<TAB>y`` line per point, with a
          blank line between strokes: the convention gnuplot and most plotter
          toolchains already understand as "lift the pen here".
        * ``json`` -- the structured form, and the only one
          :func:`load_design` reads back.
    precision : int, optional
        Round coordinates to this many decimal places, as for
        :func:`save_points`.
    meta : bool, optional
        Record the design's recipe alongside its points, for the JSON format
        only. Turn it off for a design whose motif takes a parameter that
        cannot be written as data.

    Returns
    -------
    pathlib.Path
        The file that was written.

    Raises
    ------
    TypeError
        If ``meta`` is requested and a parameter is not JSON data. The message
        names the parameter; passing ``meta=False`` writes the points anyway.
    """
    target = pathlib.Path(path)
    chosen = _format_for(target, fmt)
    round_to = _rounder(precision)

    def pairs(points: Iterable[Point]) -> list[list[float | int]]:
        return [[round_to(x), round_to(y)] for x, y in points]

    match chosen:
        case "csv":
            with target.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(("path", "x", "y"))
                for index, stroke in enumerate(design.paths):
                    writer.writerows((index, x, y) for x, y in pairs(stroke.points))
                writer.writerows(("", x, y) for x, y in pairs(design.points))
        case "txt":
            blocks = [pairs(stroke.points) for stroke in design.paths]
            if design.points:
                blocks.append(pairs(design.points))
            target.write_text(
                "\n".join("".join(f"{x}\t{y}\n" for x, y in block) for block in blocks)
            )
        case "json":
            # Imported at call time, not module scope: this module is part of
            # the package whose version it stamps, so the two would cycle.
            from .. import __version__

            blob: dict[str, object] = {
                VERSION_KEY: __version__,
                "paths": [
                    {"points": pairs(stroke.points), "closed": stroke.closed}
                    for stroke in design.paths
                ],
                "points": pairs(design.points),
            }
            if meta and design.meta:
                # The file already stamps its own version; a second copy inside
                # the recipe would only give the two a chance to disagree.
                blob["meta"] = {k: v for k, v in to_spec(design).items() if k != VERSION_KEY}
            target.write_text(json.dumps(blob) + "\n")
    return target


def load_design(path: str | PathLike[str]) -> Design:
    """Read a design back from a JSON file written by :func:`save_design`.

    A plain JSON array of pairs -- what :func:`save_points` writes -- also
    loads, as a design of loose points with no strokes. The two shapes are an
    array and an object, so there is nothing to guess at.

    Returns
    -------
    Design
        With ``meta`` restored where the file recorded it. The metadata is
        decoded but the motif is *not* rebuilt, so a design saved by a plugin
        still loads on a machine that does not have that plugin installed.

    Raises
    ------
    ValueError
        If the file is not one of the two shapes above.
    """
    data = json.loads(pathlib.Path(path).read_text())
    match data:
        case list():
            return Design(points=_points(data, where="the file"))
        case {"paths": _} | {"points": _}:
            strokes = enumerate(data.get("paths", []))
            return Design(
                paths=tuple(_path(entry, index) for index, entry in strokes),
                points=_points(data.get("points", []), where="points"),
                meta=(
                    _meta_from_spec(data["meta"])
                    if isinstance(data.get("meta"), dict)
                    else EMPTY_META
                ),
            )
        case _:
            raise ValueError(
                f"{path} is not a design file: expected a JSON array of [x, y] pairs, or "
                f"an object with 'paths' and 'points' keys, got {type(data).__name__}"
            )


def _format_for(target: pathlib.Path, fmt: PointFormat | None) -> PointFormat:
    """Return the format to write, inferring it from the file suffix if need be."""
    known = sorted(set(_SUFFIX_FORMATS.values()))
    if fmt is not None:
        if fmt not in _SUFFIX_FORMATS.values():
            raise ValueError(f"unknown format {fmt!r}; expected one of {known}")
        return fmt
    suffix = target.suffix.lower()
    if suffix not in _SUFFIX_FORMATS:
        raise ValueError(f"cannot infer format from suffix {suffix!r}; pass fmt= one of {known}")
    return _SUFFIX_FORMATS[suffix]


def _rounder(precision: int | None) -> Callable[[float], float | int]:
    """Return the coordinate formatter for a given precision.

    Zero and below come back as :class:`int`, so a whole number is written as
    ``3`` rather than ``3.0``: the file is smaller, and a reader that wants
    integers gets them rather than having to strip the tails itself.
    """
    if precision is None:
        return lambda value: value

    def coord(value: float) -> float | int:
        rounded = round(value, precision)
        return int(rounded) if precision <= 0 else rounded

    return coord


def _path(entry: object, index: int) -> Path:
    """Rebuild one stroke from its JSON object."""
    if not isinstance(entry, dict) or "points" not in entry:
        raise ValueError(f"paths[{index}] must be an object with a 'points' key, got {entry!r}")
    return Path(
        points=_points(entry["points"], where=f"paths[{index}]"),
        closed=bool(entry.get("closed", False)),
    )


def _points(value: object, where: str) -> tuple[Point, ...]:
    """Coerce a JSON array of pairs into points, blaming ``where`` if it is not one."""
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array of [x, y] pairs, got {type(value).__name__}")
    pairs: list[Point] = []
    for index, item in enumerate(value):
        if not (isinstance(item, list) and len(item) == 2):
            raise ValueError(f"{where}[{index}] must be an [x, y] pair, got {item!r}")
        pairs.append((float(item[0]), float(item[1])))
    return tuple(pairs)
