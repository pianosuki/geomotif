"""Tilings: the periodic ones, the aperiodic ones, and one that rolls dice.

Three ways of covering the plane, and the difference between them is worth
knowing before you pick a class.

A **periodic** tiling has a unit cell and two translations that repeat it
forever. Say what one cell looks like and where the next one goes, and the
lattice does the rest -- that is :class:`~geomotif.LatticeTiling`, and it is
what the square, triangular, hexagonal, rhombille, Cairo, truncated-square,
snub-square and herringbone tilings here are. They need a
:attr:`~geomotif.LatticeTiling.region` to fill, because otherwise they would
run on forever.

An **aperiodic** tiling never repeats. There is no cell to stamp, so instead a
handful of seed tiles are replaced by smaller copies of themselves, over and
over -- :class:`~geomotif.SubstitutionTiling`. Both Penrose tilings are built
that way, from the same two Robinson triangles: the kite and the dart of
:class:`PenroseP2` are those triangles glued along a *leg*, and the thin and
thick rhombs of :class:`PenroseP3` are the same triangles glued along their
*base*. One pair of shapes, two famous tilings.

:class:`AmmannBeenker` is aperiodic too but arrives a third way, by de
Bruijn's multigrid: four families of parallel lines are laid across each
other, and every crossing becomes a tile. It is a plain
:class:`~geomotif.Motif` rather than a substitution because the eightfold
inflation rule needs seven tiles placed by hand in bookkeeping that is far
easier to get subtly wrong than a line arrangement is, and the crossings can
be checked directly: every tile it emits is a unit rhomb.

:class:`TruchetTiling` is periodic in its lattice and random in its contents,
which is exactly the thing :class:`~geomotif.LatticeTiling` cannot express --
one cell, stamped everywhere. So it places its own cells, and seeds its own
generator so a given seed always draws the same tiles.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import LatticeTiling, SubstitutionTiling
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Bounds, Design, Path
from ._common import arc_points, ring_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "AmmannBeenker",
    "CairoPentagonal",
    "HerringboneTiling",
    "HexagonalTiling",
    "PenroseP2",
    "PenroseP3",
    "RhombilleTiling",
    "SnubSquare",
    "SquareTiling",
    "TriangularTiling",
    "TruchetTiling",
    "TruncatedSquare",
]

#: A 300x300 square about the origin: what every periodic tiling here fills
#: in the gallery and in the conformance suite.
_EXAMPLE_REGION = Bounds(-150.0, -150.0, 150.0, 150.0)

#: Height of an equilateral triangle of unit side, which is also the
#: half-height of a unit-circumradius hexagon. It appears in four of the
#: lattices below.
_ROOT3_HALF = math.sqrt(3.0) / 2.0

#: Golden ratio. The Penrose substitutions divide by it and nothing else.
_PHI = (1.0 + math.sqrt(5.0)) / 2.0

#: Ceiling on a multigrid's crossings, so a mistyped radius raises rather
#: than filling memory with rhombs.
_MAX_RHOMBS = 100_000


def _check_size(owner: str, size: float, *, name: str = "size") -> None:
    """Reject a tile dimension that would collapse or invert the lattice."""
    if size <= 0.0:
        raise ValueError(f"{owner} {name} must be > 0, got {size}")


def _square(center: Point, half: float) -> tuple[Point, ...]:
    """Return the corners of an axis-aligned square, counter-clockwise."""
    cx, cy = center
    return (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )


def _closed(*outlines: Sequence[Point]) -> Design:
    """Return a design of one closed path per outline. The usual cell."""
    return Design(tuple(Path(tuple(corners), closed=True) for corners in outlines))


# --- periodic ---------------------------------------------------------------


@register("tiling.square", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class SquareTiling(LatticeTiling):
    """Squares edge to edge: the graph paper of tilings.

    Parameters
    ----------
    size : float, optional
        Length of a side.
    """

    size: float = 40.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        return ((self.size, 0.0), (0.0, self.size))

    @override
    def cell(self) -> Design:
        return _closed(_square((0.0, 0.0), self.size / 2.0))


@register("tiling.triangular", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class TriangularTiling(LatticeTiling):
    """Equilateral triangles, alternately point up and point down.

    The cell is one of each, which together make the rhombus that repeats.

    Parameters
    ----------
    size : float, optional
        Length of a side.
    """

    size: float = 40.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        s = self.size
        return ((s, 0.0), (s / 2.0, s * _ROOT3_HALF))

    @override
    def cell(self) -> Design:
        s, h = self.size, self.size * _ROOT3_HALF
        return _closed(
            ((0.0, 0.0), (s, 0.0), (s / 2.0, h)),
            ((s, 0.0), (1.5 * s, h), (s / 2.0, h)),
        )


@register("tiling.hexagonal", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class HexagonalTiling(LatticeTiling):
    """The honeycomb: regular hexagons, three to a corner.

    Parameters
    ----------
    size : float, optional
        Distance from a hexagon's middle to one of its corners, which is
        also the length of a side.
    """

    size: float = 40.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        s, h = self.size, self.size * _ROOT3_HALF
        return ((1.5 * s, h), (0.0, 2.0 * h))

    @override
    def cell(self) -> Design:
        return _closed(ring_points(6, self.size))


@register("tiling.rhombille", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class RhombilleTiling(LatticeTiling):
    """Tumbling blocks: each hexagon split into three rhombi.

    The oldest optical illusion in tiling. Every rhombus is a face of a cube
    seen in isometric projection, and which cubes stick out and which are
    hollow is up to the eye.

    Parameters
    ----------
    size : float, optional
        Side of a rhombus, which is also the hexagon's circumradius.
    """

    size: float = 40.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        s, h = self.size, self.size * _ROOT3_HALF
        return ((1.5 * s, h), (0.0, 2.0 * h))

    @override
    def cell(self) -> Design:
        # Joining the middle to every other corner cuts the hexagon into
        # three rhombi; joining it to all six would give six triangles.
        corners = ring_points(6, self.size)
        return _closed(
            *(
                ((0.0, 0.0), corners[i], corners[(i + 1) % 6], corners[(i + 2) % 6])
                for i in (0, 2, 4)
            )
        )


@register("tiling.cairo", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class CairoPentagonal(LatticeTiling):
    """The Cairo tiling: pentagons in fours, spinning like a pinwheel.

    Named for the paving of Cairo's streets. The pentagon has four equal
    sides and one shorter, two right angles and three of 120 degrees -- the
    right angles are where four pentagons meet head on, and the rest is where
    three do.

    Parameters
    ----------
    size : float, optional
        Length of one of the four equal sides.
    """

    size: float = 34.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        # A square lattice turned 45 degrees. Its cell holds four pentagons,
        # which is exactly the pinwheel below.
        reach = math.sqrt(3.0) * self.size
        return ((reach, reach), (reach, -reach))

    @override
    def cell(self) -> Design:
        s = self.size
        # The pentagon, apex up, with the right-angled corner it spins about
        # moved to the origin.
        apex = (0.0, 0.0)
        right = (s * _ROOT3_HALF, -s / 2.0)
        corners = (
            apex,
            right,
            (s * (math.sqrt(3.0) - 1.0) / 2.0, -s * (0.5 + _ROOT3_HALF)),
            (-s * (math.sqrt(3.0) - 1.0) / 2.0, -s * (0.5 + _ROOT3_HALF)),
            (-s * _ROOT3_HALF, -s / 2.0),
        )
        about = tuple((x - right[0], y - right[1]) for x, y in corners)
        return _closed(
            *(
                tuple(
                    (
                        x * math.cos(quarter * math.pi / 2.0)
                        - y * math.sin(quarter * math.pi / 2.0),
                        x * math.sin(quarter * math.pi / 2.0)
                        + y * math.cos(quarter * math.pi / 2.0),
                    )
                    for x, y in about
                )
                for quarter in range(4)
            )
        )


@register("tiling.truncated-square", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class TruncatedSquare(LatticeTiling):
    """Octagons with small squares in the gaps -- the 4.8.8 tiling.

    What you get by cutting the corners off every square of a square tiling:
    the squares become octagons and the cut corners leave a smaller square
    behind, stood on its point.

    Parameters
    ----------
    size : float, optional
        Length of a side, shared by both shapes.
    """

    size: float = 34.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        span = self.size * (1.0 + math.sqrt(2.0))
        return ((span, 0.0), (0.0, span))

    @override
    def cell(self) -> Design:
        s = self.size
        span = s * (1.0 + math.sqrt(2.0))
        radius = s / (2.0 * math.sin(math.pi / 8.0))
        gap = span / 2.0
        # Corners at 22.5 degrees put the octagon's flat sides square on to
        # its four neighbours, which is what leaves a diamond in the gap.
        return _closed(
            ring_points(8, radius, rotation=math.pi / 8.0),
            ring_points(4, s / math.sqrt(2.0), center=(gap, gap)),
        )


@register("tiling.snub-square", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class SnubSquare(LatticeTiling):
    """Squares and triangles, two of each at every corner -- the 3.3.4.3.4.

    The squares come in two orientations thirty degrees apart, and the
    triangles pair up into rhombi that fill what is left. Four triangles and
    two squares repeat.

    Parameters
    ----------
    size : float, optional
        Length of a side, shared by both shapes.
    """

    size: float = 34.0

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.size)

    @override
    def basis(self) -> tuple[Point, Point]:
        s, h = self.size, self.size * _ROOT3_HALF
        return ((s / 2.0, -s - h), (s + h, s / 2.0))

    @override
    def cell(self) -> Design:
        s, h = self.size, self.size * _ROOT3_HALF
        return _closed(
            ((0.0, 0.0), (s, 0.0), (s, s), (0.0, s)),
            ((0.0, 0.0), (s / 2.0, -h), (s / 2.0 - h, -h - s / 2.0), (-h, -s / 2.0)),
            # Each rhombus of the gap, cut along its short diagonal.
            ((0.0, 0.0), (s, 0.0), (s / 2.0, -h)),
            ((s, 0.0), (1.5 * s, -h), (s / 2.0, -h)),
            ((0.0, 0.0), (0.0, s), (-h, s / 2.0)),
            ((0.0, 0.0), (-h, s / 2.0), (-h, -s / 2.0)),
        )


@register("tiling.herringbone", family="tiling", example={"region": _EXAMPLE_REGION})
@dataclass(frozen=True, slots=True)
class HerringboneTiling(LatticeTiling):
    """Rectangles laid in chevrons, each one's end against the next one's side.

    The parquet floor and the brick path. Any proportion works, not only the
    usual two-to-one: the lattice follows from the brick.

    Parameters
    ----------
    length, width : float, optional
        The brick's two sides.
    """

    length: float = 60.0
    width: float = 30.0

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.length, name="length")
        _check_size(owner, self.width, name="width")

    @override
    def basis(self) -> tuple[Point, Point]:
        # A step of one width up and across lands on the next brick of the
        # same orientation; a step of one length across and down does too.
        return ((self.width, self.width), (self.length, -self.length))

    @override
    def cell(self) -> Design:
        length, width = self.length, self.width
        return _closed(
            ((0.0, 0.0), (length, 0.0), (length, width), (0.0, width)),
            ((0.0, width), (width, width), (width, width + length), (0.0, width + length)),
        )


# --- chance -----------------------------------------------------------------


@register("tiling.truchet", family="tiling", example={"cols": 6, "rows": 6})
@dataclass(frozen=True, slots=True)
class TruchetTiling(Motif):
    """Quarter-circles in square cells, each turned at random.

    Two arcs cross every cell, joining the midpoints of its sides; whether
    they curl one way or the other is decided by the toss of a coin. The arcs
    always meet at cell borders, so what comes out is a single tangle of
    smooth curves -- Sebastien Truchet's tiles of 1704, and still the cheapest
    way to make a plotter draw something that looks designed.

    Parameters
    ----------
    size : float, optional
        Side of one cell.
    cols, rows : int, optional
        How many cells across and down.
    seed : int, optional
        Fixes the tosses. The same seed always draws the same tiles, and the
        generator is private to the call, so nothing else in the program can
        change what you get.
    center : (float, float), optional
        Middle of the finished patch.
    """

    size: float = 30.0
    cols: int = 10
    rows: int = 10
    seed: int = 0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if self.cols < 1 or self.rows < 1:
            raise ValueError(f"{owner} needs at least one cell, got {self.cols}x{self.rows}")

    @override
    def build(self) -> Design:
        rng = random.Random(self.seed)
        s = self.size
        cx, cy = self.center
        x0 = cx - self.cols * s / 2.0
        y0 = cy - self.rows * s / 2.0
        paths: list[Path] = []
        for row in range(self.rows):
            for col in range(self.cols):
                left, bottom = x0 + col * s, y0 + row * s
                # Either the two arcs hug the down-left and up-right corners,
                # or the other diagonal pair. Nothing else is a Truchet tile.
                pairs = (
                    (((left, bottom), 0.0), ((left + s, bottom + s), math.pi))
                    if rng.random() < 0.5
                    else (((left + s, bottom), math.pi / 2.0), ((left, bottom + s), -math.pi / 2.0))
                )
                paths.extend(
                    Path(arc_points(corner, s / 2.0, start, math.pi / 2.0))
                    for corner, start in pairs
                )
        return Design(tuple(paths), meta=spec(self))


# --- aperiodic --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RobinsonTriangle:
    """Half of a Penrose tile: an isosceles triangle in the complex plane.

    Two shapes only. ``kind`` 0 is the acute one, 36-72-72, whose legs are
    ``phi`` times its base; ``kind`` 1 is the obtuse one, 36-36-108, whose
    base is ``phi`` times its legs. Everything Penrose is made of these.

    :attr:`apex` is the corner between the two legs. What :attr:`first` and
    :attr:`second` mean depends on the tiling: :class:`PenroseP3` glues
    triangles along the base :attr:`first`--:attr:`second`, and
    :class:`PenroseP2` glues them along the leg :attr:`apex`--:attr:`first`.

    Complex numbers rather than points because the substitution is entirely
    ``a + (b - a) / phi`` -- one expression each way, instead of one per
    coordinate, with the rotations falling out of the arithmetic.
    """

    kind: int
    apex: complex
    first: complex
    second: complex


@dataclass(frozen=True, slots=True)
class PenroseTiling(SubstitutionTiling[RobinsonTriangle]):
    """Shared scaffolding for the two Penrose tilings: the seed and the scale.

    The seed is ten acute triangles in a wheel, which is five whole tiles
    however they are glued -- five thick rhombs for :class:`PenroseP3`, five
    kites for :class:`PenroseP2`. Subclasses supply the substitution rule and
    say which edges to draw.
    """

    radius: float = 160.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_size(type(self).__name__, self.radius, name="radius")

    @override
    def seed(self) -> Iterable[RobinsonTriangle]:
        cx, cy = self.center
        middle = complex(cx, cy)
        for i in range(10):
            first = middle + self.radius * complex(
                math.cos((2 * i - 1) * math.pi / 10.0), math.sin((2 * i - 1) * math.pi / 10.0)
            )
            second = middle + self.radius * complex(
                math.cos((2 * i + 1) * math.pi / 10.0), math.sin((2 * i + 1) * math.pi / 10.0)
            )
            # Alternate the handedness so neighbouring triangles face each
            # other and pair into whole tiles rather than all leaning one way.
            if i % 2 == 0:
                first, second = second, first
            yield RobinsonTriangle(0, middle, first, second)

    def _stroke(self, *corners: complex) -> Path:
        return Path(tuple((z.real, z.imag) for z in corners))


@register("tiling.penrose-p3", family="tiling", example={"depth": 4})
@dataclass(frozen=True, slots=True)
class PenroseP3(PenroseTiling):
    """Penrose's rhombs: one thin, one thick, and no repeating pattern ever.

    Each rhombus is two Robinson triangles glued along their base, so the
    strokes drawn are the legs -- draw the base as well and every tile would
    have a line down its middle.

    Parameters
    ----------
    depth : int, optional
        Subdivision rounds. Tile count grows by about ``phi**2`` a round.
    radius : float, optional
        Circumradius of the starting wheel, and so of the finished patch.
    center : (float, float), optional
        Middle of the wheel.
    """

    depth: int = field(default=5, kw_only=True)

    @override
    def subdivide(self, tile: RobinsonTriangle) -> Iterable[RobinsonTriangle]:
        a, b, c = tile.apex, tile.first, tile.second
        if tile.kind == 0:
            split = a + (b - a) / _PHI
            yield RobinsonTriangle(0, c, split, b)
            yield RobinsonTriangle(1, split, c, a)
        else:
            near = b + (a - b) / _PHI
            far = b + (c - b) / _PHI
            yield RobinsonTriangle(1, far, c, a)
            yield RobinsonTriangle(1, near, far, b)
            yield RobinsonTriangle(0, far, near, a)

    @override
    def outline(self, tile: RobinsonTriangle) -> Iterable[Path]:
        yield self._stroke(tile.first, tile.apex, tile.second)


@register("tiling.penrose-p2", family="tiling", example={"depth": 4})
@dataclass(frozen=True, slots=True)
class PenroseP2(PenroseTiling):
    """Penrose's kite and dart, the tiling that cannot repeat.

    Each tile is two Robinson triangles glued along a *leg* rather than a
    base: two acute ones make a kite, two obtuse ones make a dart. The same
    two triangles glued the other way give :class:`PenroseP3`, which is why
    both live here.

    Parameters
    ----------
    depth : int, optional
        Subdivision rounds. Tile count grows by about ``phi**2`` a round.
    radius : float, optional
        Circumradius of the starting wheel, and so of the finished patch.
    center : (float, float), optional
        Middle of the wheel.
    """

    depth: int = field(default=5, kw_only=True)

    @override
    def subdivide(self, tile: RobinsonTriangle) -> Iterable[RobinsonTriangle]:
        a, axis, other = tile.apex, tile.first, tile.second
        if tile.kind == 0:
            # A kite half breaks into a whole smaller kite -- the two acute
            # children, which face each other across apex--near -- plus one
            # obtuse child that pairs with its mirror image across the axis
            # and so completes a dart straddling it.
            near = a + (axis - a) / (_PHI * _PHI)
            far = a + (other - a) / _PHI
            yield RobinsonTriangle(1, near, a, far)
            yield RobinsonTriangle(0, axis, far, near)
            yield RobinsonTriangle(0, axis, far, other)
        else:
            split = other + (axis - other) / _PHI
            yield RobinsonTriangle(0, other, split, a)
            yield RobinsonTriangle(1, split, axis, a)

    @override
    def outline(self, tile: RobinsonTriangle) -> Iterable[Path]:
        # Skip apex--first: that is the glue seam down the middle of the tile.
        yield self._stroke(tile.apex, tile.second, tile.first)


@register("tiling.ammann-beenker", family="tiling", example={"radius": 110.0})
@dataclass(frozen=True, slots=True)
class AmmannBeenker(Motif):
    """The octagonal quasicrystal: squares and 45-degree rhombs, never repeating.

    Built by de Bruijn's multigrid rather than by substitution. Four families
    of evenly spaced parallel lines are drawn across each other at 45 degrees;
    every crossing of a line from one family with a line from another names
    one tile, and the tile is the rhombus spanned by those two families'
    directions. Families a right angle apart give the squares, families 45
    degrees apart give the rhombs, and there is nothing else -- which is a
    property you can check on the output rather than trust.

    Parameters
    ----------
    size : float, optional
        Edge length, shared by the square and the rhomb.
    radius : float, optional
        How far from the middle to tile. Tiles whose middle falls outside are
        dropped, so the patch comes out round.
    offsets : tuple of float, optional
        Where each family of lines sits relative to the origin. These choose
        which tiling of the family you get; every choice is locally the same
        as every other, and the default is the eightfold symmetric one.
    center : (float, float), optional
        Middle of the patch.
    """

    #: One direction per line family, a fixed 45 degrees apart. Four of them
    #: give eight directions once their opposites are counted, which is where
    #: the eightfold symmetry comes from.
    families: ClassVar[int] = 4

    size: float = 16.0
    radius: float = 150.0
    offsets: tuple[float, ...] = (0.5, 0.5, 0.5, 0.5)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        _check_size(owner, self.radius, name="radius")
        if len(self.offsets) != self.families:
            raise ValueError(
                f"{owner} needs one offset per line family: expected "
                f"{self.families}, got {len(self.offsets)}"
            )

    def rhombs(self) -> tuple[tuple[Point, ...], ...]:
        """Return every tile as its four corners, counter-clockwise.

        Exposed because the tiles themselves are often what you want -- to
        count them, to sort squares from rhombs, or to color them.
        """
        n = self.families
        step = self.radius / self.size
        reach = math.ceil(step) + 2
        crossings = (2 * reach + 1) ** 2 * (n * (n - 1) // 2)
        if crossings > _MAX_RHOMBS:
            raise ValueError(
                f"{type(self).__name__} would test {crossings} line crossings "
                f"(limit {_MAX_RHOMBS}); use a larger size or a smaller radius"
            )

        directions = [(math.cos(math.pi * j / n), math.sin(math.pi * j / n)) for j in range(n)]
        cx, cy = self.center
        tiles: list[tuple[Point, ...]] = []
        for j in range(n):
            for k in range(j + 1, n):
                (jx, jy), (kx, ky) = directions[j], directions[k]
                det = jx * ky - jy * kx
                for a in range(-reach, reach + 1):
                    for b in range(-reach, reach + 1):
                        pa, pb = a + self.offsets[j], b + self.offsets[k]
                        # Where the two lines cross, in units of `size`.
                        px = (pa * ky - pb * jy) / det
                        py = (pb * jx - pa * kx) / det
                        # Which side of every *other* family that crossing
                        # falls on names the tile's corner on the lattice.
                        index = [
                            math.ceil(px * dx + py * dy - self.offsets[i])
                            for i, (dx, dy) in enumerate(directions)
                        ]
                        index[j], index[k] = a, b
                        vx = math.fsum(index[i] * directions[i][0] for i in range(n))
                        vy = math.fsum(index[i] * directions[i][1] for i in range(n))
                        corners = (
                            (vx, vy),
                            (vx + jx, vy + jy),
                            (vx + jx + kx, vy + jy + ky),
                            (vx + kx, vy + ky),
                        )
                        mx = math.fsum(x for x, _ in corners) / 4.0
                        my = math.fsum(y for _, y in corners) / 4.0
                        if math.hypot(mx, my) * self.size > self.radius:
                            continue
                        tiles.append(
                            tuple((cx + x * self.size, cy + y * self.size) for x, y in corners)
                        )
        return tuple(tiles)

    @override
    def build(self) -> Design:
        tiles = self.rhombs()
        if not tiles:
            raise ValueError(
                f"{type(self).__name__} covered nothing: radius {self.radius} is "
                f"smaller than one tile of size {self.size}"
            )
        return Design(tuple(Path(corners, closed=True) for corners in tiles), meta=spec(self))
