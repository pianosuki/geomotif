"""Sacred geometry: circles on a hexagonal grid, and what people drew on them.

Almost everything in this module is the same idea repeated. Start with a
circle. Put another the same size through its middle -- that is the
:class:`VesicaPiscis`. Keep going until the first circle is ringed by six more
and you have the :class:`SeedOfLife`; keep going outward and you have the
:class:`FlowerOfLife`. Thin the flower down to the thirteen circles that touch
without crossing and you have the :class:`FruitOfLife`; join all thirteen
middles to each other and you have :class:`MetatronsCube`. One construction,
five figures, each of which somebody has carved into a temple.

The two outliers are :class:`SriYantra`, which is nine interlocking triangles
rather than circles, and :class:`GoldenRectangle`, which is the one figure
here with an actual theorem in it.

These are cheap to draw and they plot beautifully, because every stroke is a
full circle or a straight line -- there is nothing for a pen to stutter over.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING, ClassVar, override

from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Design, Path
from ._common import arc_points, ring_points

if TYPE_CHECKING:
    from ..core.types import Point

__all__ = [
    "FlowerOfLife",
    "FruitOfLife",
    "GoldenRectangle",
    "MetatronsCube",
    "SeedOfLife",
    "SriYantra",
    "VesicaPiscis",
]

#: Golden ratio, for :class:`GoldenRectangle`.
_PHI = (1.0 + math.sqrt(5.0)) / 2.0

#: Ceiling on how many circles a packing may reach, so a mistyped ring count
#: raises instead of filling memory.
_MAX_CIRCLES = 2_000

#: Ceiling on :class:`GoldenRectangle` cuts. Each is a golden ratio smaller
#: than the last, so sixty-four of them span forty orders of magnitude.
_MAX_CUTS = 64


def _check_radius(owner: str, radius: float, *, name: str = "radius") -> None:
    if radius <= 0.0:
        raise ValueError(f"{owner} {name} must be > 0, got {radius}")


def _circle(center: Point, radius: float) -> Path:
    """Return a closed path around ``center``.

    The last sample lands back on the first, and a closed
    :class:`~geomotif.Path` implies its seam, so it is dropped.
    """
    return Path(arc_points(center, radius, 0.0, math.tau)[:-1], closed=True)


def _hex_lattice(spacing: float, rings: int, center: Point) -> tuple[Point, ...]:
    """Return the hexagonal lattice points within ``rings`` steps of ``center``.

    Counts run 1, 7, 19, 37, 61 -- the centred hexagonal numbers, which is
    what makes a flower of life come out with the number of circles the
    figure is named for.
    """
    cx, cy = center
    ux, uy = spacing, 0.0
    vx, vy = spacing / 2.0, spacing * math.sqrt(3.0) / 2.0
    reach = spacing * rings + spacing * 1e-9
    return tuple(
        (cx + i * ux + j * vx, cy + i * uy + j * vy)
        for i in range(-rings, rings + 1)
        for j in range(-rings, rings + 1)
        if math.hypot(i * ux + j * vx, i * uy + j * vy) <= reach
    )


@register("sacred.vesica", family="sacred")
@dataclass(frozen=True, slots=True)
class VesicaPiscis(Motif):
    """Two circles, each through the other's middle.

    The almond where they overlap is the vesica itself. Its height is
    ``sqrt(3)`` times its width, so the figure hands you an equilateral
    triangle and a square root of three with no measuring -- which is why
    every construction below starts here.

    Parameters
    ----------
    radius : float, optional
        Radius of both circles, which is also how far apart they sit.
    center : (float, float), optional
        Midpoint between the two, and the middle of the almond.
    lens : bool, optional
        Also draw the almond's own outline as a closed path.
    """

    radius: float = 90.0
    center: Point = (0.0, 0.0)
    lens: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        _check_radius(type(self).__name__, self.radius)

    def centers(self) -> tuple[Point, Point]:
        """Return the two circle middles, left then right."""
        cx, cy = self.center
        half = self.radius / 2.0
        return ((cx - half, cy), (cx + half, cy))

    def lens_path(self) -> Path:
        """Return the almond: two arcs of 120 degrees, meeting at the points."""
        left, right = self.centers()
        third = math.tau / 3.0
        # Each arc is the far circle's, swept between the two crossings.
        upper = arc_points(left, self.radius, -third / 2.0, third)
        lower = arc_points(right, self.radius, math.pi - third / 2.0, third)
        return Path(upper[:-1] + lower[:-1], closed=True)

    @override
    def build(self) -> Design:
        paths = [_circle(point, self.radius) for point in self.centers()]
        if self.lens:
            paths.append(self.lens_path())
        return Design(tuple(paths), meta=spec(self))


@register("sacred.seed-of-life", family="sacred")
@dataclass(frozen=True, slots=True)
class SeedOfLife(Motif):
    """Seven circles: one in the middle, six around it, all the same size.

    Each of the six passes through the middle one's centre, and the six meet
    each other exactly. It is the first closed figure the vesica construction
    reaches, and the first ring of the :class:`FlowerOfLife`.

    Parameters
    ----------
    radius : float, optional
        Radius of every circle, which is also the spacing between them.
    center : (float, float), optional
        Middle of the figure.
    rotation : float, optional
        Angle of the first outer circle, in radians.
    """

    radius: float = 60.0
    center: Point = (0.0, 0.0)
    rotation: float = math.pi / 2.0

    def __post_init__(self) -> None:
        _check_radius(type(self).__name__, self.radius)

    def centers(self) -> tuple[Point, ...]:
        """Return the seven circle middles, the shared one first."""
        return (
            self.center,
            *ring_points(6, self.radius, center=self.center, rotation=self.rotation),
        )

    @override
    def build(self) -> Design:
        return Design(
            tuple(_circle(point, self.radius) for point in self.centers()), meta=spec(self)
        )


@register("sacred.flower-of-life", family="sacred")
@dataclass(frozen=True, slots=True)
class FlowerOfLife(Motif):
    """The seed of life continued outward: circles on a hexagonal grid.

    Every circle passes through the middles of its six neighbours, so the
    whole figure is one lattice with one spacing. Ring counts give 1, 7, 19,
    37 and 61 circles; the nineteen-circle version inside its boundary is the
    one carved at Abydos and the one most people mean.

    Parameters
    ----------
    rings : int, optional
        How many rings of circles out from the middle.
    radius : float, optional
        Radius of every circle, which is also the spacing between them.
    center : (float, float), optional
        Middle of the figure.
    boundary : bool, optional
        Draw the circle that encloses the lot. It touches the outermost
        circles from inside, which is what closes the figure off.
    """

    rings: int = 2
    radius: float = 40.0
    center: Point = (0.0, 0.0)
    boundary: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_radius(owner, self.radius)
        if self.rings < 0:
            raise ValueError(f"{owner} rings must be >= 0, got {self.rings}")
        if (1 + 3 * self.rings * (self.rings + 1)) > _MAX_CIRCLES:
            raise ValueError(
                f"{owner} rings={self.rings} would draw more than {_MAX_CIRCLES} circles"
            )

    def centers(self) -> tuple[Point, ...]:
        """Return every circle's middle."""
        return _hex_lattice(self.radius, self.rings, self.center)

    @override
    def build(self) -> Design:
        paths = [_circle(point, self.radius) for point in self.centers()]
        if self.boundary:
            paths.append(_circle(self.center, self.radius * (self.rings + 1)))
        return Design(tuple(paths), meta=spec(self))


