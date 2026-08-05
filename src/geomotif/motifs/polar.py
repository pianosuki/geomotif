"""Roses, harmonics and the sunflower: curves written as angle and radius.

Two halves that share a page because they share an idea -- a shape made by
letting something oscillate.

The polar half is :class:`Rose` and its relatives, where the radius is a
function of the angle. The harmonic half is :class:`Lissajous`,
:class:`Harmonic` and :class:`Harmonograph`, where x and y each oscillate on
their own and the shape is what their beat produces. :class:`Phyllotaxis`
belongs to neither and to both: it is a point set rather than a stroke, and
it is the one motif in the library that plants ship.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import ParametricMotif, PolarMotif, PolygonMotif
from ..core.motif import Motif
from ..core.range import Range
from ..core.registry import register, spec
from ..core.types import Design
from ._common import polar_point

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "GOLDEN_ANGLE",
    "Harmonic",
    "Harmonograph",
    "Lissajous",
    "MaurerRose",
    "Pendulum",
    "Phyllotaxis",
    "PolarExpression",
    "Rose",
    "VogelSpiral",
]

#: The angle a sunflower puts between consecutive seeds, in radians: the full
#: turn divided by the golden ratio, and the single most irrational fraction
#: of a circle there is -- which is exactly why no two seeds ever line up.
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

#: Whole-degree steps in a full turn. A Maurer rose is defined in degrees
#: rather than radians, which is not a unit choice but part of the
#: construction: it is 360 of them that decides when the walk closes.
_STEPS_PER_TURN = 360


def _reduced(n: int, d: int) -> tuple[int, int]:
    """Return ``n/d`` in lowest terms."""
    common = math.gcd(n, d)
    return n // common, d // common


@register("rose", family="polar")
@dataclass(frozen=True, slots=True)
class Rose(ParametricMotif):
    """The rhodonea ``r = cos(n/d * theta)``, with the petal count right.

    The petal count is the part everyone gets wrong, because it depends on
    the parity of the reduced fraction rather than on the numbers as typed.
    With ``k = n/d`` in lowest terms the curve has ``n`` petals when ``n*d``
    is odd and ``2*n`` when it is even, and it closes after ``d*pi`` or
    ``2*d*pi`` respectively. This class works that out and sweeps exactly
    that far, so no petal is ever traced twice.

    ``d = 1`` covers the familiar roses: three petals at ``n = 3``, eight at
    ``n = 4``. Larger denominators give the tangled many-lobed rhodoneas.

    Parameters
    ----------
    n : int, optional
        Numerator of the angular frequency.
    d : int, optional
        Denominator of the angular frequency. Reduced against ``n``, so
        ``Rose(4, 2)`` and ``Rose(2, 1)`` are the same flower.
    size : float, optional
        Petal length, measured from the center.
    center : (float, float), optional
        Where the petals meet.
    """

    closed: ClassVar[bool] = True

    n: int = field(default=5, metadata=Range(1, 24, step=1))
    d: int = field(default=1, metadata=Range(1, 12, step=1))
    size: float = field(default=100.0, metadata=Range(10.0, 400.0))
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError(f"n must be >= 1, got {self.n}")
        if self.d < 1:
            raise ValueError(f"d must be >= 1, got {self.d}")

    def petal_count(self) -> int:
        """Return how many petals this rose actually has."""
        n, d = _reduced(self.n, self.d)
        return n if (n * d) % 2 == 1 else 2 * n

    def closure(self) -> float:
        """Return the angular sweep after which the curve returns to its start."""
        n, d = _reduced(self.n, self.d)
        return math.pi * d if (n * d) % 2 == 1 else math.tau * d

    @override
    def position(self, u: float) -> Point:
        theta = u * self.closure()
        radius = self.size * math.cos(self.n / self.d * theta)
        return polar_point(theta, radius, center=self.center)

    @override
    def sweep_turns(self) -> float:
        # A rose does not wind, it oscillates, and it is the oscillation that
        # needs resolving: twenty petals in half a revolution deserve as many
        # samples as twenty windings of a spiral would.
        return self.closure() / math.tau * max(1.0, self.n / self.d)


@register("rose.maurer", family="polar")
@dataclass(frozen=True, slots=True)
class MaurerRose(PolygonMotif):
    """A rose walked in whole-degree steps and joined by straight chords.

    Peter Maurer's construction, and the best return on effort in the whole
    catalog: take the points of a rose at ``0``, ``degrees``, ``2*degrees``
    and so on, join them with straight lines, and the chords weave a
    filigree the underlying curve gives no hint of. Change ``degrees`` by one
    and the whole pattern reorganizes.

    This is a :class:`~geomotif.PolygonMotif` rather than a curve: the
    vertices *are* the design, and measuring the chords at even parameters
    would round off every corner that makes the pattern.

    Parameters
    ----------
    n : int, optional
        Petal frequency of the underlying rose, ``r = sin(n * theta)``.
    degrees : int, optional
        Whole degrees per step. Coprime with 360 gives the full 360-chord
        figure; a common factor closes the walk early on a coarser one.
    size : float, optional
        Petal length of the underlying rose.
    center : (float, float), optional
        Where the petals meet.
    """

    n: int = field(default=6, metadata=Range(1, 24, step=1))
    degrees: int = field(default=71, metadata=Range(1, 180, step=1))
    size: float = field(default=100.0, metadata=Range(10.0, 400.0))
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError(f"n must be >= 1, got {self.n}")
        if self.degrees % _STEPS_PER_TURN == 0:
            raise ValueError(
                f"degrees must not be a multiple of {_STEPS_PER_TURN}, got {self.degrees}; "
                f"every step would land on the same point"
            )

    def chord_count(self) -> int:
        """Return how many chords the walk takes before it closes."""
        return _STEPS_PER_TURN // math.gcd(self.degrees % _STEPS_PER_TURN, _STEPS_PER_TURN)

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        step = math.radians(self.degrees)
        yield [
            polar_point(k * step, self.size * math.sin(self.n * k * step), center=self.center)
            for k in range(self.chord_count())
        ]


@register("lissajous", family="harmonic")
@dataclass(frozen=True, slots=True)
class Lissajous(ParametricMotif):
    """Two perpendicular oscillations, plotted against each other.

    What an oscilloscope draws with a signal on each axis, and how frequency
    ratios were measured before there was anything better: the figure is
    stable only when the ratio is exactly rational, and it stands still only
    when the phase is too. ``a = b`` degenerates to an ellipse, and to a
    circle when ``delta`` is a quarter turn.

    Parameters
    ----------
    a, b : int, optional
        Frequencies on x and y. Whole numbers, because the figure closes
        only when their ratio is rational.
    delta : float, optional
        Phase offset applied to x, in radians.
    width, height : float, optional
        Full extent on each axis.
    center : (float, float), optional
        Middle of the figure.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    a: int = field(default=3, metadata=Range(1, 16, step=1))
    b: int = field(default=2, metadata=Range(1, 16, step=1))
    delta: float = field(default=math.pi / 2.0, metadata=Range(0.0, math.tau))
    width: float = field(default=200.0, metadata=Range(20.0, 600.0))
    height: float = field(default=200.0, metadata=Range(20.0, 600.0))
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.a < 1 or self.b < 1:
            raise ValueError(f"a and b must be >= 1, got {self.a} and {self.b}")

    @override
    def position(self, u: float) -> Point:
        cx, cy = self.center
        return (
            cx + self.width / 2.0 * math.sin(self.a * u + self.delta),
            cy + self.height / 2.0 * math.sin(self.b * u),
        )

    @override
    def sweep_turns(self) -> float:
        return float(max(self.a, self.b))


