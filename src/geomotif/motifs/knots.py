"""Celtic knotwork: strands that cross over and under and never end.

A knot drawing is a closed curve plus a decision at every crossing about which
strand is on top. This module keeps those two things apart. Each motif hands
:func:`_interlace` a set of closed loops; the interlacer finds where they
cross, works out the over-and-under, and draws the strand that goes underneath
with a gap in it. Nothing is filled and nothing is hidden, which is what a pen
plotter can actually draw and what the eye reads as weaving anyway.

Which strand goes over is not a free choice. Along one strand the crossings
must alternate over, under, over, under -- and at each crossing the two strands
must disagree. Written down, those are two kinds of "must differ", so the whole
question is a two-coloring, and it has a solution for a single closed curve
however tangled: between the two passes through any one crossing lies a closed
loop, and a closed loop meets the rest of the curve an even number of times, so
the two passes are always an odd number of crossings apart. What the interlacer
does is that argument, run as a breadth-first search.

Four figures and one engine. :class:`Triquetra` is three circles.
:class:`CircularCelticKnot` and :class:`SquareCelticKnot` are one strand wound
several times round a ring or a square frame. :class:`EndlessKnot` is the woven
grid whose ends are looped back so that the whole figure is a single strand.
:class:`CelticGrid` is the plait: strands set off at 45 degrees, bounce off the
frame, and bounce off whatever barriers you place inside it.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Design, Path
from ._common import arc_points, ring_points

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ..core.types import Point

__all__ = [
    "CelticGrid",
    "CircularCelticKnot",
    "EndlessKnot",
    "SquareCelticKnot",
    "Triquetra",
]

type Loop = tuple[Point, ...]

#: Ceiling on how many straight pieces one figure may be cut into. Crossing
#: detection is quadratic in the worst case, so a mistyped resolution should
#: raise rather than take a minute.
_MAX_SEGMENTS = 6000

_ROOT3 = math.sqrt(3.0)


def _check_gap(owner: str, gap: float) -> None:
    """Reject a break that would either not show or swallow the strand."""
    if not 0.0 < gap < 0.5:
        raise ValueError(
            f"{owner} gap is a fraction of the figure's size and must be "
            f"strictly between 0 and 0.5, got {gap}"
        )


def _rounded(corners: Sequence[Point], radius: float, *, steps: int = 5) -> Loop:
    """Return a closed polyline with its corners cut back into curves.

    Each corner is replaced by a quadratic Bezier whose control point is the
    corner itself, cut back by ``radius`` along both sides but never past the
    middle of either, so two corners on a short side cannot overrun each other.
    """
    count = len(corners)
    out: list[Point] = []
    for i, here in enumerate(corners):
        before, after = corners[i - 1], corners[(i + 1) % count]
        back = math.dist(before, here)
        ahead = math.dist(here, after)
        cut = min(radius, back / 2.0, ahead / 2.0)
        if cut == 0.0:
            out.append(here)  # nothing to round off; keep the corner sharp
            continue
        start = (
            here[0] + (before[0] - here[0]) * cut / back,
            here[1] + (before[1] - here[1]) * cut / back,
        )
        end = (
            here[0] + (after[0] - here[0]) * cut / ahead,
            here[1] + (after[1] - here[1]) * cut / ahead,
        )
        for step in range(steps + 1):
            t = step / steps
            u = 1.0 - t
            out.append(
                (
                    u * u * start[0] + 2.0 * u * t * here[0] + t * t * end[0],
                    u * u * start[1] + 2.0 * u * t * here[1] + t * t * end[1],
                )
            )
    return tuple(out)


def _pieces(loops: Sequence[Loop]) -> list[tuple[int, int, Point, Point]]:
    """Return every straight piece of every loop as ``(loop, index, start, end)``."""
    out: list[tuple[int, int, Point, Point]] = []
    for index, loop in enumerate(loops):
        for i, start in enumerate(loop):
            out.append((index, i, start, loop[(i + 1) % len(loop)]))
    if len(out) > _MAX_SEGMENTS:
        raise ValueError(
            f"knot would be cut into {len(out)} straight pieces (limit "
            f"{_MAX_SEGMENTS}); use a lower resolution or a smaller figure"
        )
    return out


def _crossings(loops: Sequence[Loop]) -> list[tuple[int, int, float, int, int, float]]:
    """Return where the loops cross, as a pair of positions along two strands.

    Pieces are visited in order of their leftmost end and compared only with
    those that start before this one's right-hand end, which keeps a knot made
    of many short pieces near linear rather than quadratic.
    """
    pieces = sorted(_pieces(loops), key=lambda p: min(p[2][0], p[3][0]))
    found: list[tuple[int, int, float, int, int, float]] = []
    for a, (loop_a, index_a, p0, p1) in enumerate(pieces):
        right = max(p0[0], p1[0])
        low_a, high_a = min(p0[1], p1[1]), max(p0[1], p1[1])
        for loop_b, index_b, q0, q1 in pieces[a + 1 :]:
            if min(q0[0], q1[0]) > right:
                break
            if min(q0[1], q1[1]) > high_a or max(q0[1], q1[1]) < low_a:
                continue
            if loop_a == loop_b:
                apart = (index_a - index_b) % len(loops[loop_a])
                if apart <= 1 or apart >= len(loops[loop_a]) - 1:
                    continue  # neighbours on one strand merely share a corner
            ux, uy = p1[0] - p0[0], p1[1] - p0[1]
            vx, vy = q1[0] - q0[0], q1[1] - q0[1]
            det = vx * uy - vy * ux
            if det == 0.0:
                continue
            rx, ry = q0[0] - p0[0], q0[1] - p0[1]
            here = (vx * ry - vy * rx) / det
            there = (ux * ry - uy * rx) / det
            if 1e-9 < here < 1.0 - 1e-9 and 1e-9 < there < 1.0 - 1e-9:
                found.append((loop_a, index_a, here, loop_b, index_b, there))
    return found


def _over_under(
    loops: Sequence[Loop],
    crossings: Sequence[tuple[int, int, float, int, int, float]],
) -> list[bool]:
    """Return, per crossing visit, whether that strand passes over.

    Two visits must differ if they are the two sides of one crossing, and two
    must differ if they are next to each other along a strand. Both are the
    same constraint, so the answer is a two-coloring, found by breadth-first
    search. A conflict can only arise where several strands are woven together
    in a way that admits no alternating diagram at all; the search keeps the
    color it first assigned and the crossing simply does not alternate.
    """
    visits: list[tuple[int, int, float]] = []
    neighbours: list[list[int]] = []
    for loop_a, index_a, here, loop_b, index_b, there in crossings:
        visits.append((loop_a, index_a, here))
        visits.append((loop_b, index_b, there))
        neighbours.append([len(visits) - 1])
        neighbours.append([len(visits) - 2])

    for index in range(len(loops)):
        along = sorted(
            (v for v, visit in enumerate(visits) if visit[0] == index),
            key=lambda v: visits[v][1:],
        )
        for first, second in zip(along, along[1:] + along[:1], strict=True):
            if first != second:
                neighbours[first].append(second)
                neighbours[second].append(first)

    color: list[bool | None] = [None] * len(visits)
    for start in range(len(visits)):
        if color[start] is not None:
            continue
        color[start] = True
        queue = [start]
        while queue:
            here = queue.pop()
            for other in neighbours[here]:
                if color[other] is None:
                    color[other] = not color[here]
                    queue.append(other)
    return [bool(c) for c in color]


def _walk(loop: Loop) -> tuple[list[float], float]:
    """Return the arc length reached at each corner, and the total."""
    reached = [0.0]
    for i in range(len(loop)):
        reached.append(reached[-1] + math.dist(loop[i], loop[(i + 1) % len(loop)]))
    return reached, reached[-1]


def _at(loop: Loop, reached: Sequence[float], where: float) -> Point:
    """Return the point a given distance along a closed loop."""
    i = min(bisect.bisect_right(reached, where) - 1, len(loop) - 1)
    span = reached[i + 1] - reached[i]
    t = 0.0 if span == 0.0 else (where - reached[i]) / span
    start, end = loop[i], loop[(i + 1) % len(loop)]
    return (start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1]))


def _break_at(loop: Loop, holes: Sequence[tuple[float, float]]) -> list[Loop]:
    """Return the loop cut into open strokes, with each hole left out."""
    reached, total = _walk(loop)
    merged: list[list[float]] = []
    for start, end in sorted(holes):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    runs: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            runs.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total:
        runs.append((cursor, total))

    strokes: list[Loop] = []
    for start, end in runs:
        points = [_at(loop, reached, start)]
        for i, corner in enumerate(loop):
            if start < reached[i] < end and math.dist(corner, points[-1]) > 1e-12:
                points.append(corner)
        last = _at(loop, reached, end)
        if math.dist(last, points[-1]) > 1e-12:
            points.append(last)
        if len(points) > 1:
            strokes.append(tuple(points))

    # A stroke that ran off the end and one that started at the beginning are
    # the same stroke: the seam is an artefact of where the loop's point list
    # happens to start, and leaving it would draw a break nobody asked for.
    if len(strokes) > 1 and runs[0][0] == 0.0 and runs[-1][1] == total:
        strokes[0] = strokes[-1][:-1] + strokes[0]
        strokes.pop()
    return strokes


def _interlace(loops: Sequence[Loop], gap: float) -> tuple[Path, ...]:
    """Return the loops drawn as knotwork, the under-strand broken at each crossing."""
    crossings = _crossings(loops)
    over = _over_under(loops, crossings)
    holes: list[list[tuple[float, float]]] = [[] for _ in loops]
    walks = [_walk(loop) for loop in loops]
    for visit, passes_over in enumerate(over):
        if passes_over:
            continue
        crossing = crossings[visit // 2]
        index, piece, t = crossing[:3] if visit % 2 == 0 else crossing[3:]
        reached, total = walks[index]
        at = reached[piece] + t * (reached[piece + 1] - reached[piece])
        holes[index].append((max(0.0, at - gap), min(total, at + gap)))

    paths: list[Path] = []
    for index, loop in enumerate(loops):
        if not holes[index]:
            paths.append(Path(loop, closed=True))
            continue
        paths.extend(Path(stroke) for stroke in _break_at(loop, holes[index]))
    return tuple(paths)


# --- three circles ----------------------------------------------------------


@register("knot.triquetra", family="knot")
@dataclass(frozen=True, slots=True)
class Triquetra(Motif):
    """The trinity knot: three arcs that turn out to be one strand.

    Three circles whose middles are one radius apart, each cut down to the
    half that faces the other two. Those three half-circles join end to end --
    the joins are where the circles meet on the far side -- so the figure is a
    single closed strand crossing itself three times, which is to say a
    trefoil, drawn the way it was drawn on stone crosses.

    Parameters
    ----------
    radius : float, optional
        Radius of each of the three circles.
    gap : float, optional
        Length of the break in the under-strand, as a fraction of the radius.
    rotation : float, optional
        Turn the figure, in radians. Defaults to one lobe pointing up.
    ring : bool, optional
        Draw the enclosing circle the knot is often set in, woven through the
        three lobes. It has the same radius as they do.
    center : (float, float), optional
        Middle of the figure.
    """

    radius: float = 90.0
    gap: float = 0.07
    rotation: float = -math.pi / 2.0
    ring: bool = field(default=False, kw_only=True)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.radius <= 0.0:
            raise ValueError(f"{owner} radius must be > 0, got {self.radius}")
        _check_gap(owner, self.gap)

    def centers(self) -> tuple[Point, ...]:
        """Return the three circle middles, one radius apart from each other."""
        return ring_points(3, self.radius / _ROOT3, center=self.center, rotation=self.rotation)

    def loops(self) -> tuple[Loop, ...]:
        """Return the closed curves the knot is woven from."""
        strand: list[Point] = []
        for i, middle in enumerate(self.centers()):
            facing = self.rotation + i * math.tau / 3.0
            # The half of this circle that faces the other two, run backwards
            # so that each arc ends where the next one starts.
            arc = arc_points(middle, self.radius, facing + 1.5 * math.pi, -math.pi)
            strand.extend(arc[:-1])
        loops = [tuple(strand)]
        if self.ring:
            loops.append(arc_points(self.center, self.radius, 0.0, math.tau)[:-1])
        return tuple(loops)

    @override
    def build(self) -> Design:
        return Design(_interlace(self.loops(), self.gap * self.radius), meta=spec(self))


# --- one strand round a frame -----------------------------------------------


def _wound(
    spine: Callable[[float], float],
    amplitude: float,
    lobes: int,
    wraps: int,
    steps: int,
    center: Point,
) -> Loop:
    """Return one strand wound ``wraps`` times round a spine, waving ``lobes`` times.

    The strand runs round the spine ``wraps`` times while the wave completes
    ``lobes`` cycles over the whole journey, so consecutive turns lie inside
    and outside each other by turns and cross where they trade places.

    Samples are taken a third of a step along rather than on the step itself.
    Every one of these crossings sits at a quarter-multiple of a step -- that
    is where the wave is halfway between its extremes -- and a third is never
    a quarter, so no crossing lands exactly on a corner of the polyline, where
    the interlacer could not see it.
    """
    cx, cy = center
    points: list[Point] = []
    for step in range(steps):
        u = (step + 1.0 / 3.0) / steps
        theta = math.tau * wraps * u
        radius = spine(theta) + amplitude * math.cos(math.tau * lobes * u)
        points.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
    return tuple(points)


def _check_winding(owner: str, lobes: int, wraps: int) -> None:
    """Reject a winding that would fall apart into separate loops."""
    if lobes < 2:
        raise ValueError(f"{owner} lobes must be >= 2, got {lobes}")
    if wraps < 1:
        raise ValueError(f"{owner} wraps must be >= 1, got {wraps}")
    shared = math.gcd(lobes, wraps)
    if shared != 1:
        raise ValueError(
            f"{owner} lobes {lobes} and wraps {wraps} share a factor of {shared}, so "
            f"the figure would close early and come out as {shared} separate loops "
            f"rather than one endless strand"
        )


@register("knot.circular", family="knot")
@dataclass(frozen=True, slots=True)
class CircularCelticKnot(Motif):
    """One strand wound several times round a ring, weaving with itself.

    The radius rises and falls as the strand goes round, and because it wraps
    more than once the turns swap places and cross. With ``wraps`` and
    ``lobes`` sharing no factor the whole thing is a single closed strand --
    the circular knot cut into stone crosses, and, read as a knot, a torus
    knot's standard diagram.

    Parameters
    ----------
    radius : float, optional
        Mean radius of the ring.
    amplitude : float, optional
        How far the strand wanders in and out.
    lobes : int, optional
        Cycles of that wandering over the whole journey.
    wraps : int, optional
        Times the strand goes round. Must share no factor with ``lobes``.
    resolution : int, optional
        Samples per lobe.
    gap : float, optional
        Length of the break in the under-strand, as a fraction of the radius.
    center : (float, float), optional
        Middle of the ring.
    """

    radius: float = 110.0
    amplitude: float = 34.0
    lobes: int = 5
    wraps: int = 2
    resolution: int = 48
    gap: float = 0.06
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.radius <= 0.0:
            raise ValueError(f"{owner} radius must be > 0, got {self.radius}")
        if not 0.0 < self.amplitude < self.radius:
            raise ValueError(
                f"{owner} amplitude must be > 0 and smaller than radius {self.radius}, "
                f"got {self.amplitude}"
            )
        if self.resolution < 8:
            raise ValueError(f"{owner} resolution must be >= 8, got {self.resolution}")
        _check_winding(owner, self.lobes, self.wraps)
        _check_gap(owner, self.gap)

    def loop(self) -> Loop:
        """Return the strand as one closed polyline, before it is broken."""
        return _wound(
            lambda _: self.radius,
            self.amplitude,
            self.lobes,
            self.wraps,
            self.resolution * self.lobes,
            self.center,
        )

    @override
    def build(self) -> Design:
        return Design(_interlace((self.loop(),), self.gap * self.radius), meta=spec(self))


@register("knot.square", family="knot")
@dataclass(frozen=True, slots=True)
class SquareCelticKnot(Motif):
    """The same winding, but round a square frame instead of a ring.

    The spine is a squircle, so the strand runs straight down each side and
    turns the corner without a kink -- the shape of a knotwork panel border.

    Parameters
    ----------
    size : float, optional
        Width of the frame, across the middle of the strand.
    amplitude : float, optional
        How far the strand wanders in and out.
    lobes : int, optional
        Cycles of that wandering over the whole journey.
    wraps : int, optional
        Times the strand goes round. Must share no factor with ``lobes``.
    squareness : float, optional
        How square the frame is: 2 is a circle, and higher is squarer.
    resolution : int, optional
        Samples per lobe.
    gap : float, optional
        Length of the break in the under-strand, as a fraction of the size.
    center : (float, float), optional
        Middle of the frame.
    """

    size: float = 220.0
    amplitude: float = 24.0
    lobes: int = 8
    wraps: int = 3
    squareness: float = 6.0
    resolution: int = 48
    gap: float = 0.035
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.size <= 0.0:
            raise ValueError(f"{owner} size must be > 0, got {self.size}")
        if not 0.0 < self.amplitude < self.size / 2.0:
            raise ValueError(
                f"{owner} amplitude must be > 0 and smaller than half the size "
                f"({self.size / 2.0}), got {self.amplitude}"
            )
        if self.squareness < 2.0:
            raise ValueError(
                f"{owner} squareness must be >= 2, got {self.squareness}; 2 is the "
                f"circle and anything below it is a pinched star"
            )
        if self.resolution < 8:
            raise ValueError(f"{owner} resolution must be >= 8, got {self.resolution}")
        _check_winding(owner, self.lobes, self.wraps)
        _check_gap(owner, self.gap)

    def spine(self, theta: float) -> float:
        """Return the frame's radius at ``theta``: a squircle, not a circle."""
        power = self.squareness
        # Typed out rather than written as one expression: ``x ** y`` on two
        # floats is Any to mypy, and the annotation is what says otherwise.
        reach: float = abs(math.cos(theta)) ** power + abs(math.sin(theta)) ** power
        shrink: float = reach ** (1.0 / power)
        return self.size / 2.0 / shrink

    def loop(self) -> Loop:
        """Return the strand as one closed polyline, before it is broken."""
        return _wound(
            self.spine,
            self.amplitude,
            self.lobes,
            self.wraps,
            self.resolution * self.lobes,
            self.center,
        )

    @override
    def build(self) -> Design:
        return Design(_interlace((self.loop(),), self.gap * self.size), meta=spec(self))


