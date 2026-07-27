"""Core spiral point generation.

Angles follow the standard math convention (counter-clockwise positive with
the y-axis pointing up). For coordinate systems where the y-axis points
down (screen/raster style), pass ``y_down=True`` so the ``clockwise`` flag
matches the direction you actually see.

Points are positioned by **arc length** by default: the spacing curve maps
each point to a fraction of the spiral's actual length on the x,y plane, so
``LinearSpacing`` yields the same real distance between every consecutive
pair of points no matter how the radius changes. Pass ``arc_length=False``
for the simpler parametric behavior (equal steps of angle/radius progress),
where spacing compresses as the path tightens toward the center.
"""

from __future__ import annotations

import bisect
import itertools
import math
from typing import TYPE_CHECKING

from .curves import LinearSpacing

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["Point", "generate_spiral"]

type Point = tuple[float, float]

# Density of the polyline used to measure arc length: enough for sub-pixel
# accuracy at typical canvas scales without noticeable cost.
_MIN_SAMPLES = 512
_SAMPLES_PER_TURN = 256


def generate_spiral(
    start: Point,
    end: Point,
    num_points: int,
    *,
    center: Point = (0, 0),
    clockwise: bool = True,
    y_down: bool = False,
    turns: int = 0,
    spacing: Callable[[float], float] | None = None,
    arc_length: bool = True,
) -> list[Point]:
    """Return ``num_points`` (x, y) tuples along a spiral from start to end.

    Parameters
    ----------
    start : (float, float)
        First point of the spiral (always included in the output).
    end : (float, float)
        Last point of the spiral (always included in the output).
    num_points : int
        Total number of points to return, inclusive of start and end.
        Must be >= 2.
    center : (float, float), optional
        Point the spiral winds around. Default ``(0, 0)``.
    clockwise : bool, optional
        Rotational direction of the sweep. Default ``True``. Interpreted in
        y-up coordinates unless ``y_down=True``.
    y_down : bool, optional
        Set ``True`` when your coordinate system's y-axis points down
        (screen/raster style) so ``clockwise`` matches the on-screen
        direction. Default ``False`` (math convention, y-up).
    turns : int, optional
        Extra full revolutions to add beyond the direct angular sweep from
        start to end. ``0`` (default) takes the shortest sweep in the chosen
        direction.
    spacing : SpacingCurve, optional
        Controls the distribution of points along the path. Defaults to
        :class:`~geomotif.curves.LinearSpacing` (equal spacing). Any
        callable mapping [0, 1] -> [0, 1] also works.
    arc_length : bool, optional
        When ``True`` (default), spacing fractions are measured in real
        distance along the curve, so equal spacing means equal x,y distance
        between consecutive points everywhere on the spiral. When ``False``,
        fractions apply to the angle/radius sweep parameter instead, which
        visually compresses spacing wherever the path tightens.

    Returns
    -------
    list[tuple[float, float]]
        The generated points, ready to plot.
    """
    if num_points < 2:
        raise ValueError(f"num_points must be >= 2, got {num_points}")
    if turns < 0:
        raise ValueError(f"turns must be >= 0, got {turns}")
    if spacing is None:
        spacing = LinearSpacing()
    elif not callable(spacing):
        raise TypeError("spacing must be a SpacingCurve (or any callable)")

    cx, cy = center
    r0 = math.dist(start, center)
    r1 = math.dist(end, center)

    # A point sitting exactly on the center has no defined angle; borrow the
    # other endpoint's angle so the path degenerates gracefully to a radial
    # line instead of an arbitrary jump.
    match r0 > 0, r1 > 0:
        case True, True:
            a0 = math.atan2(start[1] - cy, start[0] - cx)
            a1 = math.atan2(end[1] - cy, end[0] - cx)
        case True, False:
            a0 = a1 = math.atan2(start[1] - cy, start[0] - cx)
        case False, True:
            a0 = a1 = math.atan2(end[1] - cy, end[0] - cx)
        case _:
            a0 = a1 = 0.0

    # In y-down coordinates a negative (math-clockwise) sweep appears
    # counter-clockwise on screen, so flip the requested direction.
    if y_down:
        clockwise = not clockwise

    two_pi = 2.0 * math.pi
    if clockwise:
        sweep = -((a0 - a1) % two_pi) - two_pi * turns
    else:
        sweep = ((a1 - a0) % two_pi) + two_pi * turns

    def position(u: float) -> Point:
        angle = a0 + sweep * u
        radius = r0 + (r1 - r0) * u
        return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

    last = num_points - 1
    fractions = [spacing(i / last) for i in range(num_points)]

    if not arc_length:
        return [position(s) for s in fractions]

    # Measure the curve with a dense polyline, then invert the cumulative
    # length so each spacing fraction lands at that fraction of the real
    # path length.
    segments = max(_MIN_SAMPLES, int(_SAMPLES_PER_TURN * (abs(sweep) / two_pi + 1)))
    samples = [position(j / segments) for j in range(segments + 1)]
    cumulative = [0.0]
    for a, b in itertools.pairwise(samples):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    total = cumulative[-1]

    if total == 0.0:
        # start == end with no sweep: every point is the same place.
        return [samples[0]] * num_points

    points: list[Point] = []
    for s in fractions:
        target = s * total
        j = bisect.bisect_left(cumulative, target)
        if j <= 0:
            u = 0.0
        elif j > segments:
            u = 1.0
        else:
            seg_len = cumulative[j] - cumulative[j - 1]
            frac = 0.0 if seg_len == 0.0 else (target - cumulative[j - 1]) / seg_len
            u = (j - 1 + frac) / segments
        points.append(position(u))
    return points
