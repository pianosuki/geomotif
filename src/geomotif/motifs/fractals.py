"""Fractals: the same shape at every scale, reached three different ways.

Three constructions share this page because they produce the same kind of
object by very different means, and the difference is worth seeing:

* **Grammars.** Koch, Hilbert, Gosper, the dragons and the Sierpinski curves
  are each an axiom, a rewrite rule and a turn angle, drawn with a turtle --
  see :class:`~geomotif.LSystemMotif`. Every one of them below is four lines.
* **Recursion.** :class:`SierpinskiCarpet`, :class:`CantorSet`,
  :class:`PythagorasTree`, :class:`HTree` and :class:`ApollonianGasket` are
  shapes that place *smaller copies of themselves*, which is a statement about
  squares and circles rather than about a path, so they are built directly.
* **Chance.** :class:`IFSAttractor` and :class:`BarnsleyFern` play the chaos
  game: pick one contracting map at random, apply it, plot the point, repeat.
  The attractor appears without ever being drawn, and comes back as loose
  points rather than as a stroke.

A grammar fractal is sized by its :attr:`~geomotif.LSystemMotif.step`, which
is the length of *one* turtle move -- so its overall size is that step times a
power of the grammar's scale factor, and it changes when you change the depth.
That is the nature of the construction rather than an oversight; call
:meth:`~geomotif.Design.fit` when you need a fractal at a particular size. The
recursive and chaos-game motifs are not built a step at a time and do take a
plain ``size``.
"""

from __future__ import annotations

import bisect
import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import LSystemMotif, PolygonMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.transform import Affine
from ..core.types import Bounds, Design, Path
from ._common import arc_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from ..core.types import Point

__all__ = [
    "ApollonianGasket",
    "BarnsleyFern",
    "CantorSet",
    "DragonCurve",
    "GosperCurve",
    "HTree",
    "HilbertCurve",
    "IFSAttractor",
    "IFSMap",
    "KochAntisnowflake",
    "KochCurve",
    "KochSnowflake",
    "LevyCCurve",
    "MinkowskiIsland",
    "MinkowskiSausage",
    "MooreCurve",
    "PeanoCurve",
    "PythagorasTree",
    "SierpinskiArrowhead",
    "SierpinskiCarpet",
    "SierpinskiTriangle",
    "Terdragon",
    "TwinDragon",
    "VicsekFractal",
]

# --- grammars ---------------------------------------------------------------


@register("fractal.koch", family="fractal")
@dataclass(frozen=True, slots=True)
class KochCurve(LSystemMotif):
    """The original: replace the middle third of every segment with a spike.

    Helge von Koch's 1904 curve, published as an example of something
    continuous that has a tangent nowhere. Each round quadruples the segment
    count while thirding the length, so the curve between two fixed points
    grows without limit -- which is the whole point of it.
    """

    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F--F+F"}
    angle = math.pi / 3


@register("fractal.koch-snowflake", family="fractal")
@dataclass(frozen=True, slots=True)
class KochSnowflake(LSystemMotif):
    """Three Koch curves around a triangle: finite area, infinite perimeter.

    The perimeter multiplies by 4/3 every round and never stops; the area
    converges to exactly 8/5 of the starting triangle. Both facts are easy to
    check on the geometry this builds, and the test suite does.
    """

    axiom = "F--F--F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F--F+F"}
    angle = math.pi / 3
    closed = True


@register("fractal.koch-antisnowflake", family="fractal")
@dataclass(frozen=True, slots=True)
class KochAntisnowflake(LSystemMotif):
    """The snowflake with its spikes turned inward, which is a different shape.

    One sign change in the rule, and the star becomes three bites taken out of
    a triangle. Worth having next to :class:`KochSnowflake` precisely because
    the grammars differ by so little and the results by so much.
    """

    axiom = "F--F--F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F-F++F-F"}
    angle = math.pi / 3
    closed = True


@register("fractal.minkowski", family="fractal")
@dataclass(frozen=True, slots=True)
class MinkowskiSausage(LSystemMotif):
    """Koch's idea on a square grid: a battlement instead of a spike.

    Every segment becomes eight of a quarter the length, all of them axis
    aligned, which makes it the fractal of choice when the output has to look
    deliberate rather than organic. Eight pieces at a quarter scale puts its
    dimension at exactly three halves.
    """

    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F-F-FF+F+F-F"}
    angle = math.pi / 2
    depth: int = field(default=3, kw_only=True)


