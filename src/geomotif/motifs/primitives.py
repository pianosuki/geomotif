"""The basic shapes: circles, polygons, stars, grids and point fields.

Unglamorous and load-bearing. These are what you compose with
:func:`~geomotif.radial_repeat` and :func:`~geomotif.tile`, what you clip
other motifs against, and what most designs are eventually made of.

Note which base each one uses. A circle is *measured* -- sampled at evenly
spaced angles, and the denser the sampling the rounder it gets. A polygon is
*listed* -- five corners are the shape, and sampling it at five hundred
parameters would only round its corners off. That is the difference between
:class:`~geomotif.ParametricMotif` and :class:`~geomotif.PolygonMotif`, and
it is why a pentagon here costs five points rather than five hundred.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import ParametricMotif, PolygonMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Design, Path
from ._common import arc_points, ring_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "Arc",
    "Circle",
    "Egg",
    "Ellipse",
    "Line",
    "PointGrid",
    "PoissonDiscPoints",
    "Rectangle",
    "RegularPolygon",
    "ReuleauxPolygon",
    "RoundedRectangle",
    "Sector",
    "Squircle",
    "Star",
    "StarPolygon",
    "Superellipse",
]

#: Vertex straight up. The default orientation for anything with corners,
#: because a pentagon pointing sideways looks like a mistake.
_UP = math.pi / 2.0

#: Ceiling on a generated point field, so a mistyped spacing raises instead
#: of exhausting memory. Far above any plausible design.
_MAX_POINTS = 200_000


@register("circle", family="primitive")
@dataclass(frozen=True, slots=True)
class Circle(ParametricMotif):
    """A circle of radius ``radius`` around ``center``.

    Parameters
    ----------
    radius : float, optional
        Distance from the center.
    center : (float, float), optional
        Point to draw around.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    radius: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        cx, cy = self.center
        return (cx + self.radius * math.cos(u), cy + self.radius * math.sin(u))


