"""The named curves: the ones that earned a name before they earned a use.

Hearts, lemniscates, ovals, astroids, cycloids -- shapes that turn up in
optics, in mechanisms and on tombstones, and that people go looking for by
name. Each one is a formula and nothing else, so each one is a base class and
three lines.

Two conventions hold throughout this module.

``size`` **is the curve's largest extent.** A curve with a single free scale
takes ``size``, and at ``size=100`` its bounding box measures 100 across its
longer axis -- so a heart and a butterfly composed at the same ``size`` come
out the same size. Curves whose shape depends on the *ratio* of two numbers
(:class:`CassiniOval`, :class:`Limacon`, :class:`Folium`) take those two
numbers directly instead, because a third scale knob would only be a way of
saying the same thing twice.

``center`` **is the curve's own origin**, not the middle of its bounding box:
the cusp of a cardioid, the crossing point of a lemniscate, the first contact
point of a cycloid. That is the point the formula is written about, and the
point that stays put when you change the other parameters. Call
:meth:`~geomotif.Design.fit` if what you want is the box centered.

None of these takes a rotation. Turning a design is
:meth:`~geomotif.Design.transformed` with :meth:`~geomotif.Affine.rotate`,
and a per-motif copy of it would only be a worse one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, override

from ..bases import Curve, MultiCurveMotif, ParametricMotif
from ..core.registry import register
from ._common import polar_point

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ..core.types import Point

__all__ = [
    "Astroid",
    "BowCurve",
    "Butterfly",
    "Cardioid",
    "CassiniOval",
    "Cochleoid",
    "Cornoid",
    "Cycloid",
    "Deltoid",
    "FishCurve",
    "Folium",
    "Heart",
    "HeartForm",
    "Lemniscate",
    "LemniscateOfGerono",
    "Limacon",
    "Nephroid",
    "Trochoid",
    "Witch",
]

#: Which of the two traditional heart curves to draw.
type HeartForm = Literal["classic", "cardioid"]

# Largest extent of each curve at unit parameters, which is what turns `size`
# into a real measurement. Most are exact -- an astroid spans `2a`, a heart's
# `16*sin(t)**3` spans `32` -- and the two that have no closed form were
# measured numerically to twelve digits. The test suite rebuilds every curve
# and checks its bounding box against `size`, so a wrong constant here fails
# loudly rather than quietly drawing something the wrong size.
_ASTROID_EXTENT = 2.0
_BOW_EXTENT = 4.0 / (3.0 * math.sqrt(3.0))
_BUTTERFLY_EXTENT = 7.305921166724523
_CARDIOID_EXTENT = 3.0 * math.sqrt(3.0) / 2.0
_COCHLEOID_EXTENT = 1.4492227075519726
_CORNOID_EXTENT = 2.0 * math.sqrt(2.0)
_DELTOID_EXTENT = 3.0 * math.sqrt(3.0)
_FISH_EXTENT = 1.0 + 3.0 / (2.0 * math.sqrt(2.0))
_HEART_CLASSIC_EXTENT = 32.0
_LEMNISCATE_EXTENT = 2.0
_NEPHROID_EXTENT = 8.0

#: How far the butterfly has to be swept before it closes: the ``sin(t/12)``
#: term has a period twelve times longer than everything around it.
_BUTTERFLY_SPAN = 24.0 * math.pi


@register("heart", family="curve")
@dataclass(frozen=True, slots=True)
class Heart(ParametricMotif):
    """A heart, in either of the two shapes that go by the name.

    ``"classic"`` is the valentine: the ``16*sin(t)**3`` curve, with the
    dimple on top and a proper point at the bottom. ``"cardioid"`` is
    ``r = 1 - sin(theta)``, which is the same cardioid as
    :class:`Cardioid` stood on end -- rounder, symmetrical, and the one that
    falls out of the maths rather than out of a greetings card.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve.
    form : {"classic", "cardioid"}, optional
        Which heart to draw.
    center : (float, float), optional
        The curve's own origin, which for both forms is the dimple between
        the two lobes.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    form: HeartForm = "classic"
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        match self.form:
            case "classic":
                scale = self.size / _HEART_CLASSIC_EXTENT
                cx, cy = self.center
                return (
                    cx + scale * 16.0 * math.sin(u) ** 3,
                    cy
                    + scale
                    * (
                        13.0 * math.cos(u)
                        - 5.0 * math.cos(2.0 * u)
                        - 2.0 * math.cos(3.0 * u)
                        - math.cos(4.0 * u)
                    ),
                )
            case "cardioid":
                scale = self.size / _CARDIOID_EXTENT
                return polar_point(u, scale * (1.0 - math.sin(u)), center=self.center)
            case _:
                raise ValueError(f"form must be 'classic' or 'cardioid', got {self.form!r}")