@register("fractal.minkowski-island", family="fractal")
@dataclass(frozen=True, slots=True)
class MinkowskiIsland(LSystemMotif):
    """Four Minkowski sausages around a square: the quadratic Koch island.

    What :class:`KochSnowflake` is to :class:`KochCurve`. The coastline never
    stops growing while the area it encloses stays exactly that of the
    starting square, which is the tidiest statement of the coastline paradox
    there is.
    """

    axiom = "F+F+F+F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F-F-FF+F+F-F"}
    angle = math.pi / 2
    closed = True
    depth: int = field(default=3, kw_only=True)


@register("fractal.sierpinski-triangle", family="fractal")
@dataclass(frozen=True, slots=True)
class SierpinskiTriangle(LSystemMotif):
    """The gasket, drawn as one unbroken stroke that closes on itself.

    The triangle with its middle removed, then again, forever. Drawing it
    without lifting the pen is the trick the grammar performs: the naive
    construction is a pile of separate triangles, while this is a single
    closed path that happens to trace all of them.

    The same set of points falls out of :class:`IFSAttractor` played as a
    chaos game -- one arrives as a stroke, the other as a cloud.
    """

    axiom = "F+G+G"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+G-F-G+F", "G": "GG"}
    angle = math.tau / 3
    closed = True
    depth: int = field(default=5, kw_only=True)


@register("fractal.sierpinski-arrowhead", family="fractal")
@dataclass(frozen=True, slots=True)
class SierpinskiArrowhead(LSystemMotif):
    """The gasket approached along a curve instead of through a triangle.

    Two rules that swap roles at every round, tracing an open path from one
    corner of the gasket to another. The limit is the same set as
    :class:`SierpinskiTriangle`, reached by a route that looks nothing like
    it at any finite depth.
    """

    axiom = "A"
    rules: ClassVar[Mapping[str, str]] = {"A": "B-A-B", "B": "A+B+A"}
    angle = math.pi / 3
    depth: int = field(default=6, kw_only=True)


@register("fractal.dragon", family="fractal")
@dataclass(frozen=True, slots=True)
class DragonCurve(LSystemMotif):
    """The Heighway dragon: fold a strip of paper in half, repeatedly, unfold.

    Every crease is a right angle and the curve never crosses itself, which is
    far from obvious at any depth past about six. Four dragons fit together
    around a point with no gap, so the shape tiles the plane.
    """

    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+G", "G": "F-G"}
    angle = math.pi / 2
    depth: int = field(default=10, kw_only=True)


@register("fractal.twindragon", family="fractal")
@dataclass(frozen=True, slots=True)
class TwinDragon(LSystemMotif):
    """Two Heighway dragons back to back, enclosing a region that tiles.

    The Davis-Knuth dragon. Joining the pair closes the curve, and the region
    inside it is the fundamental domain of the base -1+i number system -- the
    reason this shape turns up in radix arithmetic as well as in art.
    """

    axiom = "F+F+"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+G", "G": "F-G"}
    angle = math.pi / 2
    closed = True
    depth: int = field(default=9, kw_only=True)


@register("fractal.terdragon", family="fractal")
@dataclass(frozen=True, slots=True)
class Terdragon(LSystemMotif):
    """The dragon done in thirds: one segment becomes three at 120 degrees.

    Threefold rather than twofold symmetry, and a much lacier result than the
    Heighway curve for the same number of segments.
    """

    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F-F"}
    angle = math.tau / 3
    depth: int = field(default=6, kw_only=True)


@register("fractal.levy-c", family="fractal")
@dataclass(frozen=True, slots=True)
class LevyCCurve(LSystemMotif):
    """Paul Levy's C curve: two half-size copies at right angles, forever.

    It starts as a simple bracket and turns into a cauliflower. Unlike the
    dragons it overlaps itself freely, which is what gives the finished curve
    its dense, ruffled edge.
    """

    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "+F--F+"}
    angle = math.pi / 4
    depth: int = field(default=10, kw_only=True)


