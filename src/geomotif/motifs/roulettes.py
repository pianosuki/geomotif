"""Roulettes: what one circle draws while rolling around another.

Four classical curves, the toy that made them famous, and the generalization
that swallows all five.

:class:`Epicycles` is the one to reach for when nothing else fits. Stack any
number of rotating arms, each with its own radius, frequency and phase, and
plot the tip: that is a hypotrochoid with two arms, an epitrochoid with the
middle one reversed, a planetary system with three, and a Fourier series with
as many as you like. Every other class in this module is a friendlier name for
a particular pair of arms.

These curves only close if the two radii are commensurate, so ``outer`` and
``inner`` are whole numbers here. Their ratio in lowest terms is what decides
how many revolutions it takes -- ``inner // gcd(outer, inner)`` of them -- and
the classes work that out for themselves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from ..bases import Curve, ParametricMotif
from ..core.registry import register

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ..core.types import Point

__all__ = [
    "Epicycles",
    "Epicycloid",
    "Epitrochoid",
    "Hypocycloid",
    "Hypotrochoid",
    "Spirograph",
]


def _closing_turns(outer: int, inner: int) -> int:
    """Return the revolutions a wheel of ``inner`` teeth needs to close.

    The tracing point comes home when the wheel has made a whole number of
    its own turns *and* a whole number of trips around the ring, which first
    happens after the denominator of ``outer / inner`` in lowest terms.
    """
    return inner // math.gcd(outer, inner)


def _hypotrochoid_point(
    t: float,
    outer: float,
    inner: float,
    offset: float,
    center: Point,
) -> Point:
    """Return the point traced at angle ``t`` by a wheel rolling *inside* a ring."""
    difference = outer - inner
    cx, cy = center
    return (
        cx + difference * math.cos(t) + offset * math.cos(difference / inner * t),
        cy + difference * math.sin(t) - offset * math.sin(difference / inner * t),
    )


def _epitrochoid_point(
    t: float,
    outer: float,
    inner: float,
    offset: float,
    center: Point,
) -> Point:
    """Return the point traced at angle ``t`` by a wheel rolling *outside* a ring."""
    total = outer + inner
    cx, cy = center
    return (
        cx + total * math.cos(t) - offset * math.cos(total / inner * t),
        cy + total * math.sin(t) - offset * math.sin(total / inner * t),
    )


@register("roulette.hypotrochoid", family="roulette")
@dataclass(frozen=True, slots=True)
class Hypotrochoid(ParametricMotif):
    """A pen fixed to a wheel rolling around the *inside* of a ring.

    The Spirograph curve, in its mathematical clothes -- see
    :class:`Spirograph` for the version that takes tooth counts. ``offset``
    is free to exceed ``inner``, which puts the pen outside the wheel's rim
    and is not something the physical toy can do.

    Parameters
    ----------
    outer : int, optional
        Radius of the fixed ring.
    inner : int, optional
        Radius of the rolling wheel. Must be less than ``outer``.
    offset : float, optional
        Distance from the wheel's center to the pen. Equal to ``inner``
        gives the :class:`Hypocycloid`; zero gives a circle.
    center : (float, float), optional
        Center of the fixed ring.
    """

    closed: ClassVar[bool] = True

    outer: int = 100
    inner: int = 30
    offset: float = 45.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_radii(self.outer, self.inner, inside=True)

    @override
    def position(self, u: float) -> Point:
        t = u * _closing_turns(self.outer, self.inner) * math.tau
        return _hypotrochoid_point(t, self.outer, self.inner, self.offset, self.center)

    @override
    def sweep_turns(self) -> float:
        # The pen goes round faster than the wheel does; sampling has to keep
        # up with the pen, not with the trip around the ring.
        rate = abs(self.outer - self.inner) / self.inner
        return _closing_turns(self.outer, self.inner) * max(1.0, rate)


@register("roulette.epitrochoid", family="roulette")
@dataclass(frozen=True, slots=True)
class Epitrochoid(ParametricMotif):
    """A pen fixed to a wheel rolling around the *outside* of a ring.

    The same construction as :class:`Hypotrochoid` with the wheel on the far
    side, which turns the scalloped rosette inside out into a ring of petals.
    Layered with phase offsets, this is the curve underneath every guilloche
    pattern on a banknote.

    Parameters
    ----------
    outer : int, optional
        Radius of the fixed ring.
    inner : int, optional
        Radius of the rolling wheel.
    offset : float, optional
        Distance from the wheel's center to the pen. Equal to ``inner``
        gives the :class:`Epicycloid`; zero gives a circle.
    center : (float, float), optional
        Center of the fixed ring.
    """

    closed: ClassVar[bool] = True

    outer: int = 100
    inner: int = 30
    offset: float = 45.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_radii(self.outer, self.inner, inside=False)

    @override
    def position(self, u: float) -> Point:
        t = u * _closing_turns(self.outer, self.inner) * math.tau
        return _epitrochoid_point(t, self.outer, self.inner, self.offset, self.center)

    @override
    def sweep_turns(self) -> float:
        rate = (self.outer + self.inner) / self.inner
        return _closing_turns(self.outer, self.inner) * rate


@register("roulette.hypocycloid", family="roulette")
@dataclass(frozen=True, slots=True)
class Hypocycloid(ParametricMotif):
    """A point *on the rim* of a wheel rolling inside a ring: a cusped star.

    :class:`Hypotrochoid` with the pen exactly on the rim, which is what puts
    a cusp wherever the rim touches the ring. Three cusps is the
    :class:`~geomotif.motifs.curves.Deltoid`, four is the
    :class:`~geomotif.motifs.curves.Astroid`, and both have their own class
    with a scale you can set directly.

    Parameters
    ----------
    outer : int, optional
        Radius of the fixed ring.
    inner : int, optional
        Radius of the rolling wheel. ``outer / inner`` in lowest terms gives
        the cusp count as its numerator.
    center : (float, float), optional
        Center of the fixed ring.
    """

    closed: ClassVar[bool] = True

    outer: int = 100
    inner: int = 30
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_radii(self.outer, self.inner, inside=True)

    @override
    def position(self, u: float) -> Point:
        t = u * _closing_turns(self.outer, self.inner) * math.tau
        return _hypotrochoid_point(t, self.outer, self.inner, self.inner, self.center)

    @override
    def sweep_turns(self) -> float:
        rate = abs(self.outer - self.inner) / self.inner
        return _closing_turns(self.outer, self.inner) * max(1.0, rate)


@register("roulette.epicycloid", family="roulette")
@dataclass(frozen=True, slots=True)
class Epicycloid(ParametricMotif):
    """A point *on the rim* of a wheel rolling outside a ring: a ring of petals.

    One cusp is the :class:`~geomotif.motifs.curves.Cardioid`, two is the
    :class:`~geomotif.motifs.curves.Nephroid`, and the general case is the
    flower shape a gear leaves when it rolls around another one.

    Parameters
    ----------
    outer : int, optional
        Radius of the fixed ring.
    inner : int, optional
        Radius of the rolling wheel. ``outer / inner`` in lowest terms gives
        the petal count as its numerator.
    center : (float, float), optional
        Center of the fixed ring.
    """

    closed: ClassVar[bool] = True

    outer: int = 100
    inner: int = 30
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        _check_radii(self.outer, self.inner, inside=False)

    @override
    def position(self, u: float) -> Point:
        t = u * _closing_turns(self.outer, self.inner) * math.tau
        return _epitrochoid_point(t, self.outer, self.inner, self.inner, self.center)

    @override
    def sweep_turns(self) -> float:
        rate = (self.outer + self.inner) / self.inner
        return _closing_turns(self.outer, self.inner) * rate


@register("spirograph", family="roulette")
@dataclass(frozen=True, slots=True)
class Spirograph(ParametricMotif):
    """The toy, in the toy's own terms: a ring, a wheel and a hole.

    Exactly a :class:`Hypotrochoid`, parameterized the way the box is. Tooth
    counts are what actually determine the pattern -- the ring and wheel that
    come in the tin have 96 and 36 teeth, and their ratio is why that
    particular rosette is the one everyone remembers drawing.

    Parameters
    ----------
    ring_teeth : int, optional
        Teeth on the fixed ring.
    wheel_teeth : int, optional
        Teeth on the rolling wheel. Fewer than the ring's.
    hole : float, optional
        Which hole the pen goes in, as a fraction of the wheel's radius from
        its center. ``1`` is the rim, ``0`` is the middle and draws a circle.
    ring_radius : float, optional
        Physical size of the ring, which sets the size of the drawing.
    center : (float, float), optional
        Center of the ring.
    """

    closed: ClassVar[bool] = True

    ring_teeth: int = 96
    wheel_teeth: int = 36
    hole: float = 0.7
    ring_radius: float = 150.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.ring_teeth < 3:
            raise ValueError(f"ring_teeth must be >= 3, got {self.ring_teeth}")
        if not 1 <= self.wheel_teeth < self.ring_teeth:
            raise ValueError(
                f"wheel_teeth must be at least 1 and fewer than ring_teeth "
                f"({self.ring_teeth}), got {self.wheel_teeth}"
            )
        if not 0.0 <= self.hole <= 1.0:
            raise ValueError(f"hole must be between 0 and 1, got {self.hole}")
        if self.ring_radius <= 0.0:
            raise ValueError(f"ring_radius must be > 0, got {self.ring_radius}")

    def wheel_radius(self) -> float:
        """Return the rolling wheel's radius, scaled from the tooth counts."""
        return self.ring_radius * self.wheel_teeth / self.ring_teeth

    @override
    def position(self, u: float) -> Point:
        wheel = self.wheel_radius()
        t = u * _closing_turns(self.ring_teeth, self.wheel_teeth) * math.tau
        return _hypotrochoid_point(t, self.ring_radius, wheel, self.hole * wheel, self.center)

    @override
    def sweep_turns(self) -> float:
        rate = (self.ring_teeth - self.wheel_teeth) / self.wheel_teeth
        return _closing_turns(self.ring_teeth, self.wheel_teeth) * max(1.0, rate)


