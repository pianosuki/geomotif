"""Bases for motifs defined by a formula.

Three layers, each a special case of the one above it:

* :class:`MultiCurveMotif` -- the motif is several parametric strands at once
  (both branches of a Fermat spiral, both lobes of a Cassini oval).
* :class:`ParametricMotif` -- the single-strand case: one ``position(u)``.
* :class:`PolarMotif` -- the polar case: one ``radius(theta)``, with the
  cartesian conversion, the center offset and the theta range handled for you.

Implementing any of them buys arc-length resampling, every spacing curve, the
transform layer, export and CLI exposure -- the whole library -- for what is
usually a single line of maths.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, ClassVar, Self, override

from ..core.motif import Motif
from ..core.registry import spec
from ..core.sampling import densify, samples_for_turns
from ..core.types import Design, Path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from ..core.types import Point

__all__ = ["Curve", "MultiCurveMotif", "ParametricMotif", "PolarMotif"]


@dataclass(frozen=True, slots=True)
class Curve:
    """One parametric strand of a motif, and how densely to measure it.

    Parameters
    ----------
    position : callable
        Maps a parameter to a point. Called across ``domain`` only.
    domain : (float, float), optional
        Parameter range, inclusive at both ends. May run backwards.
    closed : bool, optional
        Whether the strand returns to where it started. A closed strand's
        final sample is dropped, since :class:`~geomotif.Path` implies the
        seam rather than storing it.
    turns : float, optional
        How far the strand winds, in whole turns. Only ever used to choose a
        sample count: a curve that bends more needs measuring more finely.
    """

    position: Callable[[float], Point]
    domain: tuple[float, float] = (0.0, 1.0)
    closed: bool = False
    turns: float = 1.0


@dataclass(frozen=True, slots=True)
class MultiCurveMotif(Motif, ABC):
    """Base for a motif made of several parametric strands.

    Implement :meth:`curves`; :meth:`build` measures each strand and returns
    one :class:`~geomotif.Path` per strand.

    Notes
    -----
    Subclasses implement hooks rather than overriding :meth:`build`, and the
    bases validate inside :meth:`build` rather than in ``__post_init__``, both
    for the same reason: on Python 3.12 the zero-argument ``super()`` does not
    work inside a ``slots=True`` dataclass, so a subclass cannot reliably
    chain up to us. Nothing here ever requires it to.

    Every field on a base is keyword-only, so a subclass is free to declare
    its own parameters positionally without tripping over the "no non-default
    argument after a default one" rule.
    """

    #: Segments per strand -- a strand gets one more point than that, so both
    #: ends are included. ``None`` (default) scales density with the winding.
    resolution: int | None = field(default=None, kw_only=True)

    @abstractmethod
    def curves(self) -> Iterable[Curve]:
        """Return the strands this motif is made of. At least one."""

    @override
    def build(self) -> Design:
        if self.resolution is not None and self.resolution < 1:
            raise ValueError(f"resolution must be >= 1, got {self.resolution}")

        paths: list[Path] = []
        for curve in self.curves():
            samples = self.resolution or samples_for_turns(curve.turns)
            points = densify(curve.position, samples=samples, domain=curve.domain)
            if curve.closed:
                # The last sample lands back on the first; a closed Path implies
                # its seam, so keeping it would double a vertex.
                points = points[:-1]
            paths.append(Path(points, closed=curve.closed))

        if not paths:
            raise ValueError(f"{type(self).__name__}.curves() produced no curves")
        return Design(tuple(paths), meta=spec(self))


@dataclass(frozen=True, slots=True)
class ParametricMotif(MultiCurveMotif, ABC):
    """Base for a motif defined by a single ``position(u)``.

    Set :attr:`domain` and :attr:`closed` as class variables to describe the
    curve's shape; override :meth:`sweep_turns` if it winds more than once, so
    the sample density keeps up with it.

    Examples
    --------
    ::

        @register("astroid", family="curve")
        @dataclass(frozen=True, slots=True)
        class Astroid(ParametricMotif):
            domain = (0.0, math.tau)
            closed = True

            size: float = 1.0

            def position(self, u: float) -> Point:
                return (
                    self.size * math.cos(u) ** 3,
                    self.size * math.sin(u) ** 3,
                )
    """

    #: Parameter range handed to :meth:`position`.
    domain: ClassVar[tuple[float, float]] = (0.0, 1.0)
    #: Whether the curve returns to its starting point at the end of the domain.
    closed: ClassVar[bool] = False

    @abstractmethod
    def position(self, u: float) -> Point:
        """Return the point at parameter ``u``, which ranges over :attr:`domain`."""

    def sweep_turns(self) -> float:
        """Return how far the curve winds, in whole turns.

        Used only to pick a sample count. The default of one turn suits any
        curve that does not loop repeatedly; a spiral should return its actual
        revolution count so that a tightly wound one is still measured
        accurately.
        """
        return 1.0

    @override
    def curves(self) -> Iterable[Curve]:
        yield Curve(
            self.position,
            domain=self.domain,
            closed=self.closed,
            turns=self.sweep_turns(),
        )


@dataclass(frozen=True, slots=True)
class PolarMotif(ParametricMotif, ABC):
    """Base for a motif defined by a single ``radius(theta)``.

    The whole extensibility story in eight lines::

        @register("my-flower", family="polar")
        @dataclass(frozen=True, slots=True)
        class MyFlower(PolarMotif):
            k: float = 7.0

            def radius(self, theta: float) -> float:
                return math.sin(self.k * theta) + 0.4 * math.cos(17 * theta)

    Notes
    -----
    A negative radius **reflects**: the point is placed on the opposite ray,
    at ``theta + pi``. That is what the cartesian conversion does naturally,
    it is the convention every plot of ``r = cos(k*theta)`` assumes, and it is
    what makes the petal count of a rose come out right. Clip the radius
    yourself in :meth:`radius` if you want the other convention.

    The hook is named ``radius``, so a subclass cannot also have a field
    called ``radius`` -- the two would collide in the class body. In practice
    that never bites: a shape whose radius is a constant parameter rather
    than a function of ``theta`` is a circle or an arc, and those are
    parametric rather than polar for exactly this reason.
    """

    #: Point the curve is drawn around.
    center: Point = field(default=(0.0, 0.0), kw_only=True)
    #: Angle the sweep begins at, in radians.
    theta_start: float = field(default=0.0, kw_only=True)
    #: Angular sweep, in radians. Negative sweeps run clockwise.
    theta_span: float = field(default=math.tau, kw_only=True)

    @abstractmethod
    def radius(self, theta: float) -> float:
        """Return the radius at angle ``theta``, in radians."""

    def with_turns(self, turns: float, *, clockwise: bool = False) -> Self:
        """Return a copy sweeping ``turns`` revolutions in the given direction.

        The same thing as setting :attr:`theta_span` to ``turns * tau``, said
        the way a wound curve is usually described::

            LogarithmicSpiral(b=0.15).with_turns(5, clockwise=True)

        Parameters
        ----------
        turns : float
            Revolutions to sweep. Fractional turns are fine.
        clockwise : bool, optional
            Sweep direction. Counter-clockwise by default, matching the
            standard math convention the rest of the library uses.
        """
        span = math.tau * turns
        return replace(self, theta_span=-span if clockwise else span)

    @override
    def position(self, u: float) -> Point:
        theta = self.theta_start + self.theta_span * u
        radius = self.radius(theta)
        cx, cy = self.center
        return (cx + radius * math.cos(theta), cy + radius * math.sin(theta))

    @override
    def sweep_turns(self) -> float:
        return abs(self.theta_span) / math.tau