@register("fractal.hilbert", family="fractal")
@dataclass(frozen=True, slots=True)
class HilbertCurve(LSystemMotif):
    """The space-filling curve that keeps neighbours together.

    Hilbert's curve visits every cell of a square grid, and two cells close
    along the curve are always close on the plane. That property is why it is
    the standard order for laying out image tiles, database keys and anything
    else where locality has to survive being flattened to one dimension.

    ``X`` and ``Y`` drive the rewriting without ever drawing: the turtle only
    moves on ``F``.
    """

    axiom = "X"
    rules: ClassVar[Mapping[str, str]] = {"X": "+YF-XFX-FY+", "Y": "-XF+YFY+FX-"}
    angle = math.pi / 2
    depth: int = field(default=5, kw_only=True)


@register("fractal.moore", family="fractal")
@dataclass(frozen=True, slots=True)
class MooreCurve(LSystemMotif):
    """Hilbert's curve closed into a loop.

    Four Hilbert curves arranged so the walk returns to where it began, which
    makes it the space-filling curve to use when the traversal has to be
    cyclic rather than to start and stop somewhere.
    """

    axiom = "LFL+F+LFL"
    rules: ClassVar[Mapping[str, str]] = {"L": "-RF+LFL+FR-", "R": "+LF-RFR-FL+"}
    angle = math.pi / 2
    closed = True
    depth: int = field(default=4, kw_only=True)


@register("fractal.peano", family="fractal")
@dataclass(frozen=True, slots=True)
class PeanoCurve(LSystemMotif):
    """The first space-filling curve ever published, from 1890.

    Giuseppe Peano's construction predates Hilbert's by a year and divides the
    square into nine rather than four. It reads as a comb of combs, and it was
    the result that forced mathematics to take the idea of dimension seriously.
    """

    axiom = "X"
    rules: ClassVar[Mapping[str, str]] = {
        "X": "XFYFX+F+YFXFY-F-XFYFX",
        "Y": "YFXFY-F-XFYFX+F+YFXFY",
    }
    angle = math.pi / 2
    depth: int = field(default=3, kw_only=True)


@register("fractal.gosper", family="fractal")
@dataclass(frozen=True, slots=True)
class GosperCurve(LSystemMotif):
    """The flowsnake: a space-filling curve on a hexagonal grid.

    Bill Gosper's curve fills a region whose own boundary is fractal -- the
    Gosper island, which tiles the plane in sevens. The most beautiful thing
    in this module, and it is two rewrite rules.
    """

    axiom = "A"
    rules: ClassVar[Mapping[str, str]] = {
        "A": "A-B--B+A++AA+B-",
        "B": "+A-BB--B-A++A+B",
    }
    angle = math.pi / 3
    depth: int = field(default=4, kw_only=True)


@register("fractal.vicsek", family="fractal")
@dataclass(frozen=True, slots=True)
class VicsekFractal(LSystemMotif):
    """The box fractal: a plus sign made of plus signs.

    Tamas Vicsek's construction, which keeps only the center and the four
    edge-midpoints of each subdivided square. The saltire cross the outline
    traces is what stochastic versions of it are used to model -- percolation
    clusters and diffusion fronts.
    """

    axiom = "F-F-F-F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F-F+F+F-F"}
    angle = math.pi / 2
    closed = True
    depth: int = field(default=3, kw_only=True)


# --- recursion --------------------------------------------------------------

# A recursion this deep is a mistake rather than a design: the shapes below
# multiply by three to eight per level, so a slip of the finger past this
# would spend minutes producing something no output device can resolve.
_MAX_DEPTH = 12


def _check_depth(owner: str, depth: int) -> None:
    """Raise unless ``depth`` is a sane recursion depth."""
    if depth < 0:
        raise ValueError(f"{owner}: depth must be >= 0, got {depth}")
    if depth > _MAX_DEPTH:
        raise ValueError(
            f"{owner}: depth {depth} exceeds the limit of {_MAX_DEPTH}; the shape "
            f"multiplies at every level and would not be resolvable anyway"
        )


def _power(base: int, exponent: int) -> int:
    """Return ``base ** exponent`` as the integer it always is.

    ``int ** int`` is typed as ``Any``, because a negative exponent makes it a
    float. Every exponent below is a validated recursion depth, so the answer
    is always an integer -- and saying so here keeps four counting methods
    honestly typed instead of silently returning ``Any``.
    """
    return int(base**exponent)


def _square(center: Point, side: float) -> tuple[Point, ...]:
    """Return the corners of an axis-aligned square, counter-clockwise."""
    cx, cy = center
    half = side / 2.0
    return (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )


@register("fractal.sierpinski-carpet", family="fractal")
@dataclass(frozen=True, slots=True)
class SierpinskiCarpet(PolygonMotif):
    """A square with its middle ninth removed, then again in each ninth.

    The two-dimensional Cantor set, and the shape whose limit contains a copy
    of every possible one-dimensional curve. Drawn as outlines: the outer
    square plus every hole cut out of it, which is both what a plotter wants
    and what makes the construction legible.

    Parameters
    ----------
    depth : int, optional
        Rounds of subdivision. The hole count is ``(8**depth - 1) / 7``, so
        it climbs fast.
    size : float, optional
        Side of the outer square.
    center : (float, float), optional
        Middle of the carpet.
    """

    depth: int = 4
    size: float = 200.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_depth(type(self).__name__, self.depth)
        if self.size <= 0.0:
            raise ValueError(f"size must be > 0, got {self.size}")

    def hole_count(self) -> int:
        """Return how many holes this carpet has at its depth."""
        return (_power(8, self.depth) - 1) // 7

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        yield _square(self.center, self.size)
        yield from self._holes(self.center, self.size, self.depth)

    def _holes(self, center: Point, side: float, depth: int) -> Iterator[Sequence[Point]]:
        """Yield the hole cut from this square, then the holes of its eight neighbours."""
        if depth < 1:
            return
        third = side / 3.0
        yield _square(center, third)
        cx, cy = center
        for dx in (-third, 0.0, third):
            for dy in (-third, 0.0, third):
                # The middle ninth is the hole just emitted, not a square to
                # subdivide -- everything around it is.
                if dx == 0.0 and dy == 0.0:
                    continue
                yield from self._holes((cx + dx, cy + dy), third, depth - 1)


@register("fractal.cantor", family="fractal")
@dataclass(frozen=True, slots=True)
class CantorSet(PolygonMotif):
    """Take out the middle third. Repeat. Stack the rounds to see it happen.

    The set that survives is uncountable and has length zero, which is the
    single most useful counterexample in analysis. Drawn the way it is always
    drawn: one row of bars per round, so the construction is visible rather
    than just its limit.

    Parameters
    ----------
    depth : int, optional
        Rounds to draw. Round zero is the single unbroken bar, so ``depth``
        rows follow it and the bar count is ``2**(depth + 1) - 1``.
    width : float, optional
        Length of the first bar.
    gap : float, optional
        Vertical distance between consecutive rows.
    center : (float, float), optional
        Middle of the whole stack.
    """

    closed: ClassVar[bool] = False

    depth: int = 6
    width: float = 240.0
    gap: float = 14.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_depth(type(self).__name__, self.depth)
        if self.width <= 0.0:
            raise ValueError(f"width must be > 0, got {self.width}")
        if self.gap <= 0.0:
            raise ValueError(f"gap must be > 0, got {self.gap}")

    def bar_count(self) -> int:
        """Return how many bars this stack draws in total."""
        return _power(2, self.depth + 1) - 1

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        cx, cy = self.center
        top = cy + self.depth * self.gap / 2.0
        spans = [(cx - self.width / 2.0, cx + self.width / 2.0)]
        for row in range(self.depth + 1):
            y = top - row * self.gap
            for lo, hi in spans:
                yield ((lo, y), (hi, y))
            spans = [
                part
                for lo, hi in spans
                for part in ((lo, lo + (hi - lo) / 3.0), (hi - (hi - lo) / 3.0, hi))
            ]