@register("epicycles", family="roulette")
@dataclass(frozen=True, slots=True)
class Epicycles(ParametricMotif):
    """Rotating arms stacked tip to tail; the path of the last tip.

    Each arm is ``(radius, frequency, phase)``: how long it is, how many
    revolutions it makes per turn of the whole system, and where it starts.
    Negative frequencies turn the other way.

    This is the general case the rest of this module is made of. Two arms
    give every trochoid; a few more give the Ptolemaic orbit of a moon of a
    moon; several dozen give a Fourier series, which is to say any closed
    curve at all::

        Epicycles(arms=((100.0, 1.0, 0.0), (40.0, 5.0, 0.0), (18.0, -9.0, 0.0)))

    Parameters
    ----------
    arms : tuple of (float, float, float), optional
        The arms, outermost effect last. At least one.
    turns : float, optional
        Revolutions of the slowest hand, in effect: the parameter sweeps
        ``turns`` full cycles. Only worth changing when the frequencies are
        not whole numbers, since whole ones already close in one turn.
    center : (float, float), optional
        Where the first arm is anchored.
    """

    arms: tuple[tuple[float, float, float], ...] = (
        (120.0, 1.0, 0.0),
        (30.0, 7.0, 0.0),
        (12.0, 13.0, 0.0),
    )
    turns: float = 1.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.arms:
            raise ValueError("arms must contain at least one (radius, frequency, phase)")
        for index, arm in enumerate(self.arms):
            try:
                _, _, _ = arm
            except (TypeError, ValueError):
                raise ValueError(
                    f"arms[{index}] must be a (radius, frequency, phase) triple, got {arm!r}"
                ) from None
        if self.turns == 0.0:
            raise ValueError("turns must be non-zero; a zero sweep draws a single point")

    @override
    def position(self, u: float) -> Point:
        t = u * self.turns * math.tau
        x, y = self.center
        for radius, frequency, phase in self.arms:
            angle = frequency * t + phase
            x += radius * math.cos(angle)
            y += radius * math.sin(angle)
        return (x, y)

    @override
    def sweep_turns(self) -> float:
        fastest = max(abs(frequency) for _, frequency, _ in self.arms)
        return abs(self.turns) * max(1.0, fastest)

    @override
    def curves(self) -> Iterable[Curve]:
        # Whether the tip comes home depends on the numbers, so it cannot be a
        # class attribute the way it is everywhere else in the catalogue: with
        # whole frequencies over a whole number of turns every arm is back
        # where it started, and otherwise the stroke genuinely has two ends.
        closes = float(self.turns).is_integer() and all(
            float(frequency).is_integer() for _, frequency, _ in self.arms
        )
        yield Curve(self.position, closed=closes, turns=self.sweep_turns())


def _check_radii(outer: int, inner: int, *, inside: bool) -> None:
    """Validate a roulette's ring and wheel radii."""
    if inner < 1:
        raise ValueError(f"inner must be >= 1, got {inner}")
    if outer < 1:
        raise ValueError(f"outer must be >= 1, got {outer}")
    if inside and inner >= outer:
        raise ValueError(
            f"inner must be less than outer ({outer}) for a wheel rolling inside it, got {inner}"
        )