@register("cardioid", family="curve")
@dataclass(frozen=True, slots=True)
class Cardioid(ParametricMotif):
    """The heart-shaped ``r = 1 + cos(theta)``: one circle rolled around another.

    An epicycloid with a single cusp, and the shape of the bright caustic in
    a coffee cup. Also the limiting case of :class:`Limacon` where the inner
    loop has shrunk to a point.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve.
    center : (float, float), optional
        The cusp, which is where the curve's own origin sits.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _CARDIOID_EXTENT
        return polar_point(u, scale * (1.0 + math.cos(u)), center=self.center)


@register("lemniscate", family="curve")
@dataclass(frozen=True, slots=True)
class Lemniscate(ParametricMotif):
    """Bernoulli's lemniscate: the infinity symbol.

    The locus of points whose distances to two foci multiply to a constant --
    the one case of :class:`CassiniOval` where the two lobes have just met.
    Drawn from its rational parametrization rather than from
    ``r**2 = a**2 * cos(2*theta)``, which goes imaginary over half its range
    and would have to be stitched together from two arcs.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve: the full width across both lobes.
    center : (float, float), optional
        The crossing point in the middle.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _LEMNISCATE_EXTENT
        cos_u, sin_u = math.cos(u), math.sin(u)
        denominator = 1.0 + sin_u * sin_u
        cx, cy = self.center
        return (cx + scale * cos_u / denominator, cy + scale * sin_u * cos_u / denominator)