@register("fractal.pythagoras-tree", family="fractal")
@dataclass(frozen=True, slots=True)
class PythagorasTree(PolygonMotif):
    """Squares on the legs of right triangles, all the way up.

    Albert Bosman's 1942 construction, and a picture of the Pythagorean
    theorem rather than an illustration of it: the two child squares have the
    combined area of their parent at every level, whatever the lean, so the
    tree's total area grows by exactly one trunk per level.

    ``lean`` is the angle at the *left* corner of the triangle sitting on each
    square. A quarter of a right angle makes the symmetric tree; anything else
    tips it, and values near zero or a right angle draw a fern-like frond.

    Parameters
    ----------
    depth : int, optional
        Branching rounds. The square count is ``2**(depth + 1) - 1``.
    size : float, optional
        Side of the trunk square.
    lean : float, optional
        Apex angle of the triangle, in radians. Must be strictly between zero
        and a right angle.
    base : (float, float), optional
        Midpoint of the trunk's bottom edge -- where the tree stands.
    """

    depth: int = 8
    size: float = 60.0
    lean: float = math.pi / 4.0
    base: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_depth(type(self).__name__, self.depth)
        if self.size <= 0.0:
            raise ValueError(f"size must be > 0, got {self.size}")
        if not 0.0 < self.lean < math.pi / 2.0:
            raise ValueError(
                f"lean must be strictly between 0 and pi/2 radians, got {self.lean}; "
                f"at either end one of the two children has no area"
            )

    def square_count(self) -> int:
        """Return how many squares this tree draws in total."""
        return _power(2, self.depth + 1) - 1

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        bx, by = self.base
        half = self.size / 2.0
        yield from self._grow((bx - half, by), (bx + half, by), self.depth)

    def _grow(self, left: Point, right: Point, depth: int) -> Iterator[Sequence[Point]]:
        """Yield the square standing on ``left``-``right``, then its two children."""
        (lx, ly), (rx, ry) = left, right
        dx, dy = rx - lx, ry - ly
        # The square is raised on the left-hand side of the base direction, so
        # a base running left to right grows upwards.
        top_left = (lx - dy, ly + dx)
        top_right = (rx - dy, ry + dx)
        yield (left, right, top_right, top_left)

        if depth < 1:
            return
        # The apex sits on the circle with the top edge as diameter -- that is
        # what makes the triangle right-angled, and the two squares built on
        # its legs therefore add up to the one below.
        reach = math.cos(self.lean)
        along, across = reach * math.cos(self.lean), reach * math.sin(self.lean)
        apex = (
            top_left[0] + along * dx - across * dy,
            top_left[1] + along * dy + across * dx,
        )
        yield from self._grow(top_left, apex, depth - 1)
        yield from self._grow(apex, top_right, depth - 1)


@register("fractal.h-tree", family="fractal")
@dataclass(frozen=True, slots=True)
class HTree(PolygonMotif):
    """An H whose serifs are smaller H's, and so on down.

    Each round adds a perpendicular segment at both ends of every existing
    one, shortened by the square root of two so the arms of successive levels
    stay in proportion. It is the standard layout for a clock distribution
    network on a chip, because every leaf is exactly the same wire length from
    the root.

    Parameters
    ----------
    depth : int, optional
        Branching rounds. The segment count is ``2**(depth + 1) - 1``.
    size : float, optional
        Length of the first, longest bar.
    center : (float, float), optional
        Middle of the tree, which is the middle of that first bar.
    """

    closed: ClassVar[bool] = False

    depth: int = 6
    size: float = 220.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_depth(type(self).__name__, self.depth)
        if self.size <= 0.0:
            raise ValueError(f"size must be > 0, got {self.size}")

    def segment_count(self) -> int:
        """Return how many bars this tree draws in total."""
        return _power(2, self.depth + 1) - 1

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        yield from self._branch(self.center, self.size, horizontal=True, depth=self.depth)

    def _branch(
        self, center: Point, length: float, *, horizontal: bool, depth: int
    ) -> Iterator[Sequence[Point]]:
        """Yield one bar and the two smaller, perpendicular ones at its ends."""
        cx, cy = center
        half = length / 2.0
        ends: tuple[Point, Point] = (
            ((cx - half, cy), (cx + half, cy)) if horizontal else ((cx, cy - half), (cx, cy + half))
        )
        yield ends

        if depth < 1:
            return
        for end in ends:
            yield from self._branch(
                end, length / math.sqrt(2.0), horizontal=not horizontal, depth=depth - 1
            )


#: A circle as Descartes' theorem wants it: its curvature, and that curvature
#: times its center taken as a complex number. In these coordinates the fourth
#: circle tangent to three others is plain arithmetic -- see :func:`_sibling`.
type _Circle = tuple[float, complex]

#: The (-1, 2, 2, 3) configuration, the smallest integral gasket there is: a
#: unit circle with two half-circles and a third-circle packed inside it.
_GASKET_SEED: tuple[_Circle, ...] = (
    (-1.0, 0j),
    (2.0, 1j),
    (2.0, -1j),
    (3.0, -2 + 0j),
)