# --- the endless knot -------------------------------------------------------

#: Which end of which strand joins which, at each of the four corners of the
#: endless knot. ``L``/``R`` are the ends of the horizontal strands, numbered
#: from the top; ``T``/``B`` the ends of the verticals, numbered from the left.
#: Three corners nest their loops one inside the other and the fourth swaps
#: its pair over. Nesting all four would be prettier and would also split the
#: figure into two separate rings -- the swap is what makes it endless.
_ENDLESS_JOINS = (
    (("L", 0), ("T", 0)),
    (("L", 1), ("T", 1)),
    (("R", 0), ("T", 3)),
    (("R", 1), ("T", 2)),
    (("R", 2), ("B", 3)),
    (("R", 3), ("B", 2)),
    (("L", 2), ("B", 1)),
    (("L", 3), ("B", 0)),
)

#: How far each strand reaches past the middle of the weave, in units of the
#: strand spacing. The outer two run further so that their loops enclose the
#: inner two's rather than cutting through them.
_ENDLESS_REACH = (2.5, 2.0, 2.0, 2.5)


@register("knot.endless", family="knot")
@dataclass(frozen=True, slots=True)
class EndlessKnot(Motif):
    """The endless knot: four strands each way, woven, with their ends looped back.

    A plain over-and-under weave of four horizontal and four vertical strands,
    whose sixteen loose ends are joined in pairs round the four corners. The
    joining is what the name is about -- get it wrong and the figure falls into
    two closed rings; get it right and it is one strand with no beginning,
    which is the whole point of the symbol.

    Parameters
    ----------
    size : float, optional
        Width of the finished figure.
    roundness : float, optional
        How much the corners are curved, as a fraction of the strand spacing.
    gap : float, optional
        Length of the break in the under-strand, as a fraction of the size.
    center : (float, float), optional
        Middle of the figure.
    """

    size: float = 220.0
    roundness: float = 0.4
    gap: float = 0.02
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.size <= 0.0:
            raise ValueError(f"{owner} size must be > 0, got {self.size}")
        if not 0.0 <= self.roundness <= 1.0:
            raise ValueError(f"{owner} roundness must be in [0, 1], got {self.roundness}")
        _check_gap(owner, self.gap)

    def _end(self, which: tuple[str, int]) -> Point:
        side, index = which
        step = self.size / (2.0 * _ENDLESS_REACH[0])
        cx, cy = self.center
        reach = _ENDLESS_REACH[index] * step
        offset = (1.5 - index) * step
        match side:
            case "L":
                return (cx - reach, cy + offset)
            case "R":
                return (cx + reach, cy + offset)
            case "T":
                return (cx - offset, cy + reach)
            case _:
                return (cx - offset, cy - reach)

    def loop(self) -> Loop:
        """Return the single closed strand, corners rounded, before it is broken."""
        far: dict[tuple[str, int], tuple[str, int]] = {}
        for a, b in _ENDLESS_JOINS:
            far[a], far[b] = b, a
        opposite = {"L": "R", "R": "L", "T": "B", "B": "T"}
        across = {(side, i): (opposite[side], i) for side in "LRTB" for i in range(4)}

        start = ("L", 0)
        corners: list[Point] = []
        here = start
        while True:
            other = across[here]
            corners.append(self._end(here))
            corners.append(self._end(other))
            joined = far[other]
            # The elbow that carries one strand's end round to the next: it
            # sits at the corner of their two reaches.
            flat, upright = (other, joined) if other[0] in "LR" else (joined, other)
            corners.append((self._end(flat)[0], self._end(upright)[1]))
            here = joined
            if here == start:
                break
        step = self.size / (2.0 * _ENDLESS_REACH[0])
        return _rounded(tuple(corners), self.roundness * step)

    @override
    def build(self) -> Design:
        return Design(_interlace((self.loop(),), self.gap * self.size), meta=spec(self))


