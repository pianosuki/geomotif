"""String art: straight lines only, and a curve appears anyway.

Nails in a board, thread between them, and the thing you end up looking at is
not any of the threads. The curve is their *envelope* -- the line every thread
is tangent to -- and it is a real curve with a real equation that no thread
ever lies along. A corner strung this way produces a parabola; a circle
strung with the two times table produces a cardioid.

Four ways in, from the most specific to the most general:

* :class:`StringArtCorner` -- two arms and a parabola between them, which is
  the one everybody has made.
* :class:`StringArtPolygon` -- that corner, at every corner of a polygon.
* ``StringArtCircle`` -- nails around a circle joined by a times table. This
  is :class:`~geomotif.motifs.graphs.ModularMultiplication` under the name a
  string artist would look for it under; the geometry is identical, so it is
  re-exported here rather than reimplemented.
* :class:`StringArtEnvelope` -- point ``i`` on one curve to point ``rule(i)``
  on another, for any curves and any rule. The other three are special cases.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..bases import SegmentMotif
from ..core.registry import register
from ._common import ring_points
from .graphs import ModularMultiplication

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "StringArtCircle",
    "StringArtCorner",
    "StringArtEnvelope",
    "StringArtPolygon",
]

#: Nails around a circle of this radius, for :class:`StringArtEnvelope`'s
#: default curve. A concrete size rather than a unit one, so the default
#: instance is something you can plot without scaling it first.
_DEFAULT_RADIUS = 120.0


def _lerp(a: Point, b: Point, t: float) -> Point:
    """Return the point ``t`` of the way from ``a`` to ``b``."""
    (ax, ay), (bx, by) = a, b
    return (ax + (bx - ax) * t, ay + (by - ay) * t)


def _ring(t: float) -> Point:
    """Return the point at fraction ``t`` around the default circle."""
    angle = math.tau * t
    return (_DEFAULT_RADIUS * math.cos(angle), _DEFAULT_RADIUS * math.sin(angle))


def _frame(t: float) -> Point:
    """Return the point at fraction ``t`` around the square the circle fits in.

    Parameterized by fraction of the *perimeter* rather than by angle, so the
    nails are evenly spaced along the sides. Lacing this against
    :func:`_ring` is what the default instance does, since two different
    curves is the case that needs a general engine at all.
    """
    side, along = divmod((t % 1.0) * 4.0, 1.0)
    r = _DEFAULT_RADIUS
    reach = r - 2.0 * r * along
    return ((-reach, -r), (r, -reach), (reach, r), (-r, reach))[int(side)]


def _doubled(i: int) -> int:
    """Return twice ``i``: the two times table, which is the classic lacing."""
    return 2 * i


@register("string-art.corner", family="string-art")
@dataclass(frozen=True, slots=True)
class StringArtCorner(SegmentMotif):
    """Two arms, laced so the far end of one meets the near end of the other.

    The first piece of string art anybody makes, and the reason the whole
    family is interesting: every thread is straight, and the curve they hug is
    a parabola -- specifically the one tangent to both arms. It is exactly
    tangent to each thread at one point and touches nothing else, which is
    what an envelope is.

    Parameters
    ----------
    count : int, optional
        Nails per arm, not counting the corner itself. More threads means a
        smoother-looking parabola and no change at all to the parabola.
    corner : (float, float), optional
        Where the two arms meet.
    arm_a, arm_b : (float, float), optional
        The far end of each arm. They need not be the same length or at a
        right angle -- an oblique corner still gives a parabola, just a
        skewed one.
    """

    count: int = 20
    corner: Point = (0.0, 0.0)
    arm_a: Point = (200.0, 0.0)
    arm_b: Point = (0.0, 200.0)

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.arm_a == self.corner or self.arm_b == self.corner:
            raise ValueError(
                f"{type(self).__name__}: an arm ends where it starts, so it has no "
                f"length to put nails along"
            )

    @override
    def nodes(self) -> Sequence[Point]:
        steps = [i / self.count for i in range(self.count + 1)]
        return [
            *(_lerp(self.corner, self.arm_a, t) for t in steps),
            *(_lerp(self.corner, self.arm_b, t) for t in steps),
        ]

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        # Nail i out along one arm pairs with nail count-i out along the other,
        # so the two distances from the corner always add to the same total --
        # that constant sum is what makes the envelope a parabola.
        span = self.count + 1
        return ((i, span + self.count - i) for i in range(span))


@register("string-art.polygon", family="string-art")
@dataclass(frozen=True, slots=True)
class StringArtPolygon(SegmentMotif):
    """A strung corner at every corner of a regular polygon.

    Each edge carries nails, and each corner's two edges are laced against
    each other, so the finished piece is a ring of parabolic arcs meeting at
    the vertices. Three sides gives the classic triangle; raise the count and
    it converges on a flower.

    Parameters
    ----------
    sides : int, optional
        Corners of the underlying polygon.
    count : int, optional
        Nails along each edge, not counting its endpoints.
    radius : float, optional
        Distance from the middle to each corner.
    rotation : float, optional
        Angle of the first corner, in radians. A quarter turn puts it at the
        top.
    center : (float, float), optional
        Middle of the polygon.
    """

    sides: int = 5
    count: int = 16
    radius: float = 130.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.sides < 3:
            raise ValueError(f"sides must be >= 3, got {self.sides}")
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.radius <= 0.0:
            raise ValueError(f"radius must be > 0, got {self.radius}")

    @override
    def nodes(self) -> Sequence[Point]:
        corners = ring_points(self.sides, self.radius, center=self.center, rotation=self.rotation)
        return [
            _lerp(corners[e], corners[(e + 1) % self.sides], i / self.count)
            for e in range(self.sides)
            for i in range(self.count + 1)
        ]

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        span = self.count + 1
        # Corner e is the far end of edge e-1 and the near end of edge e, so
        # nail i counted along each of them sits `count - i` and `i` steps from
        # it. Those two distances always add up to a whole side, which is the
        # corner construction said in indices.
        return (
            ((e - 1) % self.sides * span + i, e * span + i)
            for e in range(self.sides)
            for i in range(span)
        )


@register("string-art.envelope", family="string-art")
@dataclass(frozen=True, slots=True)
class StringArtEnvelope(SegmentMotif):
    """The general engine: nail ``i`` on one curve, to nail ``rule(i)`` on another.

    Every other motif in this module and the whole of
    :mod:`geomotif.motifs.graphs` is this with the curves and the rule filled
    in. Supply your own and see what the threads hug::

        StringArtEnvelope(
            count=240,
            rule=lambda i: 3 * i,
            curve=lambda t: (150 * math.cos(math.tau * t), 150 * math.sin(math.tau * t)),
        )

    Leaving ``partner`` unset strings the curve against itself, which is the
    usual case; setting it laces two different curves together -- a circle to
    a square, an ellipse to a line. The default does the latter, because two
    different curves is the case that needs a general engine at all: one
    circle laced to itself already has a name, and it is
    :class:`~geomotif.motifs.graphs.ModularMultiplication`.

    Parameters
    ----------
    count : int, optional
        Nails on each curve.
    rule : callable, optional
        Maps a nail index to the index it is strung to. Taken modulo
        ``count``, so it may return anything.
    curve : callable, optional
        Maps a fraction of the way round, in ``[0, 1)``, to a point.
    partner : callable, optional
        A second curve for the far end of each thread. ``None`` strings
        ``curve`` against itself.

    Notes
    -----
    The design records the function objects in its metadata, so it round-trips
    within a session but not through a file. Anything that has to survive
    being written down wants a registered class of its own.
    """

    count: int = 144
    rule: Callable[[int], int] = field(default=_doubled)
    curve: Callable[[float], Point] = field(default=_ring)
    partner: Callable[[float], Point] | None = field(default=_frame)

    def __post_init__(self) -> None:
        if self.count < 2:
            raise ValueError(f"count must be >= 2, got {self.count}")

    @override
    def nodes(self) -> Sequence[Point]:
        first = [self.curve(i / self.count) for i in range(self.count)]
        if self.partner is None:
            return first
        return [*first, *(self.partner(i / self.count) for i in range(self.count))]

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        # Strung against itself the two ends index into one set of nails, so a
        # rule that maps a nail to itself becomes a self-loop and SegmentMotif
        # drops it. Against a partner they are two sets, and the offset moves
        # the far end into the second.
        offset = 0 if self.partner is None else self.count
        return ((i, offset + self.rule(i) % self.count) for i in range(self.count))


#: Circle string art under the name a string artist looks for it under. The
#: times table drawn as chords and a circle strung with thread are the same
#: construction, so this is one class with two names rather than two classes
#: with one picture -- see :class:`~geomotif.motifs.graphs.ModularMultiplication`.
StringArtCircle = ModularMultiplication