#: Segments used to draw a circle as large as the gasket's outer boundary.
#: Smaller circles get proportionally fewer, down to the floor below, because
#: a circle a hundredth the size does not need a hundredth of a degree of
#: angular resolution to look round.
_GASKET_SEGMENTS = 256
_GASKET_MIN_SEGMENTS = 12

#: The packing is infinite, so depth alone does not bound it -- a deep gasket
#: with a tiny `min_radius` would run for a very long time before running out
#: of memory. This is the backstop that turns that into an error instead.
_MAX_CIRCLES = 20_000


def _sibling(a: _Circle, b: _Circle, c: _Circle, d: _Circle) -> _Circle:
    """Return the other circle tangent to ``a``, ``b`` and ``c`` besides ``d``.

    Descartes' theorem is a quadratic, so three mutually tangent circles admit
    two companions and the two roots sum to twice the rest. Knowing one of
    them therefore gives the other by subtraction, with no square root to take
    and no sign to guess -- which is what makes the gasket cheap to generate.
    """
    return (
        2.0 * (a[0] + b[0] + c[0]) - d[0],
        2.0 * (a[1] + b[1] + c[1]) - d[1],
    )


@register("fractal.apollonian", family="fractal")
@dataclass(frozen=True, slots=True)
class ApollonianGasket(Motif):
    """Circles packed into circles, filling every gap they leave.

    Start with three circles that touch, drop the largest circle that fits in
    the gap between them, and repeat on the three new gaps. Apollonius of
    Perga posed the underlying problem; Descartes' circle theorem solves it in
    one line, which is what this uses.

    The default packing is the integral gasket ``(-1, 2, 2, 3)``: every circle
    in it has an integer curvature, which is a fact about this particular
    starting configuration rather than about gaskets in general.

    Parameters
    ----------
    depth : int, optional
        Rounds of gap-filling. Each round triples the number of gaps.
    radius : float, optional
        Radius of the outer circle.
    min_radius : float, optional
        Stop subdividing once a circle would be smaller than this fraction of
        the outer radius. Necessary as well as kind: the packing is infinite,
        and depth alone does not bound how small it gets.
    center : (float, float), optional
        Middle of the outer circle.
    """

    depth: int = 5
    radius: float = 150.0
    min_radius: float = 0.004
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_depth(type(self).__name__, self.depth)
        if self.radius <= 0.0:
            raise ValueError(f"radius must be > 0, got {self.radius}")
        if not 0.0 < self.min_radius < 1.0:
            raise ValueError(
                f"min_radius is a fraction of the outer radius and must lie strictly "
                f"between 0 and 1, got {self.min_radius}"
            )

    def circles(self) -> tuple[tuple[Point, float], ...]:
        """Return every circle in the packing as a ``(center, radius)`` pair."""
        found = list(_GASKET_SEED)
        for excluded in range(len(_GASKET_SEED)):
            triple = tuple(c for i, c in enumerate(_GASKET_SEED) if i != excluded)
            self._fill(triple, _GASKET_SEED[excluded], self.depth, found)

        cx, cy = self.center
        out: list[tuple[Point, float]] = []
        for curvature, product in found:
            unit_radius = 1.0 / abs(curvature)
            middle = product / curvature
            out.append(
                (
                    (cx + middle.real * self.radius, cy + middle.imag * self.radius),
                    unit_radius * self.radius,
                )
            )
        return tuple(out)

    def _fill(
        self,
        triple: tuple[_Circle, ...],
        other: _Circle,
        depth: int,
        found: list[_Circle],
    ) -> None:
        """Drop a circle into the gap left by ``triple``, then recurse on its three."""
        if depth < 1:
            return
        a, b, c = triple
        new = _sibling(a, b, c, other)
        if 1.0 / abs(new[0]) < self.min_radius:
            return
        found.append(new)
        if len(found) > _MAX_CIRCLES:
            raise ValueError(
                f"{type(self).__name__}: the packing passed {_MAX_CIRCLES} circles; "
                f"raise min_radius (currently {self.min_radius}) or lower depth "
                f"(currently {self.depth})"
            )
        self._fill((a, b, new), c, depth - 1, found)
        self._fill((a, c, new), b, depth - 1, found)
        self._fill((b, c, new), a, depth - 1, found)

    @override
    def build(self) -> Design:
        paths: list[Path] = []
        for middle, radius in self.circles():
            segments = max(
                _GASKET_MIN_SEGMENTS,
                math.ceil(_GASKET_SEGMENTS * radius / self.radius),
            )
            # The last sample lands on the first; a closed path implies its seam.
            points = arc_points(middle, radius, 0.0, math.tau, segments=segments)[:-1]
            paths.append(Path(points, closed=True))
        return Design(tuple(paths), meta=spec(self))