@register("ellipse", family="primitive")
@dataclass(frozen=True, slots=True)
class Ellipse(ParametricMotif):
    """An ellipse with semi-axes ``rx`` and ``ry``, optionally rotated.

    Parameters
    ----------
    rx, ry : float, optional
        Semi-axis lengths, before rotation.
    center : (float, float), optional
        Point to draw around.
    rotation : float, optional
        Angle of the ``rx`` axis, in radians.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    rx: float = 120.0
    ry: float = 70.0
    center: Point = (0.0, 0.0)
    rotation: float = 0.0

    @override
    def position(self, u: float) -> Point:
        x, y = self.rx * math.cos(u), self.ry * math.sin(u)
        cos_r, sin_r = math.cos(self.rotation), math.sin(self.rotation)
        cx, cy = self.center
        return (cx + x * cos_r - y * sin_r, cy + x * sin_r + y * cos_r)


@register("arc", family="primitive")
@dataclass(frozen=True, slots=True)
class Arc(ParametricMotif):
    """Part of a circle: ``sweep`` radians of it, starting at ``start_angle``.

    Parameters
    ----------
    radius : float, optional
        Distance from the center.
    start_angle : float, optional
        Where the arc begins, in radians.
    sweep : float, optional
        Angular extent, in radians. Negative sweeps run clockwise.
    center : (float, float), optional
        Point to draw around.
    """

    radius: float = 100.0
    start_angle: float = 0.0
    sweep: float = math.pi
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        theta = self.start_angle + self.sweep * u
        cx, cy = self.center
        return (cx + self.radius * math.cos(theta), cy + self.radius * math.sin(theta))

    @override
    def sweep_turns(self) -> float:
        return abs(self.sweep) / math.tau


@register("sector", family="primitive")
@dataclass(frozen=True, slots=True)
class Sector(Motif):
    """A pie slice: an arc closed back to its center by two radii.

    Parameters
    ----------
    radius : float, optional
        Distance from the center to the arc.
    start_angle : float, optional
        Where the arc begins, in radians.
    sweep : float, optional
        Angular extent, in radians. Negative sweeps run clockwise.
    center : (float, float), optional
        Point of the slice.
    """

    radius: float = 100.0
    start_angle: float = 0.0
    sweep: float = math.pi / 3.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.sweep == 0.0:
            raise ValueError("sweep must be non-zero; a sector of no angle has no area")

    @override
    def build(self) -> Design:
        # The two straight radii are the segments joining the center to each
        # end of the arc, so they need no points of their own -- and the
        # closing one is implied by the path being closed.
        arc = arc_points(self.center, self.radius, self.start_angle, self.sweep)
        return Design((Path((self.center, *arc), closed=True),), meta=spec(self))


@register("line", family="primitive")
@dataclass(frozen=True, slots=True)
class Line(PolygonMotif):
    """A straight segment from ``start`` to ``end``.

    Parameters
    ----------
    start, end : (float, float), optional
        The two endpoints.
    """

    closed: ClassVar[bool] = False

    start: Point = (0.0, 0.0)
    end: Point = (100.0, 100.0)

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        yield (self.start, self.end)


@register("rectangle", family="primitive")
@dataclass(frozen=True, slots=True)
class Rectangle(PolygonMotif):
    """An axis-aligned rectangle centered on ``center``.

    Parameters
    ----------
    width, height : float, optional
        Full extents, not half-extents.
    center : (float, float), optional
        Midpoint of the rectangle.
    """

    width: float = 160.0
    height: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        cx, cy = self.center
        w, h = self.width / 2.0, self.height / 2.0
        yield ((cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h))


@register("rectangle.rounded", family="primitive")
@dataclass(frozen=True, slots=True)
class RoundedRectangle(Motif):
    """A rectangle with its corners replaced by quarter circles.

    Parameters
    ----------
    width, height : float, optional
        Full extents, not half-extents.
    corner_radius : float, optional
        Radius of each corner arc. ``0`` gives a plain rectangle; the
        maximum is half the shorter side, which gives a stadium.
    center : (float, float), optional
        Midpoint of the rectangle.
    """

    width: float = 160.0
    height: float = 100.0
    corner_radius: float = 20.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        limit = min(self.width, self.height) / 2.0
        if not 0.0 <= self.corner_radius <= limit:
            raise ValueError(
                f"corner_radius must be between 0 and {limit} for a "
                f"{self.width}x{self.height} rectangle, got {self.corner_radius}"
            )

    @override
    def build(self) -> Design:
        cx, cy = self.center
        w, h = self.width / 2.0, self.height / 2.0
        r = self.corner_radius
        if r == 0.0:
            # Not a special case for speed: a zero-radius arc would emit its
            # center once per segment, giving the corner sixty-odd copies.
            corners = ((cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h))
            return Design((Path(corners, closed=True),), meta=spec(self))

        quarter = math.pi / 2.0
        points: list[Point] = []
        # Counter-clockwise from the bottom-right corner. The straight sides
        # need no points of their own: they are the segments between the end
        # of one arc and the start of the next.
        for index, (sx, sy) in enumerate(((1, -1), (1, 1), (-1, 1), (-1, -1))):
            pivot = (cx + sx * (w - r), cy + sy * (h - r))
            points.extend(arc_points(pivot, r, -quarter + index * quarter, quarter))
        return Design((Path(tuple(points), closed=True),), meta=spec(self))


@register("polygon.regular", family="primitive")
@dataclass(frozen=True, slots=True)
class RegularPolygon(PolygonMotif):
    """A regular ``sides``-gon inscribed in a circle of radius ``radius``.

    Parameters
    ----------
    sides : int, optional
        Number of corners. At least 3.
    radius : float, optional
        Circumradius -- the distance from the center to a corner, not to an
        edge.
    center : (float, float), optional
        Point to draw around.
    rotation : float, optional
        Angle of the first corner, in radians. Defaults to straight up.
    """

    sides: int = 6
    radius: float = 100.0
    center: Point = (0.0, 0.0)
    rotation: float = _UP

    def __post_init__(self) -> None:
        if self.sides < 3:
            raise ValueError(f"sides must be >= 3, got {self.sides}")

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        yield ring_points(self.sides, self.radius, center=self.center, rotation=self.rotation)


@register("polygon.star", family="primitive")
@dataclass(frozen=True, slots=True)
class StarPolygon(PolygonMotif):
    """The ``{n/k}`` star polygon: every ``step``-th corner of an ``n``-gon.

    ``{5/2}`` is the pentagram, ``{7/3}`` the heptagram, ``{6/2}`` the Star
    of David -- and that last one is *two triangles*, not one path, because
    ``n`` and ``k`` share a factor. Each component comes back as its own
    stroke; joining them would draw an edge that is not part of the figure.

    Parameters
    ----------
    points : int, optional
        The ``n`` in ``{n/k}``: how many points the star has.
    step : int, optional
        The ``k``: how many corners each edge skips ahead. Must be at least
        2 and less than half of ``points``, which is exactly the range in
        which the figure is a star rather than a convex polygon or a
        collection of straight lines.
    radius : float, optional
        Circumradius.
    center : (float, float), optional
        Point to draw around.
    rotation : float, optional
        Angle of the first corner, in radians. Defaults to straight up.
    """

    points: int = 5
    step: int = 2
    radius: float = 100.0
    center: Point = (0.0, 0.0)
    rotation: float = _UP

    def __post_init__(self) -> None:
        if self.points < 5:
            raise ValueError(f"points must be >= 5 to form a star polygon, got {self.points}")
        if not 2 <= self.step < self.points / 2:
            raise ValueError(
                f"step must be at least 2 and less than points/2 "
                f"({self.points / 2}), got {self.step}; step 1 is the convex "
                f"polygon and step points/2 collapses to diameters"
            )

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        vertices = ring_points(self.points, self.radius, center=self.center, rotation=self.rotation)
        # A step sharing a factor with the corner count never visits every
        # corner: it closes early, and the figure is that many overlaid
        # copies rotated off each other.
        components = math.gcd(self.points, self.step)
        per_component = self.points // components
        for start in range(components):
            yield [vertices[(start + i * self.step) % self.points] for i in range(per_component)]


@register("star", family="primitive")
@dataclass(frozen=True, slots=True)
class Star(PolygonMotif):
    """The star people actually draw: outer points joined through inner ones.

    Distinct from :class:`StarPolygon`, which is a single line visiting every
    ``step``-th corner of one circle. This one has two circles and twice as
    many corners, so its arms can be as fat or as thin as you like -- and it
    works for any point count, including the even ones that ``{n/k}`` cannot
    draw in a single stroke.

    Parameters
    ----------
    points : int, optional
        Number of arms.
    inner_ratio : float, optional
        Inner radius as a fraction of the outer. The default is
        ``1/phi**2``, which reproduces the pentagram's proportions.
    radius : float, optional
        Outer radius.
    center : (float, float), optional
        Point to draw around.
    rotation : float, optional
        Angle of the first arm, in radians. Defaults to straight up.
    """

    points: int = 5
    inner_ratio: float = 0.382
    radius: float = 100.0
    center: Point = (0.0, 0.0)
    rotation: float = _UP

    def __post_init__(self) -> None:
        if self.points < 3:
            raise ValueError(f"points must be >= 3, got {self.points}")
        if not 0.0 < self.inner_ratio < 1.0:
            raise ValueError(f"inner_ratio must be between 0 and 1, got {self.inner_ratio}")

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        cx, cy = self.center
        step = math.pi / self.points
        inner = self.radius * self.inner_ratio
        yield [
            (
                cx + (self.radius if i % 2 == 0 else inner) * math.cos(self.rotation + i * step),
                cy + (self.radius if i % 2 == 0 else inner) * math.sin(self.rotation + i * step),
            )
            for i in range(2 * self.points)
        ]


def _superellipse_point(u: float, rx: float, ry: float, exponent: float, center: Point) -> Point:
    """Return the point at parameter ``u`` on ``|x/rx|**n + |y/ry|**n == 1``."""
    cos_u, sin_u = math.cos(u), math.sin(u)
    power = 2.0 / exponent
    cx, cy = center
    return (
        cx + rx * math.copysign(abs(cos_u) ** power, cos_u),
        cy + ry * math.copysign(abs(sin_u) ** power, sin_u),
    )


@register("superellipse", family="primitive")
@dataclass(frozen=True, slots=True)
class Superellipse(ParametricMotif):
    """The curve ``|x/rx|**n + |y/ry|**n == 1``, for any positive ``n``.

    One knob spans the whole range from a four-pointed astroid through the
    diamond (``n = 1``), the ellipse (``n = 2``) and Piet Hein's rounded
    rectangle (``n = 2.5``, the shape of Sergels torg) up to the rectangle
    itself as ``n`` grows.

    Parameters
    ----------
    exponent : float, optional
        The ``n``. Below 2 the sides curve inward, above 2 they bulge out.
    rx, ry : float, optional
        Half-extents along each axis.
    center : (float, float), optional
        Point to draw around.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    #: Piet Hein's value: the one that got built, in Sergels torg.
    exponent: float = 2.5
    rx: float = 100.0
    ry: float = 100.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.exponent <= 0.0:
            raise ValueError(f"exponent must be > 0, got {self.exponent}")

    @override
    def position(self, u: float) -> Point:
        return _superellipse_point(u, self.rx, self.ry, self.exponent, self.center)


