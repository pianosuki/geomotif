"""Export generated points to plain-text files (CSV, TXT/TSV, JSON).

Useful for feeding the coordinates into other tools -- editors, game map
formats, plotters, spreadsheets -- without writing any glue code.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

    from .core.types import Point

__all__ = ["PointFormat", "save_points"]

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
) -> Path:
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
        Round coordinates to this many decimal places; ``0`` (or negative)
        writes whole integers. Default keeps full float precision.

    Returns
    -------
    pathlib.Path
        The file that was written.
    """
    target = Path(path)
    if fmt is None:
        suffix = target.suffix.lower()
        if suffix not in _SUFFIX_FORMATS:
            raise ValueError(
                f"cannot infer format from suffix {suffix!r}; "
                f"pass fmt= one of {sorted(set(_SUFFIX_FORMATS.values()))}"
            )
        fmt = _SUFFIX_FORMATS[suffix]

    def coord(value: float) -> float | int:
        if precision is None:
            return value
        rounded = round(value, precision)
        return int(rounded) if precision <= 0 else rounded

    rows = [(coord(x), coord(y)) for x, y in points]

    match fmt:
        case "csv":
            with target.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(("x", "y"))
                writer.writerows(rows)
        case "txt":
            target.write_text("".join(f"{x}\t{y}\n" for x, y in rows))
        case "json":
            target.write_text(json.dumps([[x, y] for x, y in rows]) + "\n")
        case _:
            raise ValueError(f"unknown format {fmt!r}")
    return target
