"""Islamic geometric patterns: girih tiles, strapwork and the star rosette.

The patterns on Persian and Timurid tilework are not drawn freehand and they
are not drawn on a square grid. They are drawn with *girih tiles*: five shapes
whose sides are all the same length and whose angles are all multiples of 36
degrees, each carrying a fixed set of lines. Lay the tiles down, draw the lines
they carry, then rub the tiles out -- what is left is the pattern. The five
shapes are the regular decagon, the regular pentagon, an elongated hexagon, a
bowtie and a rhombus, and :class:`GirihTile` draws any of them.

The lines themselves come from an older rule, usually named for Ernest Hankin,
who worked it out from the monuments: put a point at the middle of every edge
and send two lines out from it, each making the same angle with that edge, and
let every line run until it meets another. Because neighbouring tiles use the
same angle at the shared edge midpoint, the two lines meeting there are exactly
opposite and continue straight across -- which is why the finished pattern
shows no trace of the tiles that generated it. That rule is what
:class:`InterlockingDecagons` applies to the tiling :class:`TenfoldGirih` lays
down.

:class:`Rosette` is the other half of the tradition: the *shamsa*, a star
nested inside a blunter star inside a blunter one still, each reaching exactly
as far as the last one's valleys. :class:`RosetteTiling` repeats it on a
lattice, and :class:`HexStarLattice` is the six-fold pattern that needs no
strapwork at all -- six-pointed stars with rhombi in the gaps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, override

from ..bases import LatticeTiling, PolygonMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Bounds, Design, Path
from ._common import ring_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "GIRIH_SHAPES",
    "GirihTile",
    "HexStarLattice",
    "InterlockingDecagons",
    "Rosette",
    "RosetteTiling",
    "TenfoldGirih",
]

#: The five girih tiles, in the order they are usually shown.
GIRIH_SHAPES = ("decagon", "pentagon", "hexagon", "bowtie", "rhombus")

type GirihShape = Literal["decagon", "pentagon", "hexagon", "bowtie", "rhombus"]

#: Interior angles of each girih tile, in degrees, walked in order. Every one
#: is a multiple of 36 and every side is the same length -- that is the whole
#: of what makes the five tiles a set.
_INTERIOR: dict[str, tuple[float, ...]] = {
    "decagon": (144.0,) * 10,
    "pentagon": (108.0,) * 5,
    "hexagon": (72.0, 144.0, 144.0, 72.0, 144.0, 144.0),
    "bowtie": (72.0, 72.0, 216.0, 72.0, 72.0, 216.0),
    "rhombus": (72.0, 108.0, 72.0, 108.0),
}

#: The contact angle the girih tiles are drawn with: the strapwork crosses
#: every edge at 72 degrees to it, which is what makes the lines of one tile
#: continue into the next without a kink.
GIRIH_CONTACT = math.tau / 5.0

#: A 300x300 square about the origin: what every lattice motif here fills in
#: the gallery and in the conformance suite.
_EXAMPLE_REGION = Bounds(-150.0, -150.0, 150.0, 150.0)

_ROOT3 = math.sqrt(3.0)

#: Ceilings on how much geometry one motif may expand to, so a mistyped
#: parameter raises rather than filling memory.
_MAX_LAYERS = 24
_MAX_POINTS = 120


def _check_size(owner: str, size: float, *, name: str = "size") -> None:
    """Reject a dimension that would collapse or invert the figure."""
    if size <= 0.0:
        raise ValueError(f"{owner} {name} must be > 0, got {size}")


def _closed(*outlines: Sequence[Point]) -> Design:
    """Return a design of one closed path per outline. The usual cell."""
    return Design(tuple(Path(tuple(corners), closed=True) for corners in outlines))


def _walk(interior: Sequence[float], side: float) -> tuple[Point, ...]:
    """Return the corners of the polygon with these interior angles, centerd.

    Walking a polygon by its turns rather than listing its corners is what
    makes the girih tiles one table instead of five: every tile has the same
    side, so the angles are all that distinguish them.
    """
    corners: list[Point] = [(0.0, 0.0)]
    heading = 0.0
    for angle in interior[:-1]:
        x, y = corners[-1]
        corners.append((x + side * math.cos(heading), y + side * math.sin(heading)))
        heading += math.pi - math.radians(angle)
    cx = math.fsum(x for x, _ in corners) / len(corners)
    cy = math.fsum(y for _, y in corners) / len(corners)
    return tuple((x - cx, y - cy) for x, y in corners)


def _signed_area(corners: Sequence[Point]) -> float:
    """Return twice the signed area: positive when the corners run counter-clockwise."""
    return math.fsum(
        corners[i][0] * corners[(i + 1) % len(corners)][1]
        - corners[(i + 1) % len(corners)][0] * corners[i][1]
        for i in range(len(corners))
    )


def _rays(corners: Sequence[Point], contact: float) -> tuple[tuple[Point, Point], ...]:
    """Return two unit rays out of every edge midpoint, both leaning inward."""
    outline = list(corners) if _signed_area(corners) > 0.0 else list(reversed(corners))
    rays: list[tuple[Point, Point]] = []
    cos, sin = math.cos(contact), math.sin(contact)
    for i, start in enumerate(outline):
        end = outline[(i + 1) % len(outline)]
        middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        span = math.dist(start, end)
        tx, ty = (end[0] - start[0]) / span, (end[1] - start[1]) / span
        # Counter-clockwise corners put the left normal on the inside.
        nx, ny = -ty, tx
        rays.append((middle, (cos * tx + sin * nx, cos * ty + sin * ny)))
        rays.append((middle, (-cos * tx + sin * nx, -cos * ty + sin * ny)))
    return tuple(rays)


def _leaves_at(ray: tuple[Point, Point], corners: Sequence[Point]) -> float:
    """Return how far a ray travels before crossing the tile's outline again."""
    (ox, oy), (dx, dy) = ray
    best = math.inf
    for i, start in enumerate(corners):
        end = corners[(i + 1) % len(corners)]
        ex, ey = end[0] - start[0], end[1] - start[1]
        det = ex * dy - ey * dx
        if abs(det) < 1e-12:
            continue
        rx, ry = start[0] - ox, start[1] - oy
        along = (ex * ry - ey * rx) / det
        across = (dx * ry - dy * rx) / det
        if along > 1e-9 and -1e-9 <= across <= 1.0 + 1e-9:
            best = min(best, along)
    return best


