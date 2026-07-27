"""Spacing curves that control the distribution of points along a path.

A spacing curve is a monotonic mapping of normalized progress ``t`` in
[0, 1] to eased progress in [0, 1], with ``f(0) == 0`` and ``f(1) == 1``.
The eased value selects each point's position as a fraction of the path's
arc length, so the shape of the curve directly controls the gap between
consecutive points:

* ``f(t) = t``            -> equal spacing
* slow start / fast end   -> spacing gradually increases
* fast start / slow end   -> spacing gradually decreases

Because resampling is generic over polylines, these curves apply to every
motif in the library -- spirals, fractals, tilings and string art alike.
"""

from __future__ import annotations

import itertools
import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, final, override

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = [
    "CircularSpacing",
    "CompositeSpacing",
    "CubicSpacing",
    "ExponentialSpacing",
    "LinearSpacing",
    "Mode",
    "PowerSpacing",
    "QuadraticSpacing",
    "ReversedSpacing",
    "SineSpacing",
    "SmoothstepSpacing",
    "SpacingCurve",
    "SpacingLike",
    "TableSpacing",
    "coerce_spacing",
]

type Mode = Literal["in", "out", "in_out"]

#: Anything accepted wherever a spacing curve is asked for. Users are never
#: required to subclass :class:`SpacingCurve`; a plain callable will do.
type SpacingLike = SpacingCurve | Callable[[float], float]