@register("sacred.fruit-of-life", family="sacred")
@dataclass(frozen=True, slots=True)
class FruitOfLife(Motif):
    """The thirteen circles of the flower that touch without overlapping.

    Take the flower of life and keep only the circles that meet edge to edge:
    one in the middle, six around it at twice the radius, and six more at the
    corners beyond. Their thirteen middles are what :class:`MetatronsCube`
    joins up.

    Parameters
    ----------
    radius : float, optional
        Radius of every circle. Neighbours sit ``2 * radius`` apart, so they
        touch rather than cross.
    center : (float, float), optional
        Middle of the figure.
    rotation : float, optional
        Angle of the first inner circle, in radians.
    """

    radius: float = 40.0
    center: Point = (0.0, 0.0)
    rotation: float = math.pi / 2.0

    def __post_init__(self) -> None:
        _check_radius(type(self).__name__, self.radius)

    def centers(self) -> tuple[Point, ...]:
        """Return the thirteen middles: the shared one, then each ring outward."""
        step = 2.0 * self.radius
        inner = ring_points(6, step, center=self.center, rotation=self.rotation)
        # The outer six sit between the inner ones, further out by sqrt(3):
        # the same lattice, one shell along.
        outer = ring_points(
            6,
            step * math.sqrt(3.0),
            center=self.center,
            rotation=self.rotation + math.pi / 6.0,
        )
        return (self.center, *inner, *outer)

    @override
    def build(self) -> Design:
        return Design(
            tuple(_circle(point, self.radius) for point in self.centers()), meta=spec(self)
        )


@register("sacred.metatrons-cube", family="sacred")
@dataclass(frozen=True, slots=True)
class MetatronsCube(Motif):
    """Thirteen circles with every pair of middles joined by a line.

    Drawing all seventy-eight chords rather than a chosen few is the point:
    the outlines of five of the Platonic solids appear in the result without
    anybody having placed them, because the thirteen middles are a projection
    of the cubic lattice.

    Parameters
    ----------
    radius : float, optional
        Radius of every circle.
    center : (float, float), optional
        Middle of the figure.
    rotation : float, optional
        Angle of the first inner circle, in radians.
    circles : bool, optional
        Draw the circles as well as the lines. Turn it off for the bare
        lattice of chords.
    """

    radius: float = 34.0
    center: Point = (0.0, 0.0)
    rotation: float = math.pi / 2.0
    circles: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        _check_radius(type(self).__name__, self.radius)

    def centers(self) -> tuple[Point, ...]:
        """Return the thirteen middles, as :class:`FruitOfLife` places them."""
        return FruitOfLife(radius=self.radius, center=self.center, rotation=self.rotation).centers()

    @override
    def build(self) -> Design:
        nodes = self.centers()
        paths = [Path((a, b)) for a, b in combinations(nodes, 2)]
        if self.circles:
            paths.extend(_circle(point, self.radius) for point in nodes)
        return Design(tuple(paths), meta=spec(self))