# --- chance -----------------------------------------------------------------

#: Iterations run before plotting begins. The chaos game converges onto the
#: attractor geometrically fast, so a couple of dozen throwaway steps is
#: plenty to make sure the first plotted point is already on it.
_IFS_WARMUP = 25

#: A single run this long is a stress test rather than a design, and the point
#: cloud would be denser than any output device can distinguish.
_MAX_IFS_POINTS = 500_000


@dataclass(frozen=True, slots=True)
class IFSMap:
    """One contracting map of an iterated function system, and how often to pick it.

    Parameters
    ----------
    transform : Affine
        The map itself. It must contract -- shrink distances -- or the chaos
        game runs away instead of settling onto an attractor.
    weight : float
        Relative probability of choosing this map. Weights are normalized, so
        only their ratios matter. Setting it near each map's area scale factor
        is what keeps the resulting cloud evenly dense.
    """

    transform: Affine
    weight: float = 1.0


#: Barnsley's fern, and the reason iterated function systems are famous: four
#: affine maps, twenty-four numbers, and a plant. The first map is a near-total
#: collapse onto a vertical line and draws the stem; the second, taken
#: eighty-five times out of a hundred, is the slight rotate-and-shrink that
#: grows the frond; the last two throw off the left and right leaflets.
_FERN_MAPS: tuple[IFSMap, ...] = (
    IFSMap(Affine(a=0.0, b=0.0, c=0.0, d=0.16, e=0.0, f=0.0), 0.01),
    IFSMap(Affine(a=0.85, b=-0.04, c=0.04, d=0.85, e=0.0, f=1.6), 0.85),
    IFSMap(Affine(a=0.2, b=0.23, c=-0.26, d=0.22, e=0.0, f=1.6), 0.07),
    IFSMap(Affine(a=-0.15, b=0.26, c=0.28, d=0.24, e=0.0, f=0.44), 0.07),
)

#: The canonical demonstration: halve towards each corner of a triangle, with
#: equal probability. What comes out is the Sierpinski gasket -- the same set
#: :class:`SierpinskiTriangle` draws as a stroke, arrived at by throwing dice.
_GASKET_MAPS: tuple[IFSMap, ...] = (
    IFSMap(Affine(a=0.5, d=0.5, e=0.0, f=0.0)),
    IFSMap(Affine(a=0.5, d=0.5, e=0.5, f=0.0)),
    IFSMap(Affine(a=0.5, d=0.5, e=0.25, f=math.sqrt(3.0) / 4.0)),
)


def _chaos_game(maps: Sequence[IFSMap], count: int, rng: random.Random) -> list[Point]:
    """Return ``count`` points on the attractor of ``maps``, picked at random."""
    cumulative: list[float] = []
    running = 0.0
    for entry in maps:
        running += entry.weight
        cumulative.append(running)
    transforms = [entry.transform for entry in maps]

    point: Point = (0.0, 0.0)
    out: list[Point] = []
    for step in range(_IFS_WARMUP + count):
        index = bisect.bisect(cumulative, rng.random() * running)
        # bisect can land one past the end when the draw rounds up against the
        # final cumulative weight, which would be an IndexError once in a while
        # rather than reliably -- the worst kind of bug to ship.
        point = transforms[min(index, len(transforms) - 1)](point)
        if step >= _IFS_WARMUP:
            out.append(point)
    return out


def _scaled(points: Sequence[Point], *, size: float, center: Point) -> tuple[Point, ...]:
    """Return ``points`` scaled so their largest extent is ``size``, centerd on ``center``.

    The attractor's own coordinates are an artefact of whatever numbers the
    maps happen to contain, so they are measured and rescaled rather than
    trusted. ``size`` therefore means what it means everywhere else in the
    catalog: the largest extent of the bounding box.
    """
    bounds = Bounds.from_points(points)
    extent = max(bounds.width, bounds.height)
    if extent == 0.0:
        raise ValueError("the attractor collapsed to a single point; at least one map must move it")
    scale = size / extent
    cx, cy = center
    mid_x = (bounds.min_x + bounds.max_x) / 2.0
    mid_y = (bounds.min_y + bounds.max_y) / 2.0
    return tuple((cx + (x - mid_x) * scale, cy + (y - mid_y) * scale) for x, y in points)


