"""Small geometry helpers shared between motif families.

Private on purpose: these are implementation details of the catalogue rather
than API. A motif family that needs one imports it; nothing outside
:mod:`geomotif.motifs` should.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import Point

__all__ = ["arc_points", "arc_segments", "ring_points"]

#: Segments per full revolution for an arc drawn as part of a larger outline.
#: Matches the density :func:`~geomotif.samples_for_turns` uses per turn, but
#: without its floor: that floor exists so a whole curve is measured finely
#: enough, and applying it to a single rounded corner would spend five hundred
#: points on a fillet.
_SEGMENTS_PER_TURN = 256


def arc_segments(sweep: float) -> int:
    """Return a sensible segment count for an arc spanning ``sweep`` radians."""
    return max(2, math.ceil(abs(sweep) / math.tau * _SEGMENTS_PER_TURN))


def arc_points(
    center: Point,
    radius: float,
    start_angle: float,
    sweep: float,
    *,
    segments: int | None = None,
) -> tuple[Point, ...]:
    """Return points along a circular arc, inclusive of both ends.

    Parameters
    ----------
    center : (float, float)
        Point the arc is drawn around.
    radius : float
        Arc radius. Zero collapses the arc to its center, which is what a
        rounded rectangle with no corner radius should do.
    start_angle : float
        Angle of the first point, in radians.
    sweep : float
        Angular extent, in radians. Negative sweeps run clockwise.
    segments : int, optional
        Number of segments. Defaults to a density proportional to ``sweep``.

    Returns
    -------
    tuple of (float, float)
        ``segments + 1`` points, so arcs joined end to end meet exactly.
    """
    count = arc_segments(sweep) if segments is None else segments
    cx, cy = center
    return tuple(
        (
            cx + radius * math.cos(start_angle + sweep * (i / count)),
            cy + radius * math.sin(start_angle + sweep * (i / count)),
        )
        for i in range(count + 1)
    )


def ring_points(
    count: int,
    radius: float,
    *,
    center: Point = (0.0, 0.0),
    rotation: float = 0.0,
) -> tuple[Point, ...]:
    """Return ``count`` points spaced evenly around a circle.

    The first point sits at angle ``rotation``, so ``rotation=0`` puts a
    vertex on the positive x-axis and ``rotation=pi/2`` puts one at the top --
    which is how a polygon is usually wanted on screen.
    """
    cx, cy = center
    step = math.tau / count
    return tuple(
        (cx + radius * math.cos(rotation + i * step), cy + radius * math.sin(rotation + i * step))
        for i in range(count)
    )
