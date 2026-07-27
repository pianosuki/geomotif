"""Spiral motifs.

Angles follow the standard math convention: counter-clockwise positive, with
the y-axis pointing up. For a y-down (screen/raster) coordinate system, call
:meth:`~geomotif.Design.flipped_y` on the result rather than looking for a
flag here -- which way y points is a property of the target space, not of the
spiral.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.sampling import densify, samples_for_turns
from ..core.types import Design, Path

if TYPE_CHECKING:
    from ..core.types import Point

__all__ = ["SpiralBetween"]


@register(
    "spiral.between",
    family="spiral",
    example={"start": (100.0, 0.0), "end": (10.0, 0.0), "turns": 2},
)
@dataclass(frozen=True, slots=True)
class SpiralBetween(Motif):
    """The endpoint-constrained arithmetic spiral: ``r = a + b*theta``.

    Winds from ``start`` to ``end`` around ``center``, interpolating the
    radius linearly against a linearly interpolated angle. Both endpoints are
    hit exactly, which is what makes this the useful form when you know where
    the curve has to begin and end rather than what its growth rate should be.

    Parameters
    ----------
    start : (float, float)
        First point of the spiral.
    end : (float, float)
        Last point of the spiral.
    center : (float, float), optional
        Point the spiral winds around. Default ``(0, 0)``.
    clockwise : bool, optional
        Rotational direction of the sweep. Default ``True``.
    turns : int, optional
        Extra full revolutions beyond the direct angular sweep from start to
        end. ``0`` (default) takes the shortest sweep in the chosen direction.
    resolution : int, optional
        Number of segments used to measure the curve. Defaults to a density
        that scales with the number of turns, which is nearly always right.

    Examples
    --------
    ::

        SpiralBetween((200, 0), (20, 0), turns=3).generate(120)
    """

    start: Point
    end: Point
    center: Point = (0.0, 0.0)
    clockwise: bool = True
    turns: int = 0
    resolution: int | None = None

    def __post_init__(self) -> None:
        if self.turns < 0:
            raise ValueError(f"turns must be >= 0, got {self.turns}")
        if self.resolution is not None and self.resolution < 1:
            raise ValueError(f"resolution must be >= 1, got {self.resolution}")

    def _sweep(self) -> tuple[float, float, float, float]:
        """Return ``(r0, r1, a0, sweep)`` -- the spiral's polar description."""
        cx, cy = self.center
        r0 = math.dist(self.start, self.center)
        r1 = math.dist(self.end, self.center)

        # A point sitting exactly on the center has no defined angle; borrow
        # the other endpoint's angle so the path degenerates gracefully to a
        # radial line instead of an arbitrary jump.
        match r0 > 0, r1 > 0:
            case True, True:
                a0 = math.atan2(self.start[1] - cy, self.start[0] - cx)
                a1 = math.atan2(self.end[1] - cy, self.end[0] - cx)
            case True, False:
                a0 = a1 = math.atan2(self.start[1] - cy, self.start[0] - cx)
            case False, True:
                a0 = a1 = math.atan2(self.end[1] - cy, self.end[0] - cx)
            case _:
                a0 = a1 = 0.0

        if self.clockwise:
            sweep = -((a0 - a1) % math.tau) - math.tau * self.turns
        else:
            sweep = ((a1 - a0) % math.tau) + math.tau * self.turns
        return r0, r1, a0, sweep

    @override
    def build(self) -> Design:
        r0, r1, a0, sweep = self._sweep()
        cx, cy = self.center

        def position(u: float) -> Point:
            angle = a0 + sweep * u
            radius = r0 + (r1 - r0) * u
            return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

        samples = self.resolution or samples_for_turns(abs(sweep) / math.tau)
        return Design((Path(densify(position, samples=samples)),), meta=spec(self))