@register("lemniscate.gerono", family="curve")
@dataclass(frozen=True, slots=True)
class LemniscateOfGerono(ParametricMotif):
    """Gerono's lemniscate: the other figure eight, ``x**4 = x**2 - y**2``.

    Fatter and blunter than :class:`Lemniscate`, and far easier to say:
    ``x = cos(t)``, ``y = sin(t)*cos(t)``. Worth having both -- they are
    drawn interchangeably and they are not the same curve.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve: the full width across both lobes.
    center : (float, float), optional
        The crossing point in the middle.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _LEMNISCATE_EXTENT
        cx, cy = self.center
        return (cx + scale * math.cos(u), cy + scale * math.sin(u) * math.cos(u))


@register("cassini-oval", family="curve")
@dataclass(frozen=True, slots=True)
class CassiniOval(MultiCurveMotif):
    """Points whose distances to two foci *multiply* to a constant.

    An ellipse adds those distances; a Cassini oval multiplies them, and the
    difference is a shape that changes topology as the constant crosses the
    focal separation. Cassini proposed it for planetary orbits and was
    wrong, which has not stopped it being the more interesting curve.

    Three regimes, and the class draws each one honestly:

    * ``b > a`` -- a single closed loop, either an oval or, once
      ``b < a*sqrt(2)``, the pinched peanut.
    * ``b < a`` -- two separate loops, one around each focus, returned as two
      strokes rather than one path with an invented bridge between them.
    * ``b == a`` -- the loops have just touched, and the curve is Bernoulli's
      lemniscate. Rejected here, because that case is
      :class:`Lemniscate` and it draws it better.

    Parameters
    ----------
    a : float, optional
        Half the distance between the foci, which sit at ``(-a, 0)`` and
        ``(a, 0)`` relative to ``center``.
    b : float, optional
        Square root of the constant product. Compare it to ``a`` to pick the
        regime above.
    center : (float, float), optional
        Midpoint between the foci.
    """

    a: float = 70.0
    b: float = 80.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.a <= 0.0:
            raise ValueError(f"a must be > 0, got {self.a}")
        if self.b <= 0.0:
            raise ValueError(f"b must be > 0, got {self.b}")
        if self.a == self.b:
            raise ValueError(
                f"a == b == {self.a} is the degenerate case where the two lobes touch; "
                f"that curve is Lemniscate(size=...), which draws it in one smooth stroke"
            )

    @override
    def curves(self) -> Iterable[Curve]:
        if self.b > self.a:
            yield Curve(self._oval, domain=(0.0, math.tau), closed=True)
            return
        # Below the separation the radius is real only inside a wedge around
        # each focus, and both roots of r**2 are positive there -- so each lobe
        # is traced out along the far root and back along the near one.
        limit = math.acos(math.sqrt(1.0 - (self.b / self.a) ** 4)) / 2.0
        yield Curve(lambda u: self._lobe(u, limit, 0.0), closed=True)
        yield Curve(lambda u: self._lobe(u, limit, math.pi), closed=True)

    def _roots(self, theta: float) -> tuple[float, float]:
        """Return the far and near radii solving ``r**2`` at ``theta``.

        Both are clamped at zero: at the very edge of a lobe's wedge the two
        roots coincide, and rounding can push the quantity under either
        square root a few ulps negative.
        """
        a2 = self.a * self.a
        cos2 = math.cos(2.0 * theta)
        root = math.sqrt(max(0.0, a2 * a2 * (cos2 * cos2 - 1.0) + self.b**4))
        return (
            math.sqrt(max(0.0, a2 * cos2 + root)),
            math.sqrt(max(0.0, a2 * cos2 - root)),
        )

    def _oval(self, theta: float) -> Point:
        return polar_point(theta, self._roots(theta)[0], center=self.center)

    def _lobe(self, u: float, limit: float, offset: float) -> Point:
        if u <= 0.5:
            theta = -limit + 4.0 * limit * u
            radius = self._roots(theta)[0]
        else:
            theta = limit - 4.0 * limit * (u - 0.5)
            radius = self._roots(theta)[1]
        return polar_point(theta + offset, radius, center=self.center)


@register("limacon", family="curve")
@dataclass(frozen=True, slots=True)
class Limacon(ParametricMotif):
    """Pascal's snail, ``r = b + a*cos(theta)``, inner loop and all.

    One knob spans a whole family. ``abs(a) > abs(b)`` gives the looped
    limacon, whose inner loop is drawn correctly because a negative radius
    reflects onto the opposite ray rather than being clipped away.
    ``a == b`` is the :class:`Cardioid`. ``abs(b) >= 2*abs(a)`` is convex,
    with not even a dimple left.

    Parameters
    ----------
    a : float, optional
        Amplitude of the cosine term: how lopsided the curve is.
    b : float, optional
        Constant term: the radius the curve would have if ``a`` were zero.
    center : (float, float), optional
        The pole the radius is measured from.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    a: float = 100.0
    b: float = 60.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        return polar_point(u, self.b + self.a * math.cos(u), center=self.center)