def _strapwork(corners: Sequence[Point], contact: float) -> tuple[Path, ...]:
    """Return Hankin's strapwork for one tile: two lines out of every edge midpoint.

    The lines all grow at the same rate and stop in pairs, when two tips
    arrive at the same place at the same moment. Where their paths merely
    cross they carry straight on, which is what keeps a long strap from being
    cut short by a short one it happens to pass over -- the difference between
    the elongated hexagon's straps crossing it end to end and a row of stubs.

    A line with no partner runs until it leaves the tile and picks up again in
    the neighbour: at the bowtie's reflex corners the two lines are parallel
    and never could meet, so that is what they do.

    Straps that stop on each other come back as one three-point stroke rather
    than two, so the pen lifts once per strap instead of twice.
    """
    rays = _rays(corners, contact)
    stops = [_leaves_at(ray, corners) for ray in rays]

    meetings: list[tuple[float, int, int]] = []
    for i, (origin, direction) in enumerate(rays):
        for j in range(i + 1, len(rays)):
            other_origin, other_direction = rays[j]
            det = other_direction[0] * direction[1] - other_direction[1] * direction[0]
            if abs(det) < 1e-12:
                continue  # parallel, so this pair never meets
            dx = other_origin[0] - origin[0]
            dy = other_origin[1] - origin[1]
            here = (other_direction[0] * dy - other_direction[1] * dx) / det
            there = (direction[0] * dy - direction[1] * dx) / det
            # Head on means the same distance from both midpoints: a shared
            # tip rather than a crossing.
            if here > 1e-9 and abs(here - there) < 1e-7 * max(1.0, here):
                meetings.append((here, i, j))
    meetings.sort()

    partners: list[int | None] = [None] * len(rays)
    for distance, i, j in meetings:
        if partners[i] is None and partners[j] is None and distance < min(stops[i], stops[j]):
            stops[i] = stops[j] = distance
            partners[i], partners[j] = j, i

    def tip(index: int) -> Point:
        (ox, oy), (dx, dy) = rays[index]
        return (ox + stops[index] * dx, oy + stops[index] * dy)

    paths: list[Path] = []
    drawn = [False] * len(rays)
    for i, partner in enumerate(partners):
        if drawn[i]:
            continue
        drawn[i] = True
        if partner is None:
            paths.append(Path((rays[i][0], tip(i))))
        else:
            drawn[partner] = True
            paths.append(Path((rays[i][0], tip(i), rays[partner][0])))
    return tuple(paths)


