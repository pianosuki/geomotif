"""Spiral motifs.

Most of the family is a radius that grows with the angle, so most of it is a
one-line :meth:`~geomotif.PolarMotif.radius` on top of :class:`SpiralBase`.
The four that are not -- Fibonacci (quarter arcs), Theodorus (a chain of
triangles), Euler (Fresnel integrals) and the circle involute (an unwinding
string) -- are not polar functions of theta at all, and say so by using a
different base.

Angles follow the standard math convention: counter-clockwise positive, with
the y-axis pointing up. For a y-down (screen/raster) coordinate system, call
:meth:`~geomotif.Design.flipped_y` on the result rather than looking for a
flag here -- which way y points is a property of the target space, not of the
spiral.
"""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import Curve, ParametricMotif, PolarMotif, PolygonMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.sampling import densify, samples_for_turns
from ..core.types import Design, Path
from ._common import arc_points

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "ArchimedeanSpiral",
    "CircleInvolute",
    "EulerSpiral",
    "FermatSpiral",
    "FibonacciSpiral",
    "GoldenSpiral",
    "HyperbolicSpiral",
    "Lituus",
    "LogarithmicSpiral",
    "SpiralBase",
    "SpiralBetween",
    "TheodorusSpiral",
]

#: The golden ratio, and the growth rate of the spiral named after it: a
#: logarithmic spiral widens by ``PHI`` every quarter turn.
PHI = (1.0 + math.sqrt(5.0)) / 2.0
_GOLDEN_GROWTH = math.log(PHI) / (math.pi / 2.0)


def _theta_extent(motif: PolarMotif) -> tuple[float, float]:
    """Return the ``(lowest, highest)`` angle a polar motif's sweep reaches."""
    lo = motif.theta_start
    hi = lo + motif.theta_span
    return (lo, hi) if lo <= hi else (hi, lo)


@dataclass(frozen=True, slots=True)
class SpiralBase(PolarMotif, ABC):
    """Shared ground for spirals defined by a radius that grows with theta.

    Everything a spiral needs is already on :class:`~geomotif.PolarMotif` --
    :attr:`~geomotif.PolarMotif.center`, ``theta_start`` and ``theta_span``.
    This adds only the family's default sweep, three turns rather than one,
    since a single revolution of a spiral is barely recognizable as one.

    Say the sweep in revolutions with
    :meth:`~geomotif.PolarMotif.with_turns`::

        LogarithmicSpiral(b=0.2).with_turns(5, clockwise=True)

    A concrete spiral is then its formula and nothing else::

        @register("spiral.archimedean", family="spiral")
        @dataclass(frozen=True, slots=True)
        class ArchimedeanSpiral(SpiralBase):
            a: float = 0.0
            b: float = 10.0

            def radius(self, theta: float) -> float:
                return self.a + self.b * theta
    """

    #: Three turns, the point at which a spiral reads as a spiral.
    theta_span: float = field(default=3.0 * math.tau, kw_only=True)


@register("spiral.archimedean", family="spiral")
@dataclass(frozen=True, slots=True)
class ArchimedeanSpiral(SpiralBase):
    """The arithmetic spiral ``r = a + b*theta``.

    Successive turns are a constant ``b*tau`` apart, which is what makes this
    the spiral of coiled rope, clock springs and vinyl records -- and the one
    to reach for when even spacing between the windings is the point.

    Parameters
    ----------
    a : float, optional
        Radius at ``theta = 0``: the size of the hole in the middle.
    b : float, optional
        Radial growth per radian. Every turn is ``b * tau`` further out.
    """

    a: float = 0.0
    b: float = 10.0

    @override
    def radius(self, theta: float) -> float:
        return self.a + self.b * theta

    @staticmethod
    def between(
        start: Point,
        end: Point,
        *,
        center: Point = (0.0, 0.0),
        clockwise: bool = True,
        turns: int = 0,
    ) -> SpiralBetween:
        """Return the arithmetic spiral running from ``start`` to ``end``.

        The same curve as this class, constrained by where it has to begin and
        end rather than by its growth rate -- which is the useful form when
        the endpoints are given and ``b`` is whatever it has to be. See
        :class:`SpiralBetween`.
        """
        return SpiralBetween(start, end, center=center, clockwise=clockwise, turns=turns)