@register("harmonic", family="harmonic")
@dataclass(frozen=True, slots=True)
class Harmonic(ParametricMotif):
    """Sums of sines on each axis: :class:`Lissajous` with more terms.

    Each term is ``(amplitude, frequency, phase)``, and the axes are
    independent: matching term for term across the two gives a clean
    rosette, mismatching them gives a knot, and a single fast term against a
    slow one gives a ribbon with a ripple in it::

        Harmonic(
            x_terms=((100.0, 1.0, 0.0),),
            y_terms=((100.0, 3.0, 0.0), (40.0, 17.0, 0.0)),
        )

    The frequencies are whole numbers, because that is what makes the figure
    close.

    Parameters
    ----------
    x_terms, y_terms : tuple of (float, float, float), optional
        The sine terms driving each axis. At least one each.
    center : (float, float), optional
        Middle of the figure.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    x_terms: tuple[tuple[float, float, float], ...] = (
        (100.0, 1.0, 0.0),
        (40.0, 5.0, 0.0),
    )
    y_terms: tuple[tuple[float, float, float], ...] = (
        (100.0, 1.0, math.pi / 2.0),
        (40.0, 5.0, math.pi / 2.0),
    )
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        for name, terms in (("x_terms", self.x_terms), ("y_terms", self.y_terms)):
            if not terms:
                raise ValueError(f"{name} must contain at least one (amplitude, frequency, phase)")
            for index, term in enumerate(terms):
                try:
                    _, frequency, _ = term
                except (TypeError, ValueError):
                    raise ValueError(
                        f"{name}[{index}] must be an (amplitude, frequency, phase) triple, "
                        f"got {term!r}"
                    ) from None
                if not float(frequency).is_integer():
                    raise ValueError(
                        f"{name}[{index}] has frequency {frequency}, which is not a whole "
                        f"number; the figure would never close"
                    )

    @override
    def position(self, u: float) -> Point:
        cx, cy = self.center
        return (
            cx + math.fsum(a * math.sin(f * u + p) for a, f, p in self.x_terms),
            cy + math.fsum(a * math.sin(f * u + p) for a, f, p in self.y_terms),
        )

    @override
    def sweep_turns(self) -> float:
        fastest = max(abs(f) for _, f, _ in (*self.x_terms, *self.y_terms))
        return max(1.0, fastest)


@dataclass(frozen=True, slots=True)
class Pendulum:
    """One swinging weight of a :class:`Harmonograph`.

    Parameters
    ----------
    amplitude : float
        How far it swings at the start.
    frequency : float
        Radians per unit of time. Two pendulums at *almost* the same
        frequency are what makes a harmonograph drift instead of repeat.
    phase : float
        Where in its swing it is released, in radians.
    damping : float
        Exponential decay per unit of time. Zero never settles.
    """

    amplitude: float = 100.0
    frequency: float = 2.0
    phase: float = 0.0
    damping: float = 0.006

    def at(self, t: float) -> float:
        """Return this pendulum's displacement at time ``t``."""
        decay = math.exp(-self.damping * t)
        return self.amplitude * decay * math.sin(self.frequency * t + self.phase)


