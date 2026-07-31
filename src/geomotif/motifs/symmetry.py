"""Point sets defined by a symmetry group and a rule about their distances.

Every other motif in this catalogue says where its points *are*. This one says
what has to be **true** of them -- that they fall into the orbits of a cyclic or
dihedral group, and that neighbouring points sit the same distance apart -- and
then solves for an arrangement that satisfies it.

The question it exists to answer is the one that sounds trivial and is not:
*fifteen points, five-fold symmetry, every neighbour the same distance from the
last.* Fifteen is not a multiple of ten, so the dihedral group ``D5`` cannot
build it out of generic ten-point orbits alone; it needs one of those and one
five-point orbit sitting on the mirror lines. Which orbits are available, and
which counts they can add up to, is arithmetic the motif does for you --
:class:`SymmetricPointSet` refuses a count it cannot arrange and names the
nearest two it can.

Symmetry is preserved **by construction** rather than by the solver: relaxation
moves one representative point per orbit, and the group carries the rest along.
No amount of iteration can drift the figure off its own symmetry, and the result
is exactly reproducible without a random seed anywhere.

.. warning::

    This module is **experimental** -- the one place in the library where a
    motif is solved for rather than evaluated. Its parameters and its output
    may change in a minor release; see the API policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from typing import TYPE_CHECKING, Literal, override

from ..bases import SegmentMotif
from ..core.registry import register

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = ["Connection", "SymmetricPointSet"]

#: How the points are joined once they have been placed.
type Connection = Literal["none", "nearest", "equal-distance", "all-pairs"]

#: What each orbit is free to move along. A ring orbit sits at a general
#: position and may slide both outward and around; an axis orbit is pinned to a
#: mirror line and may only slide outward, since leaving the line would break
#: the very symmetry it was placed to satisfy; the centre cannot move at all.
type _Kind = Literal["centre", "ring", "axis"]

#: How far a relaxation step moves a representative, as a fraction of the
#: distance error it is correcting. Well under 1 so that neighbours converge
#: together rather than overshooting each other turn about.
_RATE = 0.35

#: The furthest one iteration may move a representative, as a fraction of the
#: target distance. Small enough that neighbours cannot swap places between
#: steps, which is what turns a relaxation into an oscillation.
_MAX_STEP = 0.25

#: How far away a neighbour can be and still pull, as a multiple of the target
#: distance. Past it a pair is not neighbouring at all, and treating it as one
#: would make every figure contract without limit -- see :func:`_force`.
_REACH = 1.5

#: How close a ring orbit may drift to a mirror line, as a fraction of the
#: sector it lives in. On the line its points would coincide in pairs and the
#: distances between them would go to zero.
_AXIS_MARGIN = 0.02


@register(
    "symmetry.point-set",
    family="symmetry",
    example={"count": 15, "group": "D5", "connect": "equal-distance"},
)
@dataclass(frozen=True, slots=True)
class SymmetricPointSet(SegmentMotif):
    """Points arranged by a symmetry group, spaced by iterative relaxation.

    The points are laid out in **orbits** -- sets the group carries onto
    themselves. Under ``Cn`` an orbit holds ``n`` points; under ``Dn`` a
    general orbit holds ``2n`` and one sitting on the mirror lines holds
    ``n``. A single point at the centre is fixed by either group, so a count
    that is one more than a multiple of ``n`` gets one.

    That is the whole constraint on ``count``: it must be a multiple of the
    group's order, or one more than one. Anything else cannot be arranged
    symmetrically at all, and is refused with the nearest two counts that can.

    Relaxation then equalizes the distances. Each orbit contributes one
    representative point, which is pushed away from neighbours closer than the
    mean nearest-neighbour distance and pulled toward those further away; the
    group replicates whatever it does. Because only representatives move, the
    figure cannot drift off its symmetry, and no random numbers are involved
    anywhere -- the same parameters always give the same points.

    Parameters
    ----------
    count : int, optional
        How many points to place.
    group : str, optional
        ``"C5"`` for five-fold rotation, ``"D5"`` for five-fold rotation plus
        mirrors. Case-insensitive.
    radius : float, optional
        Radius of the outermost point. The relaxed figure is scaled to this,
        so it is a size rather than a constraint on the solution.
    relax : int, optional
        Relaxation iterations. Zero returns the seeded rings untouched, which
        is worth looking at to see what the relaxation is doing.
    connect : {"none", "nearest", "equal-distance", "all-pairs"}, optional
        What to draw between the points:

        * ``"none"`` -- nothing; the points are the design
        * ``"nearest"`` -- each point to its ``neighbors`` closest
        * ``"equal-distance"`` -- every pair the shortest distance apart,
          within ``tolerance``. This is the one the constraint is *for*: it
          draws exactly the edges the relaxation was equalizing
        * ``"all-pairs"`` -- the complete graph, which gets solid quickly
    neighbors : int, optional
        How many neighbours each point is relaxed against, and how many
        ``connect="nearest"`` joins it to.
    tolerance : float, optional
        How far above the shortest distance a pair may be and still count as
        equal, as a fraction of it. Relaxation converges rather than lands, so
        this is never zero.
    center : (float, float), optional
        Middle of the figure.

    Examples
    --------
    >>> design = SymmetricPointSet(count=15, group="D5").build()
    >>> len(design.points)
    15
    """

    count: int = 15
    group: str = "D5"
    radius: float = 120.0
    relax: int = 200
    connect: Connection = "equal-distance"
    neighbors: int = 3
    tolerance: float = 0.08
    center: Point = (0.0, 0.0)
    show_nodes: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        name = type(self).__name__
        order, _ = _parse_group(self.group, owner=name)
        if self.count < 1:
            raise ValueError(f"{name}: needs at least one point, got {self.count}")
        if self.count % order not in (0, 1):
            lower, upper = _nearest_counts(self.count, order)
            raise ValueError(
                f"{name}: {self.count} points cannot be arranged with {self.group} "
                f"symmetry. An orbit holds a multiple of {order} points, plus at most "
                f"one at the centre -- try {lower} or {upper}"
            )
        if self.radius <= 0.0:
            raise ValueError(f"{name}: radius must be > 0, got {self.radius}")
        if self.relax < 0:
            raise ValueError(f"{name}: relax must be >= 0, got {self.relax}")
        if self.neighbors < 1:
            raise ValueError(f"{name}: neighbors must be >= 1, got {self.neighbors}")
        if self.tolerance < 0.0:
            raise ValueError(f"{name}: tolerance must be >= 0, got {self.tolerance}")
        if self.connect == "none" and not self.show_nodes:
            raise ValueError(
                f"{name}: connect='none' draws no edges and show_nodes=False draws no "
                f"points, so there would be nothing in the design at all"
            )

    def orbit_sizes(self) -> tuple[int, ...]:
        """Return how many points each orbit holds, innermost first."""
        order, dihedral = _parse_group(self.group, owner=type(self).__name__)
        plan = _plan(self.count, order, dihedral=dihedral)
        return tuple(_size(kind, order, dihedral=dihedral) for kind in plan)

    @override
    def nodes(self) -> Sequence[Point]:
        order, dihedral = _parse_group(self.group, owner=type(self).__name__)
        return _placed(
            self.count,
            order,
            dihedral,
            self.radius,
            self.relax,
            self.neighbors,
            self.center,
        )

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        points = self.nodes()
        match self.connect:
            case "none":
                return ()
            case "all-pairs":
                return combinations(range(len(points)), 2)
            case "nearest":
                return [
                    (i, j)
                    for i in range(len(points))
                    for j, _ in _closest(points, i, self.neighbors)
                ]
            case "equal-distance":
                pairs = list(combinations(range(len(points)), 2))
                if not pairs:
                    return ()
                shortest = min(math.dist(points[i], points[j]) for i, j in pairs)
                limit = shortest * (1.0 + self.tolerance)
                return [(i, j) for i, j in pairs if math.dist(points[i], points[j]) <= limit]
            case _:
                raise ValueError(
                    f"{type(self).__name__}: connect must be 'none', 'nearest', "
                    f"'equal-distance' or 'all-pairs', got {self.connect!r}"
                )


# --- the group ---------------------------------------------------------------


def _parse_group(group: str, *, owner: str) -> tuple[int, bool]:
    """Return ``(order, dihedral)`` for a ``Cn``/``Dn`` name."""
    name = group.strip().upper()
    kind, order = name[:1], name[1:]
    if kind not in ("C", "D") or not order.isdigit() or int(order) < 1:
        raise ValueError(
            f"{owner}: group must look like 'C5' (rotation) or 'D5' (rotation and "
            f"mirrors), got {group!r}"
        )
    return int(order), kind == "D"


def _nearest_counts(count: int, order: int) -> tuple[int, int]:
    """Return the workable counts either side of one that is not."""
    below = count - 1
    while below > 1 and below % order not in (0, 1):
        below -= 1
    above = count + 1
    while above % order not in (0, 1):
        above += 1
    return below, above


def _plan(count: int, order: int, *, dihedral: bool) -> tuple[_Kind, ...]:
    """Return the orbits a count breaks into, innermost first.

    The centre goes first because it is innermost by definition. Under a
    dihedral group the general orbits are twice the size, so an odd number of
    ``order``-sized units leaves one over; that leftover becomes the orbit on
    the mirror lines, placed next to the centre where its smaller ring is
    least conspicuous. A cyclic group has no mirror lines to sit on, and every
    unit is simply a ring.
    """
    units = count // order
    kinds: list[_Kind] = ["centre"] if count % order == 1 else []
    if not dihedral:
        kinds.extend(["ring"] * units)
        return tuple(kinds)
    if units % 2 == 1:
        kinds.append("axis")
    kinds.extend(["ring"] * (units // 2))
    return tuple(kinds)


def _size(kind: _Kind, order: int, *, dihedral: bool) -> int:
    """Return how many points one orbit holds."""
    match kind:
        case "centre":
            return 1
        case "axis":
            return order
        case "ring":
            return 2 * order if dihedral else order


# --- placing and relaxing -----------------------------------------------------


@lru_cache(maxsize=16)
def _placed(
    count: int,
    order: int,
    dihedral: bool,
    radius: float,
    relax: int,
    neighbors: int,
    center: Point,
) -> tuple[Point, ...]:
    """Return the relaxed point set for one set of parameters.

    Cached because a :class:`SegmentMotif` asks for its nodes and its edges
    separately, and the edge rules need the distances between the very points
    the node call just solved for. The arguments are the whole of the input and
    the function is pure, so the cache can only ever hand back what a second
    run would have computed.
    """
    kinds = _plan(count, order, dihedral=dihedral)
    radii, angles = _seed(kinds, order, radius, dihedral=dihedral)
    for step in range(relax):
        _relax_once(radii, angles, kinds, order, dihedral, neighbors, step, relax, radius)
    # Scaled only now, at the end: relaxing at one size and drawing at another
    # would mean the last iteration solved a figure nobody sees.
    return _expand(_rescaled(radii, radius), angles, kinds, order, dihedral, center)


def _seed(
    kinds: Sequence[_Kind], order: int, radius: float, *, dihedral: bool
) -> tuple[list[float], list[float]]:
    """Return starting radii and angles: evenly spaced rings, alternately staggered.

    A stagger costs nothing and gives the relaxation a better place to start
    than a set of rings whose points all line up along the same spokes.
    """
    rings = [i for i, kind in enumerate(kinds) if kind != "centre"]
    radii = [0.0] * len(kinds)
    angles = [0.0] * len(kinds)
    sector = math.pi / order if dihedral else math.tau / order
    for place, index in enumerate(rings):
        radii[index] = radius * (place + 1) / len(rings)
        if kinds[index] == "ring":
            # Half a sector along, so a dihedral orbit starts as far from
            # either mirror line as it can, then staggered ring to ring.
            angles[index] = sector * (0.5 + 0.5 * (place % 2))
    return radii, angles


def _relax_once(
    radii: list[float],
    angles: list[float],
    kinds: Sequence[_Kind],
    order: int,
    dihedral: bool,
    neighbors: int,
    step: int,
    steps: int,
    limit: float,
) -> None:
    """Move every orbit's representative one step toward equal spacing, in place."""
    points = _expand(radii, angles, kinds, order, dihedral, (0.0, 0.0))
    if len(points) < 2:
        return
    target = _mean_nearest(points)
    if target == 0.0:
        return
    # Ease the step size off toward the end: large moves early to find the
    # arrangement, small ones late to settle into it rather than ring around it.
    rate = _RATE * (1.0 - step / steps)
    sector = math.pi / order if dihedral else math.tau / order
    first = 0
    for index, kind in enumerate(kinds):
        size = _size(kind, order, dihedral=dihedral)
        if kind != "centre":
            sx, sy = _capped(_force(points, first, neighbors, target), rate, target)
            cos, sin = math.cos(angles[index]), math.sin(angles[index])
            radii[index] = min(max(radii[index] + sx * cos + sy * sin, limit * 1e-3), limit)
            if kind == "ring":
                tangential = -sx * sin + sy * cos
                angles[index] += tangential / radii[index]
                angles[index] = _confined(angles[index], sector, dihedral=dihedral)
        first += size

    # Renormalize every step, not just at the end. The springs only ever see
    # distances, so shrinking the whole figure satisfies them exactly as well
    # as the arrangement it started from -- and with the outermost orbit
    # clamped at the limit, that shows up as the inner ones quietly collapsing
    # toward the middle. Pinning the scale removes the freedom to do it.
    radii[:] = _rescaled(radii, limit)