# --- the rosette ------------------------------------------------------------


@register("girih.rosette", family="girih")
@dataclass(frozen=True, slots=True)
class Rosette(PolygonMotif):
    """The shamsa: a star, a blunter star inside it, and so on inward.

    Each layer is the outline of the ``{points/sharpness}`` star polygon. The
    next layer in is turned half a step and scaled so that its points land
    exactly in the valleys of the one outside it, which is the proportion the
    figure is built on: ``cos(k*pi/n) / cos((k-1)*pi/n)``, the same ratio that
    gives the pentagram its ``1/phi**2``. The innermost valleys are joined by
    a plain polygon, which is where the tilework usually puts a boss.

    Parameters
    ----------
    points : int, optional
        Points on each star.
    sharpness : int, optional
        The ``k`` in ``{n/k}``: how many corners each edge skips. Higher is
        spikier, and a spikier star nests faster.
    layers : int, optional
        How many stars, counting outward from the middle.
    radius : float, optional
        Circumradius of the outermost star.
    rotation : float, optional
        Angle of the outermost star's first point. Defaults to straight up.
    center : (float, float), optional
        Middle of the rosette.
    """

    points: int = 12
    sharpness: int = 3
    layers: int = 3
    radius: float = 140.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.radius, name="radius")
        if not 5 <= self.points <= _MAX_POINTS:
            raise ValueError(f"{owner} points must be in [5, {_MAX_POINTS}], got {self.points}")
        if not 2 <= self.sharpness < self.points / 2:
            raise ValueError(
                f"{owner} sharpness must be at least 2 and less than points/2 "
                f"({self.points / 2}), got {self.sharpness}; below that the star is "
                f"a convex polygon and above it the edges pass through the middle"
            )
        if not 1 <= self.layers <= _MAX_LAYERS:
            raise ValueError(f"{owner} layers must be in [1, {_MAX_LAYERS}], got {self.layers}")

    @property
    def nesting(self) -> float:
        """Radius of one layer as a fraction of the layer outside it."""
        n, k = self.points, self.sharpness
        return math.cos(k * math.pi / n) / math.cos((k - 1) * math.pi / n)

    def star(self, layer: int) -> tuple[Point, ...]:
        """Return the corners of one layer, points and valleys alternating."""
        outer = self.radius * self.nesting**layer
        # Half a step of turn per layer is what puts this star's points in the
        # valleys of the one outside it rather than on top of its points.
        rotation = self.rotation + layer * math.pi / self.points
        inner = outer * self.nesting
        step = math.tau / self.points
        corners: list[Point] = []
        cx, cy = self.center
        for i in range(self.points):
            angle = rotation + i * step
            corners.append((cx + outer * math.cos(angle), cy + outer * math.sin(angle)))
            valley = angle + step / 2.0
            corners.append((cx + inner * math.cos(valley), cy + inner * math.sin(valley)))
        return tuple(corners)

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        for layer in range(self.layers):
            yield self.star(layer)
        # The boss in the middle: the innermost star's valleys, joined up.
        yield ring_points(
            self.points,
            self.radius * self.nesting**self.layers,
            center=self.center,
            rotation=self.rotation + self.layers * math.pi / self.points,
        )


# --- the tiles --------------------------------------------------------------