@register("sacred.sri-yantra", family="sacred")
@dataclass(frozen=True, slots=True)
class SriYantra(Motif):
    """Nine interlocking triangles inside a circle, four pointing up and five down.

    Every triangle has a horizontal base and an apex on the vertical axis, so
    three numbers fix each one: how high the base sits, how wide it is, and
    how far the apex reaches. That is :attr:`bands` below, in units of the
    radius, and editing it is how you draw a different yantra.

    The classical figure additionally asks that all fifty-four crossings be
    exactly concurrent, which pins those numbers to the solution of a
    nonlinear system rather than to a table. What is here is the drawn
    yantra: right in structure, arrangement and count, and true to within a
    line's width rather than exactly.

    Parameters
    ----------
    size : float, optional
        Diameter of the enclosing circle.
    center : (float, float), optional
        Middle of the figure.
    boundary : bool, optional
        Draw the enclosing circle.
    bindu : bool, optional
        Mark the point at the middle, where the innermost triangle closes.
    """

    #: Each triangle as ``(base height, apex height, base half-width)``, in
    #: units of the radius. A base above its apex points down. The four with
    #: a base below their apex are the upward ones.
    bands: ClassVar[tuple[tuple[float, float, float], ...]] = (
        (0.86, -0.62, 0.50),
        (0.66, -0.94, 0.70),
        (0.44, -0.30, 0.86),
        (0.20, -0.14, 0.96),
        (0.30, -0.22, 0.42),
        (-0.66, 0.94, 0.70),
        (-0.86, 0.62, 0.50),
        (-0.44, 0.30, 0.86),
        (-0.20, 0.14, 0.96),
    )

    size: float = 260.0
    center: Point = (0.0, 0.0)
    boundary: bool = field(default=True, kw_only=True)
    bindu: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        _check_radius(type(self).__name__, self.size, name="size")

    def triangles(self) -> tuple[tuple[Point, Point, Point], ...]:
        """Return the nine triangles, base corners first then the apex."""
        radius = self.size / 2.0
        cx, cy = self.center
        return tuple(
            (
                (cx - half * radius, cy + base * radius),
                (cx + half * radius, cy + base * radius),
                (cx, cy + apex * radius),
            )
            for base, apex, half in self.bands
        )

    @override
    def build(self) -> Design:
        paths = [Path(corners, closed=True) for corners in self.triangles()]
        if self.boundary:
            paths.append(_circle(self.center, self.size / 2.0))
        points = (self.center,) if self.bindu else ()
        return Design(tuple(paths), points, meta=spec(self))


@register("sacred.golden-rectangle", family="sacred")
@dataclass(frozen=True, slots=True)
class GoldenRectangle(Motif):
    """A rectangle that keeps its shape when you cut a square off it.

    Cut the largest possible square from a golden rectangle and what is left
    is another golden rectangle, turned a quarter turn. Do it again and again
    and the squares spiral inward -- the frame the Fibonacci spiral is drawn
    in. Draw the outer rectangle plus each cut, and the whole theorem is one
    picture.

    Parameters
    ----------
    size : float, optional
        Length of the long side.
    depth : int, optional
        How many squares to cut off. Capped: past sixty-odd the cut is
        narrower than a wavelength of light, never mind a pen.
    center : (float, float), optional
        Middle of the outer rectangle.
    """

    size: float = 280.0
    depth: int = 8
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_radius(owner, self.size, name="size")
        if not 0 <= self.depth <= _MAX_CUTS:
            raise ValueError(f"{owner} depth must be in [0, {_MAX_CUTS}], got {self.depth}")

    def squares(self) -> tuple[tuple[Point, Point], ...]:
        """Return each cut as the two ends of the line that makes it."""
        width = self.size
        height = self.size / _PHI
        cx, cy = self.center
        left, bottom = cx - width / 2.0, cy - height / 2.0
        right, top = left + width, bottom + height
        cuts: list[tuple[Point, Point]] = []
        # Cut from the left, then the bottom, then the right, then the top,
        # so the leftover rectangle spirals inward the way the squares do.
        for step in range(self.depth):
            side = min(right - left, top - bottom)
            match step % 4:
                case 0:
                    left += side
                    cuts.append(((left, bottom), (left, top)))
                case 1:
                    bottom += side
                    cuts.append(((left, bottom), (right, bottom)))
                case 2:
                    right -= side
                    cuts.append(((right, bottom), (right, top)))
                case _:
                    top -= side
                    cuts.append(((left, top), (right, top)))
        return tuple(cuts)

    @override
    def build(self) -> Design:
        width = self.size
        height = self.size / _PHI
        cx, cy = self.center
        half_w, half_h = width / 2.0, height / 2.0
        frame = Path(
            (
                (cx - half_w, cy - half_h),
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy + half_h),
            ),
            closed=True,
        )
        return Design((frame, *(Path(cut) for cut in self.squares())), meta=spec(self))