# --- the plait --------------------------------------------------------------


@register("knot.celtic-grid", family="knot")
@dataclass(frozen=True, slots=True)
class CelticGrid(Motif):
    """The plait: strands at 45 degrees, bouncing off the frame and off barriers.

    The construction every Celtic panel is built on. Strands set off diagonally
    across a grid of ``cols`` by ``rows`` cells and turn wherever they meet the
    frame; wherever they meet each other they weave. Place a barrier inside and
    the strands turn there too, which is how one plait becomes a thousand
    different knots -- the breaks are the design.

    Barriers sit on the half-cell grid, whose coordinates run from 0 to
    ``2 * cols`` across and 0 to ``2 * rows`` up. A barrier must be strictly
    inside and its two coordinates must add to an odd number, which is where
    the strands actually go.

    Parameters
    ----------
    cols, rows : int, optional
        Size of the panel, in cells.
    size : float, optional
        Side of one cell.
    breaks : tuple, optional
        Barriers, each ``(x, y, "h")`` to turn a strand back vertically or
        ``(x, y, "v")`` to turn it back horizontally.
    roundness : float, optional
        How much the turns are curved, as a fraction of the half-cell.
    gap : float, optional
        Length of the break in the under-strand, as a fraction of the cell.
    center : (float, float), optional
        Middle of the panel.
    """

    cols: int = 4
    rows: int = 3
    size: float = 60.0
    breaks: tuple[tuple[int, int, str], ...] = ()
    roundness: float = 0.55
    gap: float = 0.14
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.cols < 1 or self.rows < 1:
            raise ValueError(f"{owner} needs at least one cell, got {self.cols}x{self.rows}")
        if self.size <= 0.0:
            raise ValueError(f"{owner} size must be > 0, got {self.size}")
        if not 0.0 <= self.roundness <= 1.0:
            raise ValueError(f"{owner} roundness must be in [0, 1], got {self.roundness}")
        _check_gap(owner, self.gap)
        for barrier in self.breaks:
            x, y, kind = barrier
            if kind not in ("h", "v"):
                raise ValueError(f"{owner} break {barrier} must be turned 'h' or 'v'")
            if not (0 < x < 2 * self.cols and 0 < y < 2 * self.rows):
                raise ValueError(
                    f"{owner} break {barrier} is not strictly inside the "
                    f"{2 * self.cols}x{2 * self.rows} half-cell grid"
                )
            if (x + y) % 2 == 0:
                raise ValueError(
                    f"{owner} break {barrier} has coordinates adding to an even "
                    f"number, where no strand ever goes; use odd"
                )

    def _leaves(self, node: tuple[int, int], heading: tuple[int, int]) -> tuple[int, int]:
        """Return the direction a strand leaves ``node`` on, having arrived heading in."""
        (x, y), (dx, dy) = node, heading
        barrier = next((kind for bx, by, kind in self.breaks if (bx, by) == (x, y)), None)
        if (x == 0 and dx < 0) or (x == 2 * self.cols and dx > 0) or barrier == "v":
            dx = -dx
        if (y == 0 and dy < 0) or (y == 2 * self.rows and dy > 0) or barrier == "h":
            dy = -dy
        return (dx, dy)

    def turns(self) -> tuple[tuple[tuple[int, int], ...], ...]:
        """Return each strand as the grid nodes where it changes direction.

        Only the corners: between two of them the strand runs dead straight,
        so listing every node it passes through would add points a plotter
        would draw over anyway -- and would put a crossing exactly on a vertex,
        where it is far harder to find.

        The strands never reach the four corners of the frame, where they could
        only turn back on themselves: a corner's coordinates add to an even
        number, and every strand lives on the odd ones.
        """
        drawn: set[frozenset[tuple[int, int]]] = set()
        strands: list[tuple[tuple[int, int], ...]] = []
        for x in range(2 * self.cols + 1):
            for y in range(2 * self.rows + 1):
                if (x + y) % 2 == 0:
                    continue
                for arriving in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                    node = (x, y)
                    heading = self._leaves(node, arriving)
                    if frozenset((node, (x + heading[0], y + heading[1]))) in drawn:
                        continue
                    corners: list[tuple[int, int]] = []
                    while True:
                        step = (node[0] + heading[0], node[1] + heading[1])
                        if frozenset((node, step)) in drawn:
                            break
                        drawn.add(frozenset((node, step)))
                        onward = self._leaves(step, heading)
                        if onward != heading:
                            corners.append(step)
                        node, heading = step, onward
                    strands.append(tuple(corners))
        return tuple(strands)

    def loops(self) -> tuple[Loop, ...]:
        """Return the strands as closed polylines, corners rounded."""
        half = self.size / 2.0
        cx, cy = self.center
        x0 = cx - self.cols * self.size / 2.0
        y0 = cy - self.rows * self.size / 2.0
        return tuple(
            _rounded(
                tuple((x0 + x * half, y0 + y * half) for x, y in corners),
                self.roundness * half,
            )
            for corners in self.turns()
        )

    @override
    def build(self) -> Design:
        return Design(_interlace(self.loops(), self.gap * self.size), meta=spec(self))
