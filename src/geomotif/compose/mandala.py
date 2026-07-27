"""Rings, symmetry groups and snowflakes: arranging a motif rather than drawing one.

Four composers and one value type, which between them cover most of what
people mean by "mandala".

:class:`Mandala` is the general one -- a list of :class:`Ring` s, each saying
what to repeat, how many times, and how far out. :class:`Kaleidoscope` is the
single-unit case, under a named symmetry group. :class:`SpokePattern` and
:class:`LayeredRings` are the scaffolding a mandala is usually hung on, worth
having because they are what you reach for first and neither deserves ten
lines at the call site. :class:`Snowflake` is the odd one out: it grows its
own arm if you do not give it one, because a snowflake's arm is a random
dendrite and there is no other motif in the library that is one.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..core.motif import Motif, SupportsBuild
from ..core.registry import register, spec
from ..core.transform import Affine, radial_repeat
from ..core.types import Design, Path
from ..motifs import Ellipse, RegularPolygon, Rose
from ..motifs._common import arc_points

if TYPE_CHECKING:
    from ..core.types import Point

__all__ = [
    "Kaleidoscope",
    "LayeredRings",
    "Mandala",
    "Ring",
    "Snowflake",
    "SpokePattern",
]

#: Ceiling on how many copies one composition may place, so a mistyped count
#: raises rather than multiplying a thousand-point motif by a thousand.
_MAX_COPIES = 2_000


def _check_count(owner: str, count: int, *, name: str = "count") -> None:
    if count < 1:
        raise ValueError(f"{owner} {name} must be >= 1, got {count}")
    if count > _MAX_COPIES:
        raise ValueError(f"{owner} {name} must be <= {_MAX_COPIES}, got {count}")


def _check_buildable(owner: str, motif: object) -> None:
    if not isinstance(motif, SupportsBuild):
        raise TypeError(
            f"{owner} needs something with a build() method, got {type(motif).__name__}"
        )


def _order_of(owner: str, group: str) -> tuple[int, bool]:
    """Return the order of a ``Cn``/``Dn`` group and whether it mirrors."""
    name = group.strip().upper()
    if name[:1] not in ("C", "D") or not name[1:].isdigit():
        raise ValueError(f"{owner} group must look like 'C6' or 'D6', got {group!r}")
    order = int(name[1:])
    _check_count(owner, order, name="group order")
    return order, name[:1] == "D"


@dataclass(frozen=True, slots=True)
class Ring:
    """One ring of a :class:`Mandala`: what to repeat, how often, how far out.

    Parameters
    ----------
    unit : Motif or anything with ``build()``
        The unit to repeat.
    count : int
        How many copies to place around the ring.
    radius : float
        Distance from the mandala's middle to each copy's own origin.
    phase : float, optional
        Angle of the first copy, in radians.
    spin : float, optional
        Extra rotation applied to every copy, on top of whichever way
        :attr:`face` leaves it pointing.
    face : bool, optional
        Turn each copy to face outward, so a petal drawn along the x-axis
        points away from the middle wherever it lands. Turn this off to keep
        every copy at its original angle, which is what you want for a shape
        that has to stay upright.
    mirror : bool, optional
        Also place each copy's reflection in its own ray, giving the ring
        mirror symmetry as well as rotational.
    """

    unit: SupportsBuild
    count: int
    radius: float
    phase: float = 0.0
    spin: float = 0.0
    face: bool = True
    mirror: bool = False

    def __post_init__(self) -> None:
        _check_count("Ring", self.count)
        _check_buildable("Ring", self.unit)

    def placements(self, center: Point = (0.0, 0.0)) -> tuple[Affine, ...]:
        """Return the transform that puts each copy where it belongs."""
        cx, cy = center
        out: list[Affine] = []
        for index in range(self.count):
            theta = self.phase + math.tau * index / self.count
            # Carry the unit out along the x-axis, then swing the whole arm
            # round to its own angle. A copy that is not meant to face
            # outward has that swing undone on the unit itself.
            spin = self.spin if self.face else self.spin - theta
            placed = (
                Affine.translate(cx, cy)
                @ Affine.rotate(theta)
                @ Affine.translate(self.radius, 0.0)
                @ Affine.rotate(spin)
            )
            out.append(placed)
            if self.mirror:
                out.append(Affine.mirror(theta, through=center) @ placed)
        return tuple(out)


#: What the gallery builds: a rose in the middle, a ring of petals turned to
#: face outward, and a rim of triangles doing the same.
_EXAMPLE_RINGS = (
    Ring(Rose(n=6, size=76.0), count=1, radius=0.0),
    Ring(Ellipse(rx=27.0, ry=11.0), count=12, radius=74.0),
    Ring(RegularPolygon(sides=3, radius=17.0), count=24, radius=128.0),
)


@register("mandala", family="mandala", example={"rings": _EXAMPLE_RINGS})
@dataclass(frozen=True, slots=True)
class Mandala(Motif):
    """Concentric rings of repeated motifs.

    The workhorse. Each :class:`Ring` is built once and then placed by an
    affine transform per copy, so a hundred-fold ring costs one build and a
    hundred cheap transforms rather than a hundred builds.

    Parameters
    ----------
    rings : tuple of Ring
        The rings, innermost first by convention. Nothing enforces an order,
        and rings are free to overlap.
    center : (float, float), optional
        Middle of the figure.
    """

    rings: tuple[Ring, ...]
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.rings:
            raise ValueError(f"{type(self).__name__} needs at least one ring")

    @override
    def build(self) -> Design:
        paths: list[Path] = []
        points: list[Point] = []
        for ring in self.rings:
            unit = ring.unit.build()
            for place in ring.placements(self.center):
                copy = unit.transformed(place)
                paths.extend(copy.paths)
                points.extend(copy.points)
        return Design(tuple(paths), tuple(points), meta=spec(self))


@register(
    "kaleidoscope",
    family="mandala",
    example={"unit": Rose(n=5, d=2, size=150.0), "group": "C5"},
)
@dataclass(frozen=True, slots=True)
class Kaleidoscope(Motif):
    """One motif, repeated under a cyclic or dihedral symmetry group.

    ``"C6"`` turns the motif six ways; ``"D6"`` turns it six ways and mirrors
    each, giving twelve copies and the look of a real kaleidoscope, where
    every second image is reflected because it has bounced off a mirror an
    odd number of times.

    Parameters
    ----------
    unit : Motif or anything with ``build()``
        The fundamental domain: the one wedge everything else is made from.
    group : str, optional
        ``"Cn"`` for n-fold rotation, ``"Dn"`` for rotation plus mirrors.
    center : (float, float), optional
        Point the symmetry is about.
    """

    unit: SupportsBuild
    group: str = "D6"
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_buildable(owner, self.unit)
        _order_of(owner, self.group)

    @override
    def build(self) -> Design:
        order, mirror = _order_of(type(self).__name__, self.group)
        repeated = radial_repeat(self.unit.build(), order, about=self.center, mirror=mirror)
        return Design(repeated.paths, repeated.points, meta=spec(self))


@register("spoke-pattern", family="mandala")
@dataclass(frozen=True, slots=True)
class SpokePattern(Motif):
    """Radial lines from an inner circle to an outer one.

    The bones of most mandalas, and a decent motif on its own. With
    :attr:`stagger` set, every other spoke stops short, which is the ticked
    dial of a compass rose.

    Parameters
    ----------
    count : int, optional
        How many spokes.
    inner, outer : float, optional
        Where each spoke starts and ends.
    stagger : float, optional
        How far short every second spoke stops, as a fraction of its length.
        ``0`` draws every spoke full length; ``0.5`` halves the alternates.
    rotation : float, optional
        Angle of the first spoke, in radians.
    center : (float, float), optional
        Point they radiate from.
    """

    count: int = 24
    inner: float = 40.0
    outer: float = 140.0
    stagger: float = 0.0
    rotation: float = 0.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_count(owner, self.count)
        if self.inner < 0.0:
            raise ValueError(f"{owner} inner must be >= 0, got {self.inner}")
        if self.outer <= self.inner:
            raise ValueError(f"{owner} outer {self.outer} must be beyond inner {self.inner}")
        if not 0.0 <= self.stagger < 1.0:
            raise ValueError(f"{owner} stagger must be in [0, 1), got {self.stagger}")

    @override
    def build(self) -> Design:
        cx, cy = self.center
        span = self.outer - self.inner
        paths: list[Path] = []
        for index in range(self.count):
            theta = self.rotation + math.tau * index / self.count
            reach = self.outer - (span * self.stagger if index % 2 else 0.0)
            paths.append(
                Path(
                    (
                        (cx + self.inner * math.cos(theta), cy + self.inner * math.sin(theta)),
                        (cx + reach * math.cos(theta), cy + reach * math.sin(theta)),
                    )
                )
            )
        return Design(tuple(paths), meta=spec(self))


@register("layered-rings", family="mandala")
@dataclass(frozen=True, slots=True)
class LayeredRings(Motif):
    """Concentric circles: the other half of a mandala's scaffolding.

    Parameters
    ----------
    count : int, optional
        How many circles.
    inner : float, optional
        Radius of the innermost.
    step : float, optional
        Radial gap between the first two circles.
    growth : float, optional
        Multiplier applied to the gap each time out. ``1`` gives evenly
        spaced rings; above ``1`` they spread as they go, which reads as
        depth.
    center : (float, float), optional
        Middle of the figure.
    """

    count: int = 7
    inner: float = 24.0
    step: float = 20.0
    growth: float = 1.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_count(owner, self.count)
        if self.inner <= 0.0:
            raise ValueError(f"{owner} inner must be > 0, got {self.inner}")
        if self.step <= 0.0:
            raise ValueError(f"{owner} step must be > 0, got {self.step}")
        if self.growth <= 0.0:
            raise ValueError(f"{owner} growth must be > 0, got {self.growth}")

    def radii(self) -> tuple[float, ...]:
        """Return each circle's radius, innermost first."""
        out: list[float] = []
        radius, gap = self.inner, self.step
        for _ in range(self.count):
            out.append(radius)
            radius += gap
            gap *= self.growth
        return tuple(out)

    @override
    def build(self) -> Design:
        return Design(
            tuple(
                Path(arc_points(self.center, radius, 0.0, math.tau)[:-1], closed=True)
                for radius in self.radii()
            ),
            meta=spec(self),
        )