def _force(points: Sequence[Point], index: int, neighbors: int, target: float) -> Point:
    """Return the spring force on one point from the neighbours nearest it.

    Closer than ``target`` pushes apart, further pulls together, and the
    magnitude is the error itself -- so a point already at the right distance
    contributes nothing and a badly placed one dominates.

    A neighbour past :data:`_REACH` is ignored rather than pulled toward. Every
    point has a second and a third nearest neighbour further away than its
    first, and a spring on those would be a standing instruction to contract
    that no arrangement could ever satisfy -- the figure would collapse in on
    itself however well spaced it already was.
    """
    px, py = points[index]
    fx = fy = 0.0
    for j, distance in _closest(points, index, neighbors):
        if distance == 0.0 or distance > target * _REACH:
            continue
        push = (target - distance) / target
        qx, qy = points[j]
        fx += push * (px - qx) / distance * target
        fy += push * (py - qy) / distance * target
    return (fx, fy)


def _capped(force: Point, rate: float, target: float) -> Point:
    """Return the step a force takes, never longer than :data:`_MAX_STEP`.

    Several neighbours pulling the same way add up, and an orbit that has
    collapsed to a small radius turns even a modest sideways step into a large
    angle. Capping the step is what keeps the relaxation from throwing a
    representative across its own sector and having to be clamped back.
    """
    fx, fy = force
    length = math.hypot(fx, fy) * rate
    ceiling = _MAX_STEP * target
    if length <= ceiling or length == 0.0:
        return (fx * rate, fy * rate)
    return (fx * rate * ceiling / length, fy * rate * ceiling / length)