class SpacingCurve(ABC):
    """Base class for point-spacing curves.

    Subclasses must implement :meth:`ease`, mapping [0, 1] -> [0, 1]
    monotonically with the endpoints fixed.
    """

    def __call__(self, t: float) -> float:
        """Return ``ease(t)``, rejecting a ``t`` outside [0, 1]."""
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"t must be in [0, 1], got {t}")
        return self.ease(t)

    @abstractmethod
    def ease(self, t: float) -> float:
        """Map a fraction of the way along the curve to a fraction of its length."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class LinearSpacing(SpacingCurve):
    """Equal spacing between every point (the default, a "0 curve")."""

    @override
    def ease(self, t: float) -> float:
        return t


class _ModalCurve(SpacingCurve):
    """Shared machinery for curves that support ease in/out/in-out modes.

    ``mode`` is one of:

    * ``"in"``     -- slow start, fast end (spacing gradually increases)
    * ``"out"``    -- fast start, slow end (spacing gradually decreases)
    * ``"in_out"`` -- slow at both ends, fast in the middle
    """

    MODES: tuple[Mode, ...] = ("in", "out", "in_out")

    def __init__(self, mode: Mode = "in") -> None:
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}, got {mode!r}")
        self.mode = mode

    @abstractmethod
    def _ease_in(self, t: float) -> float: ...

    @override
    def ease(self, t: float) -> float:
        match self.mode:
            case "in":
                return self._ease_in(t)
            case "out":
                return 1.0 - self._ease_in(1.0 - t)
            case "in_out" if t < 0.5:
                return self._ease_in(2.0 * t) / 2.0
            case _:
                return 1.0 - self._ease_in(2.0 * (1.0 - t)) / 2.0

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}(mode={self.mode!r})"


class PowerSpacing(_ModalCurve):
    """``t ** exponent`` -- the general-purpose "by how much" control.

    * ``exponent == 1`` -- equal spacing (identical to :class:`LinearSpacing`)
    * ``exponent > 1``  -- with mode ``"in"``, spacing gradually increases;
      larger exponents exaggerate the effect
    * ``0 < exponent < 1`` -- the opposite bias

    Combine with ``mode="out"`` to flip which end is dense.
    """

    def __init__(self, exponent: float = 2.0, mode: Mode = "in") -> None:
        if exponent <= 0:
            raise ValueError(f"exponent must be > 0, got {exponent}")
        super().__init__(mode)
        self.exponent = exponent

    @override
    def _ease_in(self, t: float) -> float:
        return math.pow(t, self.exponent)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}(exponent={self.exponent}, mode={self.mode!r})"


class QuadraticSpacing(PowerSpacing):
    """Classic quadratic easing (``t ** 2``)."""

    def __init__(self, mode: Mode = "in") -> None:
        super().__init__(2.0, mode)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}(mode={self.mode!r})"


class CubicSpacing(PowerSpacing):
    """Classic cubic easing (``t ** 3``)."""

    def __init__(self, mode: Mode = "in") -> None:
        super().__init__(3.0, mode)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}(mode={self.mode!r})"


class SineSpacing(_ModalCurve):
    """Sinusoidal easing -- a gentle, natural-feeling bias."""

    @override
    def _ease_in(self, t: float) -> float:
        return 1.0 - math.cos(t * math.pi / 2.0)


class ExponentialSpacing(_ModalCurve):
    """Exponential easing with adjustable ``strength`` (dramatic bias).

    ``strength`` (default 10, the CSS/Penner standard) controls how extreme
    the clustering is; higher values pack points ever more tightly at the
    slow end. The curve is normalized so it still maps 0 -> 0 and 1 -> 1.
    """

    def __init__(self, mode: Mode = "in", strength: float = 10.0) -> None:
        if strength <= 0:
            raise ValueError(f"strength must be > 0, got {strength}")
        super().__init__(mode)
        self.strength = strength

    @override
    def _ease_in(self, t: float) -> float:
        k = self.strength
        floor = math.pow(2.0, -k)
        return (math.pow(2.0, k * (t - 1.0)) - floor) / (1.0 - floor)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}(mode={self.mode!r}, strength={self.strength})"


class CircularSpacing(_ModalCurve):
    """Circular (quarter-arc) easing -- abrupt at one end, flat at the other."""

    @override
    def _ease_in(self, t: float) -> float:
        return 1.0 - math.sqrt(1.0 - t * t)


class SmoothstepSpacing(SpacingCurve):
    """Hermite smoothstep ``3t^2 - 2t^3`` -- inherently ease-in-out.

    Spacing grows toward the middle of the path and shrinks again toward
    the end, with perfectly smooth acceleration.
    """

    @override
    def ease(self, t: float) -> float:
        return t * t * (3.0 - 2.0 * t)


class ReversedSpacing(SpacingCurve):
    """Mirror any curve: dense where the original was sparse, and vice versa.

    ``ReversedSpacing(f)(t) == 1 - f(1 - t)``, which is exactly the ``"out"``
    of a modal curve's ``"in"`` -- but this works on curves that have no mode,
    including plain callables and :class:`TableSpacing`.
    """

    def __init__(self, curve: SpacingLike) -> None:
        self.curve = coerce_spacing(curve)

    @override
    def ease(self, t: float) -> float:
        return 1.0 - self.curve(1.0 - t)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.curve!r})"


class CompositeSpacing(SpacingCurve):
    """Chain curves, feeding each one's output into the next.

    ``CompositeSpacing(a, b)(t) == b(a(t))`` -- written in application order,
    so it reads left to right. Composition of monotone [0, 1] -> [0, 1] maps
    is itself monotone with fixed endpoints, so the result is always a valid
    spacing curve.
    """

    def __init__(self, *curves: SpacingLike) -> None:
        if not curves:
            raise ValueError("CompositeSpacing needs at least one curve")
        self.curves = tuple(coerce_spacing(c) for c in curves)

    @override
    def ease(self, t: float) -> float:
        for curve in self.curves:
            t = curve(t)
        return t

    @override
    def __repr__(self) -> str:
        inner = ", ".join(repr(c) for c in self.curves)
        return f"{type(self).__name__}({inner})"


class TableSpacing(SpacingCurve):
    """A curve drawn by hand, from arbitrary ``(t, eased)`` control points.

    Interpolation between control points is linear. That is a deliberate
    choice over a smoother spline: linear interpolation of monotone data is
    exactly monotone, whereas cubic fits can overshoot and hand back a curve
    that walks backwards -- which shows up as points in the wrong order.

    Parameters
    ----------
    points : sequence of (float, float)
        Control points in [0, 1] x [0, 1]. ``(0, 0)`` and ``(1, 1)`` are
        supplied automatically when absent, so only the interesting middle
        needs listing. Both coordinates must be non-decreasing.

    Examples
    --------
    A curve that spends the first half of its length on the first quarter
    of the path::

        TableSpacing([(0.5, 0.25)])
    """

    def __init__(self, points: Sequence[tuple[float, float]]) -> None:
        table = sorted((float(t), float(v)) for t, v in points)
        for t, v in table:
            if not 0.0 <= t <= 1.0 or not 0.0 <= v <= 1.0:
                raise ValueError(f"control points must lie in [0, 1] x [0, 1], got ({t}, {v})")
        if not table or table[0][0] > 0.0:
            table.insert(0, (0.0, 0.0))
        if table[-1][0] < 1.0:
            table.append((1.0, 1.0))
        for (t0, v0), (t1, v1) in itertools.pairwise(table):
            if t1 < t0 or v1 < v0:
                raise ValueError(
                    f"control points must be non-decreasing in both axes, "
                    f"got ({t0}, {v0}) then ({t1}, {v1})"
                )
        self.table = tuple(table)

    @override
    def ease(self, t: float) -> float:
        table = self.table
        for (t0, v0), (t1, v1) in itertools.pairwise(table):
            if t <= t1:
                span = t1 - t0
                # A vertical step in the table is a legal instantaneous jump;
                # take its far side rather than dividing by zero. The curve is
                # continuous from the left, so a jump lands after its own t.
                return v1 if span == 0.0 else v0 + (v1 - v0) * (t - t0) / span
        return table[-1][1]

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self.table)!r})"


@final
class _CallableSpacing(SpacingCurve):
    """Adapter that lets any plain callable stand in for a curve."""

    def __init__(self, fn: Callable[[float], float]) -> None:
        self.fn = fn

    @override
    def ease(self, t: float) -> float:
        return self.fn(t)

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.fn!r})"


def coerce_spacing(spacing: SpacingLike | None) -> SpacingCurve:
    """Normalize anything spacing-shaped into a :class:`SpacingCurve`.

    ``None`` means :class:`LinearSpacing`. This is the single place the
    library decides what counts as a spacing curve, so every entry point
    accepts exactly the same things and fails the same way.

    Raises
    ------
    TypeError
        If ``spacing`` is neither a curve, a callable, nor ``None``.
    """
    if spacing is None:
        return LinearSpacing()
    if isinstance(spacing, SpacingCurve):
        return spacing
    if callable(spacing):
        return _CallableSpacing(spacing)
    raise TypeError(
        f"spacing must be a SpacingCurve or a callable mapping [0, 1] -> [0, 1], got {spacing!r}"
    )