@register("harmonograph", family="harmonic")
@dataclass(frozen=True, slots=True)
class Harmonograph(ParametricMotif):
    """The Victorian drawing machine: swinging pendulums, slowly running down.

    Two pendulums per axis, each decaying, and a pen where their motions
    meet. What makes the figure rather than a scribble is detuning: set two
    frequencies to ``2.0`` and ``2.005`` and the loops precess a little on
    every pass, so the curve fills a band instead of retracing itself. The
    damping is what closes the spiral inwards and ends the drawing.

    Parameters
    ----------
    x_pendulums, y_pendulums : tuple of Pendulum, optional
        What drives each axis. At least one each; two is the classic
        machine.
    duration : float, optional
        How long to let it swing. Longer means a denser figure, up to the
        point where the damping has stopped it.
    center : (float, float), optional
        Where the pen rests once everything has settled.
    """

    x_pendulums: tuple[Pendulum, ...] = (
        Pendulum(140.0, 2.0, 0.0, 0.006),
        Pendulum(60.0, 3.0, math.pi / 4.0, 0.0018),
    )
    y_pendulums: tuple[Pendulum, ...] = (
        Pendulum(140.0, 2.005, math.pi / 2.0, 0.006),
        Pendulum(60.0, 4.0, 0.0, 0.0018),
    )
    duration: float = 50.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.x_pendulums or not self.y_pendulums:
            raise ValueError("x_pendulums and y_pendulums each need at least one Pendulum")
        if self.duration <= 0.0:
            raise ValueError(f"duration must be > 0, got {self.duration}")

    @override
    def position(self, u: float) -> Point:
        t = u * self.duration
        cx, cy = self.center
        return (
            cx + math.fsum(p.at(t) for p in self.x_pendulums),
            cy + math.fsum(p.at(t) for p in self.y_pendulums),
        )

    @override
    def sweep_turns(self) -> float:
        fastest = max(abs(p.frequency) for p in (*self.x_pendulums, *self.y_pendulums))
        return max(1.0, self.duration * fastest / math.tau)