@register("spiral.logarithmic", family="spiral")
@dataclass(frozen=True, slots=True)
class LogarithmicSpiral(SpiralBase):
    """The equiangular spiral ``r = a * exp(b*theta)``.

    Every turn is a constant *multiple* of the one inside it, so the shape is
    the same at every scale -- the nautilus shell, the spiral galaxy, the low
    pressure system. The tangent meets the radius at the same angle
    everywhere, which is where "equiangular" comes from.

    Parameters
    ----------
    a : float, optional
        Radius at ``theta = 0``.
    b : float, optional
        Growth rate. The radius multiplies by ``exp(b * tau)`` each turn;
        ``0`` degenerates to a circle.
    """

    a: float = 5.0
    b: float = 0.15

    @override
    def radius(self, theta: float) -> float:
        return self.a * math.exp(self.b * theta)


@register("spiral.golden", family="spiral")
@dataclass(frozen=True, slots=True)
class GoldenSpiral(SpiralBase):
    """The logarithmic spiral that widens by the golden ratio each quarter turn.

    A preset rather than a new curve: :class:`LogarithmicSpiral` with ``b``
    fixed at ``ln(phi) / (pi/2)``. Distinct from :class:`FibonacciSpiral`,
    which is the quarter-circle *approximation* usually drawn in its place --
    they are close enough to be mistaken for each other and different enough
    to be worth having both.

    Parameters
    ----------
    a : float, optional
        Radius at ``theta = 0``.
    """

    #: Radial growth per radian. Fixed: varying it makes an ordinary
    #: logarithmic spiral, which already exists.
    GROWTH: ClassVar[float] = _GOLDEN_GROWTH

    a: float = 2.0
    #: Two turns, because at 6.85x growth per turn a third would dwarf the
    #: first two into invisibility.
    theta_span: float = field(default=2.0 * math.tau, kw_only=True)

    @override
    def radius(self, theta: float) -> float:
        return self.a * math.exp(self.GROWTH * theta)


@register("spiral.fermat", family="spiral")
@dataclass(frozen=True, slots=True)
class FermatSpiral(SpiralBase):
    """The parabolic spiral ``r = a * sqrt(theta)``, both branches.

    Defined by ``r**2 = a**2 * theta``, so every angle has a positive and a
    negative root and the true curve is two arms meeting at the origin, each
    the other reflected through it. That symmetry is the whole character of
    the shape -- it is the arrangement sunflower seeds settle into -- so both
    arms are drawn by default.

    Because area grows linearly with ``theta``, the windings crowd together as
    they go out, packing points at constant density rather than constant
    spacing.

    Parameters
    ----------
    a : float, optional
        Radial scale.
    both_branches : bool, optional
        Draw the second arm. Turn off for the single arm alone.
    """

    a: float = 30.0
    both_branches: bool = field(default=True, kw_only=True)

    def __post_init__(self) -> None:
        low, _ = _theta_extent(self)
        if low < 0.0:
            raise ValueError(
                f"{type(self).__name__} needs theta >= 0 (its radius is a square root), "
                f"but the sweep reaches {low}"
            )

    @override
    def radius(self, theta: float) -> float:
        return self.a * math.sqrt(theta)

    def _reflected(self, u: float) -> Point:
        """Return :meth:`position` reflected through the center: the other arm."""
        x, y = self.position(u)
        cx, cy = self.center
        return (2.0 * cx - x, 2.0 * cy - y)

    @override
    def curves(self) -> Iterable[Curve]:
        turns = self.sweep_turns()
        yield Curve(self.position, domain=self.domain, turns=turns)
        if self.both_branches:
            yield Curve(self._reflected, domain=self.domain, turns=turns)


@register("spiral.hyperbolic", family="spiral")
@dataclass(frozen=True, slots=True)
class HyperbolicSpiral(SpiralBase):
    """The reciprocal spiral ``r = a / theta``.

    Runs the other way from most of the family: it starts far out and winds
    *inward* toward the origin, which it approaches without ever arriving.
    Outward it is asymptotic to the line ``y = a``.

    ``theta = 0`` is a pole, so the sweep must not cross it --
    :attr:`~geomotif.PolarMotif.theta_start` therefore defaults to a small
    positive angle rather than zero.

    Parameters
    ----------
    a : float, optional
        Radial scale, and the height of the horizontal asymptote.
    """

    a: float = 200.0
    #: Far enough from the pole to keep the outer end on the canvas.
    theta_start: float = field(default=math.pi / 6.0, kw_only=True)

    def __post_init__(self) -> None:
        _reject_pole(self)

    @override
    def radius(self, theta: float) -> float:
        return self.a / theta