@register("squircle", family="primitive")
@dataclass(frozen=True, slots=True)
class Squircle(ParametricMotif):
    """The square-circle midpoint: a :class:`Superellipse` with ``n = 4``.

    A preset rather than a new curve, and the one worth having a name for --
    it is the rounded square of app icons and camera viewfinders, and it
    fills a noticeably larger fraction of its bounding box than a circle
    without reading as a square.

    Parameters
    ----------
    radius : float, optional
        Half-extent along both axes.
    center : (float, float), optional
        Point to draw around.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    #: The exponent that makes a squircle a squircle.
    EXPONENT: ClassVar[float] = 4.0

    radius: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        return _superellipse_point(u, self.radius, self.radius, self.EXPONENT, self.center)


@register("polygon.reuleaux", family="primitive")
@dataclass(frozen=True, slots=True)
class ReuleauxPolygon(Motif):
    """A curve of constant width: the Reuleaux triangle and its odd-sided kin.

    Every arc is centered on the corner opposite it, so the distance across
    the shape is the same in every direction -- it rolls under a plank as
    smoothly as a circle does, while being nothing like one. Only odd corner
    counts work: an even one has a corner opposite a corner rather than an
    edge, and there is nothing to center the arcs on.

    Parameters
    ----------
    sides : int, optional
        Number of corners. Must be odd and at least 3.
    width : float, optional
        The constant width, in every direction.
    center : (float, float), optional
        Point to draw around.
    rotation : float, optional
        Angle of the first corner, in radians. Defaults to straight up.
    """

    sides: int = 3
    width: float = 150.0
    center: Point = (0.0, 0.0)
    rotation: float = _UP

    def __post_init__(self) -> None:
        if self.sides < 3 or self.sides % 2 == 0:
            raise ValueError(f"sides must be odd and >= 3, got {self.sides}")
        if self.width <= 0.0:
            raise ValueError(f"width must be > 0, got {self.width}")

    @override
    def build(self) -> Design:
        # The width is measured corner to opposite corner, which is `opposite`
        # steps around the polygon; invert that to get the circumradius.
        opposite = (self.sides - 1) // 2
        circumradius = self.width / (2.0 * math.sin(math.pi * opposite / self.sides))
        corners = ring_points(self.sides, circumradius, center=self.center, rotation=self.rotation)

        points: list[Point] = []
        for k in range(self.sides):
            pivot = corners[k]
            begin = corners[(k + opposite) % self.sides]
            finish = corners[(k + opposite + 1) % self.sides]
            start_angle = math.atan2(begin[1] - pivot[1], begin[0] - pivot[0])
            end_angle = math.atan2(finish[1] - pivot[1], finish[0] - pivot[0])
            # Both ends lie on the same short arc, so the sweep is the
            # counter-clockwise difference and is always well under pi.
            sweep = (end_angle - start_angle) % math.tau
            arc = arc_points(pivot, self.width, start_angle, sweep)
            # Consecutive arcs end and begin at the same corner.
            points.extend(arc if k == 0 else arc[1:])

        # The final arc closes back onto the first arc's start, and a closed
        # path implies that segment rather than storing it.
        return Design((Path(tuple(points[:-1]), closed=True),), meta=spec(self))


@register("egg", family="primitive")
@dataclass(frozen=True, slots=True)
class Egg(ParametricMotif):
    """An oval fatter at one end than the other.

    An ellipse whose height is tapered along its length, which is the
    simplest form that reads as an egg and stays smooth everywhere.
    ``taper = 0`` is exactly an ellipse.

    Parameters
    ----------
    length : float, optional
        Full extent along the x-axis.
    width : float, optional
        Full extent across, before tapering.
    taper : float, optional
        How lopsided the egg is, between -1 and 1. Positive values put the
        blunt end on the right.
    center : (float, float), optional
        Point to draw around.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    length: float = 140.0
    width: float = 100.0
    taper: float = 0.25
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if not -1.0 < self.taper < 1.0:
            raise ValueError(
                f"taper must be between -1 and 1, got {self.taper}; at 1 the "
                f"narrow end pinches into a cusp"
            )

    @override
    def position(self, u: float) -> Point:
        cx, cy = self.center
        cos_u = math.cos(u)
        return (
            cx + self.length / 2.0 * cos_u,
            cy + self.width / 2.0 * math.sin(u) * (1.0 + self.taper * cos_u),
        )