def _closest(points: Sequence[Point], index: int, count: int) -> list[tuple[int, float]]:
    """Return the ``count`` points nearest to ``index``, as ``(index, distance)``."""
    distances = [
        (j, math.dist(points[index], point)) for j, point in enumerate(points) if j != index
    ]
    distances.sort(key=lambda item: item[1])
    return distances[:count]


def _mean_nearest(points: Sequence[Point]) -> float:
    """Return the average distance from a point to its nearest neighbour."""
    nearest = [_closest(points, i, 1)[0][1] for i in range(len(points))]
    return math.fsum(nearest) / len(nearest)


def _confined(angle: float, sector: float, *, dihedral: bool) -> float:
    """Keep a ring orbit inside the wedge the group repeats.

    Under a dihedral group the wedge is bounded by two mirror lines, and an
    orbit that reaches one has its points coincide in pairs. Under a cyclic
    group there are no walls, so the angle simply wraps.
    """
    if not dihedral:
        return angle % sector
    margin = sector * _AXIS_MARGIN
    return min(max(angle, margin), sector - margin)


def _rescaled(radii: Sequence[float], radius: float) -> list[float]:
    """Return the radii scaled so the outermost orbit sits exactly at ``radius``."""
    widest = max(radii, default=0.0)
    if widest <= 0.0:
        return list(radii)
    return [r * radius / widest for r in radii]


def _expand(
    radii: Sequence[float],
    angles: Sequence[float],
    kinds: Sequence[_Kind],
    order: int,
    dihedral: bool,
    center: Point,
) -> tuple[Point, ...]:
    """Carry every representative around its orbit, in orbit order."""
    cx, cy = center
    step = math.tau / order
    points: list[Point] = []
    for index, kind in enumerate(kinds):
        if kind == "centre":
            points.append(center)
            continue
        r, angle = radii[index], angles[index]
        rotations = [angle + i * step for i in range(order)]
        if kind == "ring" and dihedral:
            rotations.extend(-angle + i * step for i in range(order))
        points.extend((cx + r * math.cos(a), cy + r * math.sin(a)) for a in rotations)
    return tuple(points)