@register("points.phyllotaxis", family="polar")
@dataclass(frozen=True, slots=True)
class Phyllotaxis(Motif):
    """The sunflower head: ``r = c*sqrt(n)`` at ``n`` golden angles.

    Vogel's model of how a plant packs seeds, and the best dot art in the
    library for the least work. The square root keeps the density even from
    the middle to the rim; the golden angle keeps consecutive seeds from ever
    lining up, which is why the spiral arms you see are an illusion of the
    packing rather than anything the formula mentions. Their count is always
    a Fibonacci number.

    Produces loose points rather than a stroke: joining them in order would
    draw a line no sunflower has.

    Parameters
    ----------
    count : int, optional
        Number of seeds.
    spacing : float, optional
        Scale factor. The head's radius works out at ``spacing *
        sqrt(count)``.
    angle : float, optional
        Turn between consecutive seeds, in radians. Defaults to
        :data:`GOLDEN_ANGLE`; nudge it a hundredth and the packing falls
        apart into visible spokes, which is worth trying once.
    center : (float, float), optional
        Middle of the head.
    """

    count: int = field(default=500, metadata=Range(1, 2000, step=1))
    spacing: float = field(default=8.0, metadata=Range(1.0, 50.0))
    angle: float = field(default=GOLDEN_ANGLE, metadata=Range(0.0, math.tau))
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.spacing <= 0.0:
            raise ValueError(f"spacing must be > 0, got {self.spacing}")

    @override
    def build(self) -> Design:
        seeds = tuple(
            polar_point(i * self.angle, self.spacing * math.sqrt(i), center=self.center)
            for i in range(self.count)
        )
        return Design((), seeds, meta=spec(self))


#: Vogel's name for the same construction. The literature uses both, and a
#: reader who knows it as one should not have to guess the other.
VogelSpiral = Phyllotaxis


def _ripple(theta: float) -> float:
    """Return the radius of a seven-lobed flower with a ripple on it.

    The ripple runs at three times the lobe frequency rather than at some
    unrelated one, so the flower keeps its seven-fold symmetry instead of
    merely looking busy.
    """
    return 100.0 * math.sin(7.0 * theta) + 25.0 * math.cos(21.0 * theta)


@register("polar.expression", family="polar")
@dataclass(frozen=True, slots=True)
class PolarExpression(PolarMotif):
    """Any radius function you like, wrapped as a motif.

    The escape hatch for a one-off polar curve that does not deserve a class
    of its own::

        PolarExpression(lambda t: 60 + 20 * math.sin(9 * t))

    Subclassing :class:`~geomotif.PolarMotif` is still the better answer for
    anything you will use twice -- it gets a name, a docstring, parameters
    and a registry entry. This is for the other times.

    Parameters
    ----------
    formula : callable, optional
        Maps an angle in radians to a radius. Called across the sweep only.
        Named ``formula`` rather than ``radius`` because ``radius`` is the
        method it is about to become.

    Notes
    -----
    The design this builds records the function object in its metadata, so
    it round-trips within a session but not through a file. Anything that
    has to survive being written down wants a real registered class.
    """

    formula: Callable[[float], float] = field(default=_ripple)

    @override
    def radius(self, theta: float) -> float:
        return self.formula(theta)