@register("points.grid", family="primitive")
@dataclass(frozen=True, slots=True)
class PointGrid(Motif):
    """A rectangular lattice of loose points, optionally staggered.

    Produces points rather than strokes: this is the substrate for dot art,
    stipple fields and object placement, not something to draw a line
    through. ``stagger=0.5`` offsets alternate rows by half a step, which
    turns the square lattice into a triangular one.

    Parameters
    ----------
    columns, rows : int, optional
        Lattice size. At least 1 each.
    dx, dy : float, optional
        Spacing between neighbours.
    stagger : float, optional
        Fraction of ``dx`` to shift every other row by.
    center : (float, float), optional
        Midpoint of the lattice.
    """

    columns: int = 12
    rows: int = 12
    dx: float = 20.0
    dy: float = 20.0
    stagger: float = 0.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.columns < 1 or self.rows < 1:
            raise ValueError(f"columns and rows must be >= 1, got {self.columns}x{self.rows}")

    @override
    def build(self) -> Design:
        cx, cy = self.center
        x0 = cx - (self.columns - 1) * self.dx / 2.0
        y0 = cy - (self.rows - 1) * self.dy / 2.0
        points = tuple(
            (
                x0 + column * self.dx + (self.stagger * self.dx if row % 2 else 0.0),
                y0 + row * self.dy,
            )
            for row in range(self.rows)
            for column in range(self.columns)
        )
        return Design(points=points, meta=spec(self))


