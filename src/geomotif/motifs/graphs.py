"""Graph and number art: points on a circle, joined by an arithmetic rule.

Every motif here is the same motif with a different edge rule -- nodes spaced
around a circle, and a statement about which pairs get a straight line between
them. What makes the family worth a module is how little the rule has to
change for the picture to change completely: multiplying by two gives a
cardioid, by three a nephroid, and by 51 a figure with no name at all.

The workhorse is :class:`ModularMultiplication`, the times table drawn as
chords. It is also, viewed from the other side, circle string art -- so
:mod:`geomotif.motifs.stringart` re-exports it under that name rather than
implementing the same geometry twice.

All of these are :class:`~geomotif.SegmentMotif` subclasses, so they take
``merge=True`` to chain segments that share an endpoint into longer strokes
(far fewer pen lifts on a plotter) and ``show_nodes=True`` to emit the nodes
themselves as loose points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING, override

from ..bases import SegmentMotif
from ..core.registry import register
from ._common import ring_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "BipartiteGraph",
    "ChordDiagram",
    "CompleteGraph",
    "CyclicGraph",
    "ModularAddition",
    "ModularMultiplication",
    "PrimeChords",
]

#: The default chords of a :class:`ChordDiagram`: an arbitrary set on sixteen
#: nodes, there to show the shape of the input rather than to mean anything.
#: The class exists for chords you supply.
_EXAMPLE_CHORDS: tuple[tuple[int, int], ...] = (
    (0, 7),
    (0, 9),
    (1, 5),
    (2, 11),
    (3, 8),
    (3, 14),
    (4, 10),
    (5, 13),
    (6, 12),
    (7, 15),
    (8, 2),
    (9, 4),
    (10, 1),
    (11, 6),
    (12, 3),
    (13, 0),
)


def _check_ring(owner: str, count: int, radius: float, *, minimum: int = 2) -> None:
    """Raise unless ``count`` nodes at ``radius`` describe a drawable ring."""
    if count < minimum:
        raise ValueError(f"{owner}: needs at least {minimum} nodes, got {count}")
    if radius <= 0.0:
        raise ValueError(f"{owner}: radius must be > 0, got {radius}")


def _primes_below(limit: int) -> list[int]:
    """Return every prime strictly below ``limit``, by sieve."""
    sieve = bytearray([1]) * limit
    sieve[0:2] = b"\x00\x00"
    for candidate in range(2, math.isqrt(limit - 1) + 1):
        if sieve[candidate]:
            sieve[candidate * candidate :: candidate] = bytearray(
                len(range(candidate * candidate, limit, candidate))
            )
    return [n for n in range(limit) if sieve[n]]


@register("graph.complete", family="graph")
@dataclass(frozen=True, slots=True)
class CompleteGraph(SegmentMotif):
    """Every node joined to every other: K5, K12, and the ones in between.

    The picture mathematicians draw when they say "complete graph", and a
    surprisingly good ornament -- the chords cross in a moire that tightens
    towards the middle. The edge count is ``order * (order - 1) / 2``, so it
    grows quadratically and gets solid black somewhere around forty nodes.

    Parameters
    ----------
    order : int, optional
        Number of nodes.
    radius : float, optional
        Radius of the circle they sit on.
    rotation : float, optional
        Angle of the first node, in radians. A quarter turn puts it at the
        top, which is how these are conventionally drawn.
    center : (float, float), optional
        Middle of the circle.
    """

    order: int = 12
    radius: float = 120.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.order, self.radius)

    def edge_count(self) -> int:
        """Return how many chords this graph draws."""
        return self.order * (self.order - 1) // 2

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.order, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return combinations(range(self.order), 2)


@register("graph.cyclic", family="graph")
@dataclass(frozen=True, slots=True)
class CyclicGraph(SegmentMotif):
    """The circulant: join every node to the ones a fixed number of steps away.

    One step is the plain cycle, which is a regular polygon. Several steps at
    once is where it gets interesting -- each one contributes its own star
    polygon and they overlay into a rosette. ``steps=(1, 2, 3)`` on a dozen
    nodes is a good place to start.

    Parameters
    ----------
    order : int, optional
        Number of nodes.
    steps : tuple of int, optional
        How far around to reach. Each step ``s`` joins node ``i`` to node
        ``i + s`` for every ``i``, wrapping.
    radius : float, optional
        Radius of the circle the nodes sit on.
    rotation : float, optional
        Angle of the first node, in radians.
    center : (float, float), optional
        Middle of the circle.
    """

    order: int = 16
    steps: tuple[int, ...] = (1, 3, 5)
    radius: float = 120.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.order, self.radius, minimum=3)
        if not self.steps:
            raise ValueError(f"{type(self).__name__}: needs at least one step")
        for step in self.steps:
            if not 1 <= step < self.order:
                raise ValueError(
                    f"{type(self).__name__}: step {step} must be >= 1 and < order "
                    f"({self.order}); a larger step is the same as a smaller one wrapped"
                )

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.order, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return ((i, (i + step) % self.order) for step in self.steps for i in range(self.order))


@register("graph.bipartite", family="graph")
@dataclass(frozen=True, slots=True)
class BipartiteGraph(SegmentMotif):
    """Two rows of nodes, and every line from one row to the other.

    The complete bipartite graph, drawn the way it is drawn in textbooks: two
    facing ranks with all ``left * right`` connections between them. Every
    crossing is visible, which is what makes it useful for showing why K33
    cannot be drawn without them.

    Parameters
    ----------
    left, right : int, optional
        Nodes in each rank.
    span : float, optional
        Horizontal distance between the two ranks.
    height : float, optional
        Vertical extent of each rank.
    center : (float, float), optional
        Middle of the whole figure.
    """

    left: int = 4
    right: int = 5
    span: float = 200.0
    height: float = 220.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.left < 1 or self.right < 1:
            raise ValueError(
                f"{type(self).__name__}: each rank needs at least one node, "
                f"got {self.left} and {self.right}"
            )
        if self.span <= 0.0 or self.height <= 0.0:
            raise ValueError(
                f"{type(self).__name__}: span and height must be > 0, "
                f"got {self.span} and {self.height}"
            )

    @override
    def nodes(self) -> Sequence[Point]:
        cx, cy = self.center
        half = self.span / 2.0
        return [
            *self._rank(cx - half, cy, self.left),
            *self._rank(cx + half, cy, self.right),
        ]

    def _rank(self, x: float, cy: float, count: int) -> list[Point]:
        """Return ``count`` nodes spread down a vertical line at ``x``."""
        # A single node sits on the axis rather than at the top of the rank,
        # which is the only sensible place for it to be.
        if count == 1:
            return [(x, cy)]
        step = self.height / (count - 1)
        return [(x, cy + self.height / 2.0 - i * step) for i in range(count)]

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return ((i, self.left + j) for i in range(self.left) for j in range(self.right))


@register("graph.chord", family="graph")
@dataclass(frozen=True, slots=True)
class ChordDiagram(SegmentMotif):
    """Nodes on a circle and whichever chords you name between them.

    The escape hatch of the family, and the one to reach for when the
    connections come from data rather than from arithmetic -- a dependency
    graph, a migration table, who talks to whom. The other classes in this
    module are this one with the chord list computed.

    Parameters
    ----------
    order : int, optional
        Number of nodes around the circle.
    chords : tuple of (int, int), optional
        Index pairs to join. Self-loops and repeats are dropped rather than
        rejected, since a real dataset routinely contains both.
    radius : float, optional
        Radius of the circle.
    rotation : float, optional
        Angle of node zero, in radians.
    center : (float, float), optional
        Middle of the circle.
    show_nodes : bool, optional
        Emit the nodes as loose points. On by default here and nowhere else:
        an arithmetic rule fills the circle densely enough to imply where its
        nodes are, while a handful of chords from a dataset does not, and
        without the dots the figure reads as a pile of sticks.
    """

    order: int = 16
    chords: tuple[tuple[int, int], ...] = _EXAMPLE_CHORDS
    radius: float = 120.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)
    show_nodes: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.order, self.radius)
        if not self.chords:
            raise ValueError(f"{type(self).__name__}: needs at least one chord to draw")

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.order, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return self.chords


@register("modular.multiplication", family="graph")
@dataclass(frozen=True, slots=True)
class ModularMultiplication(SegmentMotif):
    """The times table drawn as chords, which turns out to be a cardioid.

    Space the numbers ``0`` to ``modulus - 1`` evenly around a circle and join
    each ``i`` to ``factor * i``. Doubling gives a cardioid, tripling a
    nephroid, and every factor after that an epicycloid with one fewer cusp
    than the factor -- none of which is put there deliberately. The cusps are
    the envelope of the chords, and the whole family falls out of one line of
    arithmetic.

    Seen from the other direction this is circle string art, which is why
    :mod:`geomotif.motifs.stringart` re-exports it as ``StringArtCircle``
    rather than drawing the same chords twice.

    Parameters
    ----------
    modulus : int, optional
        How many numbers go around the circle.
    factor : int, optional
        What each is multiplied by. Two for the cardioid, three for the
        nephroid, and large primes for the dense figures.
    radius : float, optional
        Radius of the circle.
    rotation : float, optional
        Angle of node zero, in radians.
    center : (float, float), optional
        Middle of the circle.
    """

    modulus: int = 200
    factor: int = 2
    radius: float = 120.0
    rotation: float = math.pi
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.modulus, self.radius)
        if self.factor % self.modulus == 1:
            raise ValueError(
                f"{type(self).__name__}: factor {self.factor} leaves every number where "
                f"it is modulo {self.modulus}, so every chord would join a node to "
                f"itself and there would be nothing to draw"
            )

    def cusp_count(self) -> int:
        """Return how many cusps the chord envelope has: one fewer than the factor."""
        return max(1, self.factor - 1)

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.modulus, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return ((i, self.factor * i % self.modulus) for i in range(self.modulus))


@register("modular.addition", family="graph")
@dataclass(frozen=True, slots=True)
class ModularAddition(SegmentMotif):
    """Join each number to the one a fixed distance further round.

    The times table's sibling, and the plainer of the two: adding a constant
    steps around the circle at a constant rate, so the result is the star
    polygon ``{modulus/addend}`` -- one loop if the two are coprime, several
    interleaved ones if they are not.

    That makes it the same set of lines :class:`~geomotif.motifs.primitives.StarPolygon`
    draws, and it is here because the family reads wrong without it: seeing
    how little the addition version does is what makes the multiplication
    version surprising. Reach for ``StarPolygon`` when you want the star
    itself, and for this when you are exploring the arithmetic.

    Parameters
    ----------
    modulus : int, optional
        How many numbers go around the circle.
    addend : int, optional
        How far each step reaches.
    radius : float, optional
        Radius of the circle.
    rotation : float, optional
        Angle of node zero, in radians.
    center : (float, float), optional
        Middle of the circle.
    """

    modulus: int = 120
    addend: int = 37
    radius: float = 120.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.modulus, self.radius)
        if self.addend % self.modulus == 0:
            raise ValueError(
                f"{type(self).__name__}: an addend of {self.addend} is a whole number of "
                f"times round a circle of {self.modulus}, so every step would land back "
                f"where it started and there would be nothing to draw"
            )

    def loop_count(self) -> int:
        """Return how many separate loops the walk falls into."""
        return math.gcd(self.addend % self.modulus, self.modulus)

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.modulus, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        return ((i, (i + self.addend) % self.modulus) for i in range(self.modulus))


@register("graph.prime-chords", family="graph")
@dataclass(frozen=True, slots=True)
class PrimeChords(SegmentMotif):
    """Join two numbers whenever they add up to a prime.

    Space the whole numbers below ``limit`` around a circle and draw a chord
    between every pair whose sum is prime. The result is a dense, oddly
    orderly web, and every feature in it is a fact about primes rather than a
    decision about drawing: no chord ever joins two even numbers or two odd
    ones, because their sum would be even, so the figure is bipartite and the
    ring of alternating nodes shows it. The one exception is the pair summing
    to two, which is why zero-to-two is the only even-even chord in the
    picture.

    Parameters
    ----------
    limit : int, optional
        Numbers to place around the circle, from ``0`` to ``limit - 1``. The
        chord count grows roughly as ``limit**2 / log(limit)``, so this gets
        solid black quickly.
    radius : float, optional
        Radius of the circle.
    rotation : float, optional
        Angle of node zero, in radians.
    center : (float, float), optional
        Middle of the circle.
    """

    limit: int = 60
    radius: float = 120.0
    rotation: float = math.pi / 2.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_ring(type(self).__name__, self.limit, self.radius, minimum=4)

    @override
    def nodes(self) -> Sequence[Point]:
        return ring_points(self.limit, self.radius, center=self.center, rotation=self.rotation)

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        # Two nodes below the limit sum to less than twice it, so that is how
        # far the sieve has to run.
        reachable = frozenset(_primes_below(2 * self.limit))
        return (
            (i, j)
            for i in range(self.limit)
            for j in range(i + 1, self.limit)
            if i + j in reachable
        )