@register("spiral.lituus", family="spiral")
@dataclass(frozen=True, slots=True)
class Lituus(SpiralBase):
    """The spiral ``r = a / sqrt(theta)``, named for the Roman augur's staff.

    The reciprocal of :class:`FermatSpiral`, and its complement: it sweeps
    equal *areas* in equal angles, so where Fermat's arms crowd outward this
    one's crowd inward. Like :class:`HyperbolicSpiral` it has a pole at
    ``theta = 0`` and its sweep must avoid it.

    Parameters
    ----------
    a : float, optional
        Radial scale.
    """

    a: float = 200.0
    #: Far enough from the pole to keep the outer end on the canvas.
    theta_start: float = field(default=math.pi / 6.0, kw_only=True)

    def __post_init__(self) -> None:
        _reject_pole(self)
        low, _ = _theta_extent(self)
        if low < 0.0:
            raise ValueError(
                f"{type(self).__name__} needs theta > 0 (its radius is a square root), "
                f"but the sweep reaches {low}"
            )

    @override
    def radius(self, theta: float) -> float:
        return self.a / math.sqrt(theta)


def _reject_pole(motif: PolarMotif) -> None:
    """Raise if a motif with a pole at ``theta = 0`` sweeps across it."""
    low, high = _theta_extent(motif)
    if low <= 0.0 <= high:
        raise ValueError(
            f"{type(motif).__name__} has a pole at theta = 0, but its sweep covers "
            f"[{low}, {high}]; move theta_start away from zero"
        )


@register("spiral.theodorus", family="spiral")
@dataclass(frozen=True, slots=True)
class TheodorusSpiral(PolygonMotif):
    """The square-root spiral: a chain of right triangles, drawn exactly.

    Each triangle stands on the hypotenuse of the last with a new leg of
    length ``size``, so the ``n``-th vertex sits at distance
    ``size * sqrt(n)`` from the center. The result is a polyline by nature,
    not a sampled curve -- there is nothing between the vertices to measure --
    which is why this is a :class:`~geomotif.PolygonMotif`.

    Parameters
    ----------
    triangles : int, optional
        How many triangles to stack. The classic figure stops at 16, where
        the spiral has just about closed its first turn.
    size : float, optional
        Length of each triangle's new leg.
    center : (float, float), optional
        Point the chain winds around.
    """

    #: An open chain, not a loop.
    closed: ClassVar[bool] = False

    triangles: int = 16
    size: float = 20.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.triangles < 1:
            raise ValueError(f"triangles must be >= 1, got {self.triangles}")

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        cx, cy = self.center
        angle = 0.0
        corners: list[Point] = [(cx + self.size, cy)]
        for n in range(1, self.triangles + 1):
            # The new leg is perpendicular to the current hypotenuse of
            # length sqrt(n), so it turns the radius by atan(1 / sqrt(n)).
            angle += math.atan2(1.0, math.sqrt(n))
            radius = self.size * math.sqrt(n + 1)
            corners.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        yield corners


@register("spiral.fibonacci", family="spiral")
@dataclass(frozen=True, slots=True)
class FibonacciSpiral(Motif):
    """Quarter circles inscribed in a chain of Fibonacci squares.

    The spiral everyone draws when they mean :class:`GoldenSpiral`, and not
    the same curve: it is a sequence of circular arcs that jump in curvature
    at every join, where the golden spiral is smooth throughout. The two run
    within a couple of percent of each other, which is exactly why the
    distinction is worth drawing.

    Parameters
    ----------
    quarters : int, optional
        Number of quarter-circle arcs, one per Fibonacci square.
    size : float, optional
        Side of the first square.
    """

    quarters: int = 9
    size: float = 10.0

    def __post_init__(self) -> None:
        if self.quarters < 1:
            raise ValueError(f"quarters must be >= 1, got {self.quarters}")

    def _radii(self) -> list[float]:
        """Return the arc radii: the Fibonacci numbers, scaled by ``size``."""
        radii = [self.size, self.size]
        while len(radii) < self.quarters:
            radii.append(radii[-1] + radii[-2])
        return radii[: self.quarters]

    @override
    def build(self) -> Design:
        quarter = math.pi / 2.0
        radii = self._radii()
        cx, cy = 0.0, 0.0
        angle = math.pi
        points: list[Point] = []

        for index, radius in enumerate(radii):
            arc = arc_points((cx, cy), radius, angle, quarter)
            # Consecutive arcs meet exactly, so the joint is only stored once.
            points.extend(arc if index == 0 else arc[1:])
            angle += quarter
            if index + 1 < len(radii):
                # Shift the center along the shared radius so the next, larger
                # arc starts where this one ended.
                shift = radius - radii[index + 1]
                cx += shift * math.cos(angle)
                cy += shift * math.sin(angle)

        return Design((Path(tuple(points)),), meta=spec(self))


