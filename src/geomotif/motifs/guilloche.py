"""Guilloché: the engine-turned line work on banknotes and watch dials.

The whole family is one trick. Draw a wavy curve; draw it again with the wave
shifted a little; repeat twenty times. Nowhere do two lines cross at a shallow
angle, so the eye reads the stack as a woven surface rather than as twenty
separate strokes -- and because the pattern is the *sum* of two frequencies,
copying it by hand is hopeless, which is exactly why engravers used it on
money.

Three shapes cover what a rose engine could do. :class:`GuillocheRosette` runs
the wave around a circle. :class:`GuillocheBand` runs it along a straight
spine, for a border or a ribbon. :class:`GuillochePattern` puts one inside the
other, which is the banknote layout: a rosette in the middle, a band around
the edge, rules between them.

Two frequencies, not one, is the part worth keeping. A single sine shifted in
phase just slides sideways and the stack looks like a comb. Adding a second
wave that runs the *other* way makes each shifted copy a genuinely different
curve, and the interference between them is the weave.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..bases import Curve, MultiCurveMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Design, Path
from ._common import arc_points

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ..core.types import Point

__all__ = ["GuillocheBand", "GuillochePattern", "GuillocheRosette"]

#: Ceiling on the number of strokes one motif may stack, so a mistyped layer
#: count raises rather than spending a minute drawing an inky disc.
_MAX_LINES = 400


def _check_lines(owner: str, lines: int, *, name: str = "layers") -> None:
    if lines < 1:
        raise ValueError(f"{owner} {name} must be >= 1, got {lines}")
    if lines > _MAX_LINES:
        raise ValueError(f"{owner} {name} must be <= {_MAX_LINES}, got {lines}")


def _weave(u: float, waves: float, counter: float, phase: float) -> float:
    """Return the two-frequency wave at ``u``, in ``[-1, 1]``.

    One wave runs forward and one back, so shifting the phase changes the
    shape of the curve rather than merely sliding it along.
    """
    return (math.sin(math.tau * waves * u + phase) + math.sin(math.tau * counter * u - phase)) / 2.0


@register(
    "guilloche.rosette",
    family="guilloche",
    example={"layers": 6, "petals": 7},
)
@dataclass(frozen=True, slots=True)
class GuillocheRosette(MultiCurveMotif):
    """A stack of rosettes, each turned a little further than the last.

    The wave runs around a circle instead of along a line, so every stroke
    closes. Successive layers step outward by :attr:`spread` and forward by
    :attr:`twist`, and where the two rates disagree the lines braid.

    Parameters
    ----------
    radius : float, optional
        Radius of the innermost layer's spine.
    amplitude : float, optional
        How far the wave carries a stroke off its spine.
    petals : float, optional
        Waves per revolution. Whole numbers close cleanly.
    counter : float, optional
        Waves per revolution of the backward-running second frequency.
    layers : int, optional
        How many strokes to stack.
    spread : float, optional
        Radial step between layers.
    twist : float, optional
        Phase step between layers, in radians. This is what turns a stack of
        identical rings into a weave.
    center : (float, float), optional
        Middle of the rosette.
    """

    radius: float = 96.0
    amplitude: float = 30.0
    petals: float = 13.0
    counter: float = 5.0
    layers: int = 14
    spread: float = 2.6
    twist: float = 0.42
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_lines(owner, self.layers)
        if self.radius <= 0.0:
            raise ValueError(f"{owner} radius must be > 0, got {self.radius}")
        if self.amplitude == 0.0:
            raise ValueError(f"{owner} amplitude must be non-zero; a flat wave is a circle")

    def _layer(self, index: int) -> Curve:
        spine = self.radius + index * self.spread
        phase = index * self.twist
        cx, cy = self.center

        def position(u: float) -> Point:
            theta = math.tau * u
            r = spine + self.amplitude * _weave(u, self.petals, self.counter, phase)
            return (cx + r * math.cos(theta), cy + r * math.sin(theta))

        return Curve(position, closed=True, turns=max(abs(self.petals), abs(self.counter)))

    @override
    def curves(self) -> Iterable[Curve]:
        return (self._layer(index) for index in range(self.layers))


@register("guilloche.band", family="guilloche", example={"lines": 8})
@dataclass(frozen=True, slots=True)
class GuillocheBand(MultiCurveMotif):
    """A woven ribbon along a straight spine: the border of a banknote.

    Each stroke is the same two-frequency wave at a different phase, so the
    stack fills a band of constant height with a pattern that never quite
    repeats along its length.

    Parameters
    ----------
    length : float, optional
        Length of the spine.
    height : float, optional
        Full height of the band.
    waves : float, optional
        Cycles of the forward wave along the whole length.
    counter : float, optional
        Cycles of the backward wave.
    lines : int, optional
        How many strokes to stack. Their phases divide one full cycle evenly.
    center : (float, float), optional
        Middle of the band.
    """

    length: float = 320.0
    height: float = 76.0
    waves: float = 5.0
    counter: float = 8.0
    lines: int = 18
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_lines(owner, self.lines, name="lines")
        if self.length <= 0.0:
            raise ValueError(f"{owner} length must be > 0, got {self.length}")
        if self.height <= 0.0:
            raise ValueError(f"{owner} height must be > 0, got {self.height}")

    def _line(self, index: int) -> Curve:
        phase = math.tau * index / self.lines
        cx, cy = self.center
        left = cx - self.length / 2.0

        def position(u: float) -> Point:
            return (
                left + self.length * u,
                cy + self.height / 2.0 * _weave(u, self.waves, self.counter, phase),
            )

        return Curve(position, turns=max(abs(self.waves), abs(self.counter)))

    @override
    def curves(self) -> Iterable[Curve]:
        return (self._line(index) for index in range(self.lines))


@register(
    "guilloche.pattern",
    family="guilloche",
    example={"layers": 5, "border_lines": 8, "border_waves": 18.0},
)
@dataclass(frozen=True, slots=True)
class GuillochePattern(Motif):
    """A rosette inside a woven border, with rules between: the banknote layout.

    A composition rather than a curve of its own: two
    :class:`GuillocheRosette` instances, one broad and slow for the middle and
    one narrow and fast for the border, with a plain circle ruled either side
    of the border to close it off. A band bent into a ring *is* a rosette, so
    there is no third shape to write.

    Parameters
    ----------
    radius : float, optional
        Outer radius, to the middle of the border.
    layers : int, optional
        Strokes in the central rosette.
    petals : float, optional
        Waves per revolution in the central rosette.
    border_lines : int, optional
        Strokes in the border.
    border_height : float, optional
        Full width of the border band.
    border_waves : float, optional
        Waves around the border.
    rules : bool, optional
        Draw the two plain circles that fence the border in.
    center : (float, float), optional
        Middle of the figure.
    """

    radius: float = 150.0
    layers: int = 12
    petals: float = 11.0
    border_lines: int = 16
    border_height: float = 30.0
    border_waves: float = 36.0
    rules: bool = field(default=True, kw_only=True)
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_lines(owner, self.layers)
        _check_lines(owner, self.border_lines, name="border_lines")
        if self.radius <= 0.0:
            raise ValueError(f"{owner} radius must be > 0, got {self.radius}")
        if self.border_height <= 0.0:
            raise ValueError(f"{owner} border_height must be > 0, got {self.border_height}")
        if self.border_height >= self.radius:
            raise ValueError(
                f"{owner} border_height {self.border_height} must be smaller than "
                f"radius {self.radius}, or the border swallows the rosette"
            )

    def rosette(self) -> GuillocheRosette:
        """Return the central rosette, sized to sit inside the border."""
        inner = self.radius - self.border_height
        spread = inner / (2.0 * self.layers)
        return GuillocheRosette(
            radius=inner / 2.0,
            amplitude=inner / 6.0,
            petals=self.petals,
            counter=self.petals / 2.0,
            layers=self.layers,
            spread=spread,
            twist=math.tau / (2.0 * self.layers),
            center=self.center,
        )

    def border(self) -> GuillocheRosette:
        """Return the border, which is a rosette with a tight, fast wave."""
        return GuillocheRosette(
            radius=self.radius - self.border_height / 2.0,
            amplitude=self.border_height / 2.0,
            petals=self.border_waves,
            counter=self.border_waves / 3.0,
            layers=self.border_lines,
            spread=0.0,
            twist=math.tau / self.border_lines,
            center=self.center,
        )

    @override
    def build(self) -> Design:
        design = self.rosette().build() + self.border().build()
        paths = design.paths
        if self.rules:
            paths = (
                *paths,
                *(
                    Path(arc_points(self.center, radius, 0.0, math.tau)[:-1], closed=True)
                    for radius in (self.radius - self.border_height, self.radius)
                ),
            )
        return Design(paths, meta=spec(self))