@register("folium", family="curve")
@dataclass(frozen=True, slots=True)
class Folium(ParametricMotif):
    """The leaf curve ``r = cos(theta) * (4*a*sin(theta)**2 - b)``.

    Three named shapes live in two numbers: ``b == a`` is the trifolium's
    three petals, ``b == 4*a`` is the single-petalled simple folium, and
    ``b == 0`` is the bifolium's two. Anything between them is a legitimate
    intermediate.

    Half a revolution draws the whole thing. The other half retraces it,
    because ``r(theta + pi) == -r(theta)`` and a negative radius lands back
    on the ray it came from.

    Parameters
    ----------
    a : float, optional
        Scale of the petals.
    b : float, optional
        Petal count, in effect: see the shapes listed above.
    center : (float, float), optional
        The pole all the petals meet at.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.pi)
    closed: ClassVar[bool] = True

    a: float = 100.0
    b: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        radius = math.cos(u) * (4.0 * self.a * math.sin(u) ** 2 - self.b)
        return polar_point(u, radius, center=self.center)


@register("butterfly", family="curve")
@dataclass(frozen=True, slots=True)
class Butterfly(ParametricMotif):
    """Temple Fay's butterfly: twelve revolutions that draw two wings.

    ``r = exp(cos(theta)) - 2*cos(4*theta) + sin(theta/12)**5``. The last
    term has twelve times the period of the rest, so the curve takes twelve
    turns to close and each turn lays down a slightly different outline --
    which is the whole trick, and why it is the one transcendental doodle
    everybody recognizes.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve.
    center : (float, float), optional
        The body, which is where the pole sits.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, _BUTTERFLY_SPAN)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        radius = math.exp(math.cos(u)) - 2.0 * math.cos(4.0 * u) + math.sin(u / 12.0) ** 5
        return polar_point(u, radius * self.size / _BUTTERFLY_EXTENT, center=self.center)

    @override
    def sweep_turns(self) -> float:
        return _BUTTERFLY_SPAN / math.tau


@register("fish", family="curve")
@dataclass(frozen=True, slots=True)
class FishCurve(ParametricMotif):
    """A fish, tail and all, from ``x = cos(t) - sin(t)**2 / sqrt(2)``.

    The negative pedal of an ellipse at a particular eccentricity, which is a
    dry way of saying that the tail crosses itself exactly where a tail
    should.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve, nose to tail.
    center : (float, float), optional
        The curve's own origin, just behind the head.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _FISH_EXTENT
        cx, cy = self.center
        sin_u, cos_u = math.sin(u), math.cos(u)
        return (
            cx + scale * (cos_u - sin_u * sin_u / math.sqrt(2.0)),
            cy + scale * sin_u * cos_u,
        )


@register("bow", family="curve")
@dataclass(frozen=True, slots=True)
class BowCurve(ParametricMotif):
    """The bow, ``x**4 == x**2*y - y**3``: two loops pinched at the origin.

    Rational all the way through -- ``x = t - t**3``, ``y = t**2 - t**4`` --
    so it needs no trigonometry and no domain surgery.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve: the full width across both loops.
    center : (float, float), optional
        The pinch point where the two loops meet.
    """

    domain: ClassVar[tuple[float, float]] = (-1.0, 1.0)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _BOW_EXTENT
        cx, cy = self.center
        return (cx + scale * (u - u**3), cy + scale * (u**2 - u**4))


@register("astroid", family="curve")
@dataclass(frozen=True, slots=True)
class Astroid(ParametricMotif):
    """The four-cusped star ``x**(2/3) + y**(2/3) == 1``.

    A hypocycloid with four cusps, and the envelope of a ladder sliding down
    a wall -- which is why it turns up in string art without anyone having
    set out to draw it.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve: cusp to opposite cusp.
    center : (float, float), optional
        The middle, equidistant from all four cusps.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _ASTROID_EXTENT
        cx, cy = self.center
        return (cx + scale * math.cos(u) ** 3, cy + scale * math.sin(u) ** 3)