@register("points.poisson", family="primitive")
@dataclass(frozen=True, slots=True)
class PoissonDiscPoints(Motif):
    """Points scattered at random, but never closer together than a set distance.

    Bridson's algorithm. The result looks organic in a way a plain random
    scatter does not: random points clump and leave holes, while these fill
    the area evenly without ever falling into a visible grid. It is what you
    want for stippling, foliage placement and any "natural" arrangement.

    Parameters
    ----------
    width, height : float, optional
        Size of the area to fill.
    min_distance : float, optional
        Closest two points may ever be.
    seed : int, optional
        Seeds a private generator, so the same seed always gives the same
        field and the design stays reproducible from its metadata.
    attempts : int, optional
        Candidates tried around each accepted point before giving up on it.
        Higher packs slightly tighter and costs proportionally more.
    center : (float, float), optional
        Midpoint of the area.
    """

    width: float = 300.0
    height: float = 300.0
    min_distance: float = 20.0
    seed: int = field(default=0, kw_only=True)
    attempts: int = field(default=30, kw_only=True)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError(f"width and height must be > 0, got {self.width}x{self.height}")
        if self.min_distance <= 0.0:
            raise ValueError(f"min_distance must be > 0, got {self.min_distance}")
        if self.attempts < 1:
            raise ValueError(f"attempts must be >= 1, got {self.attempts}")
        # Bridson packs at roughly 0.7 points per min_distance square; refuse
        # up front rather than after filling memory.
        estimate = 0.7 * self.width * self.height / self.min_distance**2
        if estimate > _MAX_POINTS:
            raise ValueError(
                f"min_distance {self.min_distance} would scatter about {int(estimate)} "
                f"points over {self.width}x{self.height} (limit {_MAX_POINTS}); "
                f"use a larger min_distance or a smaller area"
            )

    @override
    def build(self) -> Design:
        rng = random.Random(self.seed)
        radius = self.min_distance
        # One point per cell at most, which is what makes the neighbour check
        # a constant-size window rather than a scan.
        cell = radius / math.sqrt(2.0)
        columns = max(1, math.ceil(self.width / cell))
        rows = max(1, math.ceil(self.height / cell))
        grid: dict[tuple[int, int], Point] = {}

        def fits(point: Point) -> bool:
            """Return whether ``point`` clears every already-placed neighbour."""
            gx, gy = int(point[0] / cell), int(point[1] / cell)
            for i in range(max(gx - 2, 0), min(gx + 3, columns)):
                for j in range(max(gy - 2, 0), min(gy + 3, rows)):
                    other = grid.get((i, j))
                    if other is not None and math.dist(point, other) < radius:
                        return False
            return True

        first = (rng.uniform(0.0, self.width), rng.uniform(0.0, self.height))
        grid[int(first[0] / cell), int(first[1] / cell)] = first
        accepted = [first]
        active = [first]

        while active:
            index = rng.randrange(len(active))
            origin = active[index]
            for _ in range(self.attempts):
                angle = rng.uniform(0.0, math.tau)
                # Uniform over the annulus between r and 2r: sampling the
                # radius linearly instead would bunch candidates inward.
                distance = radius * math.sqrt(rng.uniform(1.0, 4.0))
                candidate = (
                    origin[0] + distance * math.cos(angle),
                    origin[1] + distance * math.sin(angle),
                )
                if not (0.0 <= candidate[0] < self.width and 0.0 <= candidate[1] < self.height):
                    continue
                if fits(candidate):
                    grid[int(candidate[0] / cell), int(candidate[1] / cell)] = candidate
                    accepted.append(candidate)
                    active.append(candidate)
                    break
            else:
                # Nothing else fits around this one; it stops seeding.
                active[index] = active[-1]
                active.pop()

        cx, cy = self.center
        x0, y0 = cx - self.width / 2.0, cy - self.height / 2.0
        points = tuple((x0 + x, y0 + y) for x, y in accepted)
        return Design(points=points, meta=spec(self))