@register("spiral.euler", family="spiral")
@dataclass(frozen=True, slots=True)
class EulerSpiral(ParametricMotif):
    """The clothoid: curvature increasing linearly with distance travelled.

    Drive at constant speed and turn the wheel at a constant rate and this is
    the path you take, which is why it is the transition curve between a
    straight railway and a curved one. Both arms wind into their own limit
    point, and the whole curve is one continuous sweep through the origin.

    Parameters
    ----------
    scale : float, optional
        Size of the figure: the two limit points sit ``scale/2`` from the
        center along each axis.
    extent : float, optional
        How far along the curve to travel in each direction. Past about 3 the
        arms have all but reached their limit points.
    center : (float, float), optional
        Midpoint of the figure.

    Notes
    -----
    The Fresnel integrals are evaluated by power series, which is accurate to
    machine precision out to ``extent = 4``. Beyond that the series loses too
    many digits to cancellation and a standard rational approximation takes
    over, good to about ``2e-3 * scale``. That is the price of a
    dependency-free implementation, and it is charged only where the curve
    has already spiralled down to a dot.
    """

    scale: float = 200.0
    extent: float = 2.5
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.extent <= 0.0:
            raise ValueError(f"extent must be > 0, got {self.extent}")

    @override
    def position(self, u: float) -> Point:
        t = self.extent * (2.0 * u - 1.0)
        c, s = _fresnel(t)
        cx, cy = self.center
        return (cx + self.scale * c, cy + self.scale * s)

    @override
    def sweep_turns(self) -> float:
        # Total turning is pi*t**2/2 radians at parameter t, so each arm winds
        # t**2/4 times; both arms together are twice that.
        return self.extent**2 / 2.0


@register("spiral.involute", family="spiral")
@dataclass(frozen=True, slots=True)
class CircleInvolute(ParametricMotif):
    """The path of a string unwinding, taut, from a circle.

    Neighbouring turns stay exactly one circumference apart, which is what
    makes this the profile of very nearly every gear tooth in existence: two
    involutes rolling against each other transmit motion at a constant ratio
    however far apart their axes drift.

    Not a polar motif, despite looking like one -- ``r`` and ``theta`` are
    both functions of how much string has unwound, and neither is a function
    of the other in closed form.

    Parameters
    ----------
    radius : float, optional
        Radius of the circle being unwound from.
    turns : float, optional
        Revolutions of string to unwind.
    center : (float, float), optional
        Center of that circle.
    """

    radius: float = 10.0
    turns: float = 3.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.turns <= 0.0:
            raise ValueError(f"turns must be > 0, got {self.turns}")

    @override
    def position(self, u: float) -> Point:
        t = math.tau * self.turns * u
        cx, cy = self.center
        return (
            cx + self.radius * (math.cos(t) + t * math.sin(t)),
            cy + self.radius * (math.sin(t) - t * math.cos(t)),
        )

    @override
    def sweep_turns(self) -> float:
        return self.turns