@register("girih.tile", family="girih", example={"size": 90.0})
@dataclass(frozen=True, slots=True)
class GirihTile(Motif):
    """One of the five girih tiles, with the strapwork it carries.

    All five have the same side length and only angles that are multiples of
    36 degrees, which is what lets them be shuffled freely -- and what makes
    the strapwork of one line up with the strapwork of its neighbour.

    Parameters
    ----------
    shape : str, optional
        One of ``"decagon"``, ``"pentagon"``, ``"hexagon"`` (the elongated
        one), ``"bowtie"`` or ``"rhombus"``.
    size : float, optional
        Side length, shared by every tile.
    contact : float, optional
        Angle the strapwork makes with each edge, in radians.
    strapwork : bool, optional
        Draw the lines the tile carries.
    outline : bool, optional
        Draw the tile itself. In finished work the tile is rubbed out and
        only the strapwork remains.
    rotation : float, optional
        Turn the tile, in radians.
    center : (float, float), optional
        Middle of the tile.
    """

    shape: GirihShape = "decagon"
    size: float = 60.0
    contact: float = GIRIH_CONTACT
    strapwork: bool = field(default=True, kw_only=True)
    outline: bool = field(default=True, kw_only=True)
    rotation: float = 0.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if self.shape not in _INTERIOR:
            raise ValueError(
                f"{owner} shape must be one of {', '.join(GIRIH_SHAPES)}, got {self.shape!r}"
            )
        if not 0.0 < self.contact < math.pi / 2.0:
            raise ValueError(
                f"{owner} contact must be strictly between 0 and pi/2 radians, got "
                f"{self.contact}; outside that the strapwork leaves the tile"
            )
        if not (self.strapwork or self.outline):
            raise ValueError(f"{owner} would draw nothing: set strapwork or outline")

    def corners(self) -> tuple[Point, ...]:
        """Return the tile's corners, turned and placed."""
        cos, sin = math.cos(self.rotation), math.sin(self.rotation)
        cx, cy = self.center
        return tuple(
            (cx + x * cos - y * sin, cy + x * sin + y * cos)
            for x, y in _walk(_INTERIOR[self.shape], self.size)
        )

    @override
    def build(self) -> Design:
        corners = self.corners()
        paths: list[Path] = []
        if self.outline:
            paths.append(Path(corners, closed=True))
        if self.strapwork:
            paths.extend(_strapwork(corners, self.contact))
        return Design(tuple(paths), meta=spec(self))


# --- the tenfold tiling and its pattern -------------------------------------


def _decagon_cell(size: float) -> tuple[tuple[Point, ...], tuple[Point, ...]]:
    """Return the decagon and the bowtie that together fill one lattice cell.

    Regular decagons laid edge to edge on a rhombic lattice leave a gap, and
    the gap is exactly one girih bowtie -- same side, same angles. That is not
    a coincidence to be checked by eye: the cell's two areas add up to the
    determinant of its basis, which is what the tests assert.
    """
    circumradius = size / (2.0 * math.sin(math.pi / 10.0))
    reach = size / math.tan(math.pi / 10.0)  # twice the apothem: center to center
    across = (reach, 0.0)
    slant = (reach * math.cos(math.tau / 5.0), reach * math.sin(math.tau / 5.0))

    def corner(origin: Point, degrees: float) -> Point:
        angle = math.radians(degrees)
        return (
            origin[0] + circumradius * math.cos(angle),
            origin[1] + circumradius * math.sin(angle),
        )

    decagon = ring_points(10, circumradius, rotation=math.pi / 10.0)
    bowtie = (
        corner((0.0, 0.0), 54.0),
        corner((0.0, 0.0), 18.0),
        corner(across, 126.0),
        corner(across, 90.0),
        corner(slant, -18.0),
        corner(slant, -54.0),
    )
    return decagon, bowtie


def _tenfold_basis(size: float) -> tuple[Point, Point]:
    """Return the lattice that lays regular decagons edge to edge."""
    reach = size / math.tan(math.pi / 10.0)
    return ((reach, 0.0), (reach * math.cos(math.tau / 5.0), reach * math.sin(math.tau / 5.0)))


