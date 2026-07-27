"""Spacing curves that control the distribution of points along a spiral.

A spacing curve is a monotonic mapping of normalized progress ``t`` in
[0, 1] to eased progress in [0, 1], with ``f(0) == 0`` and ``f(1) == 1``.
The eased value selects each point's position as a fraction of the spiral's
arc length, so the shape of the curve directly controls the gap between
consecutive points:

* ``f(t) = t``            -> equal spacing
* slow start / fast end   -> spacing gradually increases
* fast start / slow end   -> spacing gradually decreases
"""

import math
from abc import ABC, abstractmethod
from typing import Literal, override

__all__ = [
    "CircularSpacing",
    "CubicSpacing",
    "ExponentialSpacing",
    "LinearSpacing",
    "Mode",
    "PowerSpacing",
    "QuadraticSpacing",
    "SineSpacing",
    "SmoothstepSpacing",
    "SpacingCurve",
]

type Mode = Literal["in", "out", "in_out"]


class SpacingCurve(ABC):
    """Base class for point-spacing curves.

    Subclasses must implement :meth:`ease`, mapping [0, 1] -> [0, 1]
    monotonically with the endpoints fixed.
    """

    def __call__(self, t: float) -> float:
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"t must be in [0, 1], got {t}")
        return self.ease(t)

    @abstractmethod
    def ease(self, t: float) -> float: ...

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

    Spacing grows toward the middle of the spiral and shrinks again toward
    the end, with perfectly smooth acceleration.
    """

    @override
    def ease(self, t: float) -> float:
        return t * t * (3.0 - 2.0 * t)