@register("deltoid", family="curve")
@dataclass(frozen=True, slots=True)
class Deltoid(ParametricMotif):
    """The three-cusped tricuspoid, Euler's curve of 1745.

    The hypocycloid a wheel traces rolling inside a ring three times its
    size, and the shape of the caustic you get reflecting parallel light off
    the inside of a cup.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve.
    center : (float, float), optional
        The middle, equidistant from all three cusps.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _DELTOID_EXTENT
        cx, cy = self.center
        return (
            cx + scale * (2.0 * math.cos(u) + math.cos(2.0 * u)),
            cy + scale * (2.0 * math.sin(u) - math.sin(2.0 * u)),
        )

    @override
    def sweep_turns(self) -> float:
        return 2.0


@register("nephroid", family="curve")
@dataclass(frozen=True, slots=True)
class Nephroid(ParametricMotif):
    """The kidney: the two-cusped epicycloid, ``r = 3cos(t) - cos(3t)``.

    The caustic of a circle lit from infinity, which is the bright cusp of
    light in a teacup that everyone has seen and few have named.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve, across the two lobes.
    center : (float, float), optional
        The middle, on the line joining the cusps.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _NEPHROID_EXTENT
        cx, cy = self.center
        return (
            cx + scale * (3.0 * math.cos(u) - math.cos(3.0 * u)),
            cy + scale * (3.0 * math.sin(u) - math.sin(3.0 * u)),
        )

    @override
    def sweep_turns(self) -> float:
        return 3.0


@register("cornoid", family="curve")
@dataclass(frozen=True, slots=True)
class Cornoid(ParametricMotif):
    """The cornoid, ``x = cos(t)cos(2t)``, ``y = sin(t)(2 + cos(2t))``.

    An oval with a pair of cusped loops tucked inside it, one near each end.
    A closed sextic, and one of the few named curves that looks like nothing
    else in the catalog.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve, along the oval.
    center : (float, float), optional
        The middle, between the two inner loops.
    """

    domain: ClassVar[tuple[float, float]] = (0.0, math.tau)
    closed: ClassVar[bool] = True

    size: float = 100.0
    center: Point = (0.0, 0.0)

    @override
    def position(self, u: float) -> Point:
        scale = self.size / _CORNOID_EXTENT
        cx, cy = self.center
        return (
            cx + scale * math.cos(u) * math.cos(2.0 * u),
            cy + scale * math.sin(u) * (2.0 + math.cos(2.0 * u)),
        )

    @override
    def sweep_turns(self) -> float:
        return 2.0


@register("cochleoid", family="curve")
@dataclass(frozen=True, slots=True)
class Cochleoid(ParametricMotif):
    """The snail shell ``r = sin(theta) / theta``, coiling in on itself.

    Every loop touches the pole and every loop is smaller than the last, so
    the whole family of them nests inside the first. The curve is symmetric
    about the x-axis -- ``r(-theta) == r(theta)`` -- so it is drawn from
    ``-loops`` turns to ``+loops``, in one stroke through the point at
    ``theta = 0``.

    Parameters
    ----------
    size : float, optional
        Largest extent of the curve. Set by the outermost loop, so adding
        loops makes the picture busier rather than bigger.
    loops : int, optional
        Loops drawn on each side of the axis.
    center : (float, float), optional
        The pole every loop passes through.
    """

    size: float = 100.0
    loops: int = 4
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.loops < 1:
            raise ValueError(f"loops must be >= 1, got {self.loops}")

    @override
    def position(self, u: float) -> Point:
        theta = (2.0 * u - 1.0) * self.loops * math.pi
        # sin(theta)/theta is removable at the pole, and the sweep lands on it
        # exactly whenever the sample count is even.
        ratio = 1.0 if theta == 0.0 else math.sin(theta) / theta
        return polar_point(theta, ratio * self.size / _COCHLEOID_EXTENT, center=self.center)

    @override
    def sweep_turns(self) -> float:
        return float(self.loops)