@register("girih.tenfold", family="girih", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class TenfoldGirih(LatticeTiling):
    """Regular decagons laid edge to edge, with a bowtie in every gap.

    The girih tiling a craftsman would chalk on the wall before drawing
    anything: two of the five tiles, repeating. The decagons touch along four
    of their ten edges and the bowtie fills what is left, which it does
    exactly, since it was cut from the same set.

    Parameters
    ----------
    size : float, optional
        Side length, shared by both tiles.
    """

    size: float = 26.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        return _tenfold_basis(self.size)

    @override
    def cell(self) -> Design:
        return _closed(*_decagon_cell(self.size))


@register("girih.interlocking-decagons", family="girih", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class InterlockingDecagons(LatticeTiling):
    """The pattern the tenfold tiling carries: ten-pointed stars, interlocked.

    Hankin's rule applied to :class:`TenfoldGirih`. Each decagon turns into a
    ten-pointed star and each bowtie into the straps that tie four of them
    together. The tiles themselves are gone -- the lines cross their edges
    dead straight, because both tiles meet the shared midpoint at the same
    angle from opposite sides, so the two halves are exactly opposite.

    Parameters
    ----------
    size : float, optional
        Side length of the tiles underneath.
    contact : float, optional
        Angle the strapwork makes with each edge, in radians. Turning it down
        makes the stars sharper and the pattern more open.
    """

    size: float = 26.0
    contact: float = GIRIH_CONTACT

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if not 0.0 < self.contact < math.pi / 2.0:
            raise ValueError(
                f"{owner} contact must be strictly between 0 and pi/2 radians, got "
                f"{self.contact}; outside that the strapwork leaves the tile"
            )

    @override
    def basis(self) -> tuple[Point, Point]:
        return _tenfold_basis(self.size)

    @override
    def cell(self) -> Design:
        paths = tuple(
            path
            for corners in _decagon_cell(self.size)
            for path in _strapwork(corners, self.contact)
        )
        return Design(paths)


# --- six-fold ---------------------------------------------------------------


@register("girih.hex-star", family="girih", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class HexStarLattice(LatticeTiling):
    """Six-pointed stars on a triangular lattice, rhombi filling the gaps.

    The six-fold pattern that needs no strapwork: the stars and the rhombi are
    already the design. Three rhombi to a star, and the star takes two thirds
    of the plane -- the tests check that by area rather than by eye.

    Parameters
    ----------
    size : float, optional
        Edge length, shared by the star and the rhombi.
    """

    size: float = 30.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        pitch = 3.0 * self.size
        return ((pitch, 0.0), (pitch / 2.0, pitch * _ROOT3 / 2.0))

    @override
    def cell(self) -> Design:
        size = self.size
        star: list[Point] = []
        for i in range(6):
            # Points out at 30 degrees and multiples of 60 from there; the
            # concave corners between them are the plain hexagon's own.
            point = math.pi / 6.0 + i * math.pi / 3.0
            star.append((size * _ROOT3 * math.cos(point), size * _ROOT3 * math.sin(point)))
            valley = point + math.pi / 6.0
            star.append((size * math.cos(valley), size * math.sin(valley)))

        # One rhombus sits on the ray through a star point, reaching from that
        # point to the point of the next star along. The other two are the
        # same rhombus turned by a third of a revolution.
        template = (
            (_ROOT3, 0.0),
            (1.5 * _ROOT3, -0.5),
            (2.0 * _ROOT3, 0.0),
            (1.5 * _ROOT3, 0.5),
        )
        rhombi = []
        for third in range(3):
            angle = math.pi / 6.0 + third * math.tau / 3.0
            cos, sin = math.cos(angle), math.sin(angle)
            rhombi.append(
                tuple((size * (x * cos - y * sin), size * (x * sin + y * cos)) for x, y in template)
            )
        return _closed(tuple(star), *rhombi)


# --- rosettes on a lattice --------------------------------------------------


@register("girih.rosette-tiling", family="girih", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class RosetteTiling(LatticeTiling):
    """A field of rosettes, touching point to point.

    What a whole wall looks like rather than one medallion. The lattice is
    square or triangular; on the triangular one a six-pointed rosette meets
    its neighbours at every point, which is the arrangement most tiled
    courtyards use.

    Parameters
    ----------
    points, sharpness, layers : int, optional
        Passed straight to :class:`Rosette`.
    radius : float, optional
        Circumradius of each rosette. Neighbours are two radii apart, so
        their points touch.
    lattice : str, optional
        ``"hex"`` for the triangular lattice, ``"square"`` for the square one.
    """

    points: int = 6
    sharpness: int = 2
    layers: int = 2
    radius: float = 45.0
    lattice: Literal["hex", "square"] = "hex"

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.radius, name="radius")
        if self.lattice not in ("hex", "square"):
            raise ValueError(f"{owner} lattice must be 'hex' or 'square', got {self.lattice!r}")
        # Building one rejects a bad points/sharpness/layers combination with
        # the message that names the real parameter, rather than a later one
        # about an outline the lattice could not place.
        self.unit()

    def unit(self) -> Rosette:
        """Return the rosette this tiling repeats."""
        return Rosette(
            points=self.points,
            sharpness=self.sharpness,
            layers=self.layers,
            radius=self.radius,
        )

    @override
    def basis(self) -> tuple[Point, Point]:
        pitch = 2.0 * self.radius
        if self.lattice == "square":
            return ((pitch, 0.0), (0.0, pitch))
        return ((pitch, 0.0), (pitch / 2.0, pitch * _ROOT3 / 2.0))

    @override
    def cell(self) -> Design:
        return self.unit().build()