@register(
    "spiral.between",
    family="spiral",
    example={"start": (100.0, 0.0), "end": (10.0, 0.0), "turns": 2},
)
@dataclass(frozen=True, slots=True)
class SpiralBetween(Motif):
    """The endpoint-constrained arithmetic spiral: ``r = a + b*theta``.

    Winds from ``start`` to ``end`` around ``center``, interpolating the
    radius linearly against a linearly interpolated angle. Both endpoints are
    hit exactly, which is what makes this the useful form when you know where
    the curve has to begin and end rather than what its growth rate should be.
    :class:`ArchimedeanSpiral` is the same curve parameterized the other way.

    Parameters
    ----------
    start : (float, float)
        First point of the spiral.
    end : (float, float)
        Last point of the spiral.
    center : (float, float), optional
        Point the spiral winds around. Default ``(0, 0)``.
    clockwise : bool, optional
        Rotational direction of the sweep. Default ``True``.
    turns : int, optional
        Extra full revolutions beyond the direct angular sweep from start to
        end. ``0`` (default) takes the shortest sweep in the chosen direction.
    resolution : int, optional
        Number of segments used to measure the curve. Defaults to a density
        that scales with the number of turns, which is nearly always right.

    Examples
    --------
    ::

        SpiralBetween((200, 0), (20, 0), turns=3).generate(120)
    """

    start: Point
    end: Point
    center: Point = (0.0, 0.0)
    clockwise: bool = True
    turns: int = 0
    resolution: int | None = None

    def __post_init__(self) -> None:
        if self.turns < 0:
            raise ValueError(f"turns must be >= 0, got {self.turns}")
        if self.resolution is not None and self.resolution < 1:
            raise ValueError(f"resolution must be >= 1, got {self.resolution}")

    def _sweep(self) -> tuple[float, float, float, float]:
        """Return ``(r0, r1, a0, sweep)`` -- the spiral's polar description."""
        cx, cy = self.center
        r0 = math.dist(self.start, self.center)
        r1 = math.dist(self.end, self.center)

        # A point sitting exactly on the center has no defined angle; borrow
        # the other endpoint's angle so the path degenerates gracefully to a
        # radial line instead of an arbitrary jump.
        match r0 > 0, r1 > 0:
            case True, True:
                a0 = math.atan2(self.start[1] - cy, self.start[0] - cx)
                a1 = math.atan2(self.end[1] - cy, self.end[0] - cx)
            case True, False:
                a0 = a1 = math.atan2(self.start[1] - cy, self.start[0] - cx)
            case False, True:
                a0 = a1 = math.atan2(self.end[1] - cy, self.end[0] - cx)
            case _:
                a0 = a1 = 0.0

        if self.clockwise:
            sweep = -((a0 - a1) % math.tau) - math.tau * self.turns
        else:
            sweep = ((a1 - a0) % math.tau) + math.tau * self.turns
        return r0, r1, a0, sweep

    @override
    def build(self) -> Design:
        r0, r1, a0, sweep = self._sweep()
        cx, cy = self.center

        def position(u: float) -> Point:
            angle = a0 + sweep * u
            radius = r0 + (r1 - r0) * u
            return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

        samples = self.resolution or samples_for_turns(abs(sweep) / math.tau)
        return Design((Path(densify(position, samples=samples)),), meta=spec(self))


# Where the Fresnel power series is still accurate. Its terms peak around
# ``(pi/2 * z**2 / 2)**n / n!`` and beyond this the cancellation between them
# eats more significant digits than a double has to give.
_SERIES_LIMIT = 4.0
_SERIES_TERMS = 60


def _fresnel(z: float) -> tuple[float, float]:
    """Return the Fresnel integrals ``(C(z), S(z))``.

    ``C`` and ``S`` integrate ``cos(pi*t**2/2)`` and ``sin(pi*t**2/2)`` from
    zero to ``z``. Both are odd, so negative arguments are handled by
    symmetry.
    """
    if z < 0.0:
        c, s = _fresnel(-z)
        return (-c, -s)
    if z <= _SERIES_LIMIT:
        return _fresnel_series(z)
    return _fresnel_rational(z)


def _fresnel_series(z: float) -> tuple[float, float]:
    """Return ``(C(z), S(z))`` from their power series about zero."""
    half_pi = math.pi / 2.0
    # Successive terms differ by this factor over a rising factorial, so each
    # is stepped from the last rather than recomputed from powers.
    growth = half_pi**2 * z**4

    c_term = z
    s_term = half_pi * z**3
    c, s = c_term, s_term / 3.0

    for n in range(1, _SERIES_TERMS):
        c_term *= growth / ((2 * n - 1) * (2 * n))
        s_term *= growth / ((2 * n) * (2 * n + 1))
        sign = -1.0 if n % 2 else 1.0
        c += sign * c_term / (4 * n + 1)
        s += sign * s_term / (4 * n + 3)
        if abs(c_term) < 1e-18 and abs(s_term) < 1e-18:
            break
    return (c, s)


def _fresnel_rational(z: float) -> tuple[float, float]:
    """Return ``(C(z), S(z))`` for large ``z`` from Abramowitz & Stegun 7.3.32.

    Absolute error below ``2e-3``, which past the series limit is a fraction
    of the radius the curve has left to spiral through.
    """
    f = (1.0 + 0.926 * z) / (2.0 + 1.792 * z + 3.104 * z**2)
    g = 1.0 / (2.0 + 4.142 * z + 3.492 * z**2 + 6.670 * z**3)
    phase = math.pi * z**2 / 2.0
    return (
        0.5 + f * math.sin(phase) - g * math.cos(phase),
        0.5 - f * math.cos(phase) - g * math.sin(phase),
    )