@register("cycloid", family="curve")
@dataclass(frozen=True, slots=True)
class Cycloid(ParametricMotif):
    """The path of a point on a rolling wheel's rim.

    The brachistochrone and the tautochrone at once: the curve a bead slides
    down fastest, and the curve it takes the same time to slide down from
    anywhere. Seventeenth-century mathematicians fought over it enough for it
    to be nicknamed the Helen of geometers.

    Parameters
    ----------
    radius : float, optional
        Radius of the rolling wheel. Each arch is ``tau * radius`` long and
        ``2 * radius`` tall.
    arches : int, optional
        How many arches to roll out.
    center : (float, float), optional
        Where the first arch touches the ground.
    """

    radius: float = 40.0
    arches: int = 3
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"radius must be > 0, got {self.radius}")
        if self.arches < 1:
            raise ValueError(f"arches must be >= 1, got {self.arches}")

    @override
    def position(self, u: float) -> Point:
        t = u * self.arches * math.tau
        cx, cy = self.center
        return (
            cx + self.radius * (t - math.sin(t)),
            cy + self.radius * (1.0 - math.cos(t)),
        )

    @override
    def sweep_turns(self) -> float:
        return float(self.arches)


@register("trochoid", family="curve")
@dataclass(frozen=True, slots=True)
class Trochoid(ParametricMotif):
    """The path of a point fixed to a rolling wheel, on the rim or off it.

    ``arm < radius`` is the curtate trochoid, the gentle wave a point inside
    the wheel traces. ``arm > radius`` is the prolate one, whose overhanging
    point runs backwards once per revolution and cuts a loop. ``arm ==
    radius`` is exactly the :class:`Cycloid`.

    Parameters
    ----------
    radius : float, optional
        Radius of the rolling wheel.
    arm : float, optional
        Distance from the wheel's center to the traced point.
    arches : int, optional
        How many revolutions to roll out.
    center : (float, float), optional
        Where the wheel's center starts, projected onto the ground.
    """

    radius: float = 40.0
    arm: float = 60.0
    arches: int = 3
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"radius must be > 0, got {self.radius}")
        if self.arm < 0.0:
            raise ValueError(f"arm must be >= 0, got {self.arm}")
        if self.arches < 1:
            raise ValueError(f"arches must be >= 1, got {self.arches}")

    @override
    def position(self, u: float) -> Point:
        t = u * self.arches * math.tau
        cx, cy = self.center
        return (
            cx + self.radius * t - self.arm * math.sin(t),
            cy + self.radius - self.arm * math.cos(t),
        )

    @override
    def sweep_turns(self) -> float:
        return float(self.arches)


@register("witch-of-agnesi", family="curve")
@dataclass(frozen=True, slots=True)
class Witch(ParametricMotif):
    """The witch of Agnesi: a bell curve with an exact algebraic definition.

    ``y = 8a**3 / (x**2 + 4a**2)``, constructed from a circle of radius ``a``
    sitting on the origin. Named a witch by a translator who mistook
    *versiera* for *avversiera*; the curve has been stuck with it since.

    It approaches its asymptote without reaching it, so it has to be cut off
    somewhere -- that is what ``extent`` is for.

    Parameters
    ----------
    radius : float, optional
        Radius of the generating circle. The peak sits at ``2 * radius``.
    extent : float, optional
        How far out to draw, in units of the peak's height. The curve has
        fallen to a fifth of its height by ``extent = 2``.
    center : (float, float), optional
        The point on the asymptote directly below the peak.
    """

    radius: float = 50.0
    extent: float = 3.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"radius must be > 0, got {self.radius}")
        if self.extent <= 0.0:
            raise ValueError(f"extent must be > 0, got {self.extent}")

    @override
    def position(self, u: float) -> Point:
        s = (2.0 * u - 1.0) * self.extent
        height = 2.0 * self.radius
        cx, cy = self.center
        return (cx + height * s, cy + height / (1.0 + s * s))