def _check_ifs(owner: str, maps: Sequence[IFSMap], count: int) -> None:
    """Raise unless ``maps`` and ``count`` describe a runnable chaos game."""
    if not maps:
        raise ValueError(f"{owner}: needs at least one IFSMap to iterate")
    if any(entry.weight <= 0.0 for entry in maps):
        raise ValueError(f"{owner}: every map's weight must be > 0, since it is a probability")
    if count < 1:
        raise ValueError(f"{owner}: count must be >= 1, got {count}")
    if count > _MAX_IFS_POINTS:
        raise ValueError(f"{owner}: count {count} exceeds the limit of {_MAX_IFS_POINTS}")


@register("points.ifs", family="fractal", example={"count": 4_000})
@dataclass(frozen=True, slots=True)
class IFSAttractor(Motif):
    """The chaos game: pick a map at random, apply it, plot the point, repeat.

    Michael Barnsley's construction, and the most surprising thing in this
    module. A handful of contracting affine maps have exactly one compact set
    they leave unchanged, and iterating them at random converges onto it from
    any starting point whatsoever -- so the attractor draws itself without
    anyone ever computing where it is.

    The default maps halve towards the corners of a triangle and produce the
    Sierpinski gasket, which is the same set :class:`SierpinskiTriangle`
    traces as a single stroke. Comparing the two is the cheapest way to see
    what a fractal actually *is*, as opposed to how one is drawn.

    Produces loose points rather than a stroke: the order they arrive in is
    random, so joining them would draw noise.

    Parameters
    ----------
    maps : tuple of IFSMap, optional
        The system to iterate. Each map should contract; the weights are
        relative and get normalized.
    count : int, optional
        Points to plot. More fills the attractor in more finely, and costs
        linearly.
    size : float, optional
        Largest extent of the finished cloud. The attractor is measured and
        rescaled, since its own coordinates depend on the maps.
    seed : int, optional
        Seeds a private generator, so the same seed always gives the same
        cloud and the design stays reproducible from its metadata.
    center : (float, float), optional
        Middle of the cloud's bounding box.
    """

    maps: tuple[IFSMap, ...] = _GASKET_MAPS
    count: int = 20_000
    size: float = 240.0
    seed: int = field(default=0, kw_only=True)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ifs(type(self).__name__, self.maps, self.count)
        if self.size <= 0.0:
            raise ValueError(f"size must be > 0, got {self.size}")

    @override
    def build(self) -> Design:
        raw = _chaos_game(self.maps, self.count, random.Random(self.seed))
        return Design((), _scaled(raw, size=self.size, center=self.center), meta=spec(self))


@register("points.barnsley-fern", family="fractal", example={"count": 4_000})
@dataclass(frozen=True, slots=True)
class BarnsleyFern(Motif):
    """Four affine maps and a coin, producing a fern.

    The canonical iterated function system, and still the most persuasive
    argument that a very short description can encode a very complicated
    shape: twenty-four numbers, listed in the source, and the result has a
    stem, fronds and leaflets that were never drawn.

    The same engine with different numbers is :class:`IFSAttractor`. This is
    here because the fern is the example everybody arrives looking for.

    Parameters
    ----------
    count : int, optional
        Points to plot. The fern needs tens of thousands before its leaflets
        fill in.
    size : float, optional
        Largest extent of the finished plant, which is its height.
    seed : int, optional
        Seeds a private generator, so the same seed always gives the same
        fern.
    center : (float, float), optional
        Middle of the plant's bounding box.
    """

    count: int = 40_000
    size: float = 300.0
    seed: int = field(default=0, kw_only=True)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ifs(type(self).__name__, _FERN_MAPS, self.count)
        if self.size <= 0.0:
            raise ValueError(f"size must be > 0, got {self.size}")

    @override
    def build(self) -> Design:
        raw = _chaos_game(_FERN_MAPS, self.count, random.Random(self.seed))
        return Design((), _scaled(raw, size=self.size, center=self.center), meta=spec(self))