@register("snowflake", family="mandala")
@dataclass(frozen=True, slots=True)
class Snowflake(Motif):
    """Six identical arms, each mirrored in its own axis.

    A real snowflake is sixfold because a water molecule is, and identical
    across its six arms because every arm grew in the same air. Both facts
    are in the construction: one arm is grown, then reflected in its own axis
    and turned six ways.

    Give it a ``unit`` to use that as the arm. Otherwise it grows a
    dendrite -- a spine with side branches at sixty degrees, each of which may
    branch again -- from :attr:`seed`, so the same seed always yields the same
    crystal and a different one never does.

    Parameters
    ----------
    unit : Motif or anything with ``build()``, optional
        The arm, drawn along the positive x-axis and mirrored in it.
    size : float, optional
        Length of the grown arm's spine. Ignored when a unit is given.
    branches : int, optional
        Side branches per spine. Ignored when a unit is given.
    depth : int, optional
        How many times a branch may branch again. Ignored when a unit is
        given.
    seed : int, optional
        Fixes the growth. The generator is private to the call, so nothing
        else in the program can change what you get.
    center : (float, float), optional
        Middle of the crystal.
    """

    unit: SupportsBuild | None = None
    size: float = 150.0
    branches: int = 4
    depth: int = 2
    seed: int = 0
    center: Point = field(default=(0.0, 0.0), kw_only=True)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.unit is not None:
            _check_buildable(owner, self.unit)
        if self.size <= 0.0:
            raise ValueError(f"{owner} size must be > 0, got {self.size}")
        if self.branches < 0:
            raise ValueError(f"{owner} branches must be >= 0, got {self.branches}")
        if not 0 <= self.depth <= 4:
            # Each level multiplies the stroke count by twice the branch
            # count, so five levels of four branches is a third of a million
            # strokes -- a limit rather than a preference.
            raise ValueError(f"{owner} depth must be in [0, 4], got {self.depth}")

    def arm(self) -> Design:
        """Return the single arm, before it is mirrored and repeated."""
        if self.unit is not None:
            return self.unit.build()
        rng = random.Random(self.seed)
        return Design(tuple(self._grow(rng, self.center, 0.0, self.size, self.depth)))

    def _grow(
        self, rng: random.Random, start: Point, angle: float, length: float, depth: int
    ) -> list[Path]:
        end = (start[0] + length * math.cos(angle), start[1] + length * math.sin(angle))
        strokes = [Path((start, end))]
        if depth <= 0:
            return strokes
        for index in range(self.branches):
            # Branch feet march out along the spine; the jitter is what keeps
            # the crystal from reading as a comb.
            along = (index + 1) / (self.branches + 1) * rng.uniform(0.85, 1.15)
            if not 0.0 < along < 1.0:
                continue
            foot = (
                start[0] + length * along * math.cos(angle),
                start[1] + length * along * math.sin(angle),
            )
            reach = length * (1.0 - along) * rng.uniform(0.45, 0.8)
            for side in (1.0, -1.0):
                strokes.extend(
                    self._grow(rng, foot, angle + side * math.pi / 3.0, reach, depth - 1)
                )
        return strokes

    @override
    def build(self) -> Design:
        arm = self.arm()
        # Mirror in the arm's own axis first, then turn the pair six ways:
        # reflecting afterwards would put the mirror lines between the arms
        # instead of down them.
        paired = arm + arm.transformed(Affine.mirror(0.0, through=self.center))
        repeated = radial_repeat(paired, 6, about=self.center)
        return Design(repeated.paths, repeated.points, meta=spec(self))
