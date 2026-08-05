"""Turtle graphics driven by an L-system grammar.

An L-system is a start string plus rewrite rules applied a fixed number of
times; the resulting string is then read as turtle instructions. It is the
most economical description of the classic fractal curves there is -- Koch,
Hilbert, Gosper, dragon, Sierpinski and the rest each reduce to an axiom, one
or two rules and a turn angle.

The turtle alphabet, which follows the usual convention:

===========  ==================================================
Symbol       Meaning
===========  ==================================================
``F G A B``  move forward, drawing (see :attr:`LSystemMotif.draw`)
``f g``      move forward without drawing, breaking the stroke
``+``        turn left by :attr:`LSystemMotif.angle`
``-``        turn right by :attr:`LSystemMotif.angle`
``|``        turn around
``[``        push position and heading
``]``        pop position and heading, starting a new stroke
===========  ==================================================

Every other symbol is ignored while drawing, which is what lets grammars use
letters like ``X`` and ``Y`` purely to drive the rewriting.
"""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, override

from ..core.motif import Motif
from ..core.range import Range
from ..core.registry import spec
from ..core.types import Design, Path

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..core.types import Point

__all__ = ["LSystemMotif"]

# An expansion this large is a runaway depth, not a design: a million points
# is already far more than any plotter or screen can resolve.
_MAX_SYMBOLS = 2_000_000

# Closure tolerance, as a fraction of the step length. Turtle arithmetic
# accumulates rounding over thousands of moves, so a curve that returns to its
# start does so only approximately.
_CLOSURE_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class LSystemMotif(Motif, ABC):
    """Base for a motif described by a grammar and drawn with a turtle.

    Define :attr:`axiom`, :attr:`rules` and :attr:`angle` as class variables;
    everything else is a parameter with a sensible default. A concrete
    fractal is four lines::

        @register("koch", family="fractal")
        @dataclass(frozen=True, slots=True)
        class KochCurve(LSystemMotif):
            axiom = "F"
            rules: ClassVar[Mapping[str, str]] = {"F": "F+F--F+F"}
            angle = math.pi / 3

    The ``ClassVar`` annotation on :attr:`rules` is not decoration: without
    it, a mutable class attribute in a dataclass body is ambiguous to reader
    and linter alike, and annotating it as anything else would make it a
    constructor parameter with a mutable default, which dataclasses reject.

    Notes
    -----
    Both the string expansion and the point count grow exponentially with
    :attr:`depth`; the expansion is capped so that an accidental ``depth=20``
    raises instead of exhausting memory.
    """

    #: Starting string. Required -- there is no sensible default.
    axiom: ClassVar[str] = ""
    #: Symbol -> replacement, applied simultaneously each round.
    rules: ClassVar[Mapping[str, str]] = MappingProxyType({})
    #: Turn angle for ``+`` and ``-``, in radians.
    angle: ClassVar[float] = math.pi / 2
    #: Symbols that move the turtle forward while drawing.
    draw: ClassVar[frozenset[str]] = frozenset("FGAB")
    #: Symbols that move the turtle forward without drawing.
    move: ClassVar[frozenset[str]] = frozenset("fg")
    #: Whether a stroke that returns to its own start should be closed.
    closed: ClassVar[bool] = False

    #: Number of rewriting rounds.
    depth: int = field(default=4, metadata=Range(1, 7, step=1), kw_only=True)
    #: Length of one forward move.
    step: float = field(default=1.0, metadata=Range(0.1, 50.0), kw_only=True)
    #: Initial heading, in radians, counter-clockwise from the x-axis.
    start_angle: float = field(default=0.0, metadata=Range(0.0, math.tau), kw_only=True)

    def expand(self) -> str:
        """Return the axiom rewritten :attr:`depth` times.

        Raises
        ------
        ValueError
            If ``depth`` is negative, if no axiom was defined, or if the
            expansion outgrows what can usefully be drawn.
        """
        if self.depth < 0:
            raise ValueError(f"depth must be >= 0, got {self.depth}")
        if not self.axiom:
            raise ValueError(
                f"{type(self).__name__} must define a non-empty `axiom` class variable"
            )

        current = self.axiom
        for round_number in range(self.depth):
            current = "".join(self.rules.get(symbol, symbol) for symbol in current)
            if len(current) > _MAX_SYMBOLS:
                raise ValueError(
                    f"{type(self).__name__} expanded to more than {_MAX_SYMBOLS} symbols "
                    f"after {round_number + 1} of {self.depth} rounds; use a smaller depth"
                )
        return current

    @override
    def build(self) -> Design:
        if self.step <= 0:
            raise ValueError(f"step must be > 0, got {self.step}")

        paths = self._walk(self.expand())
        if not paths:
            raise ValueError(
                f"{type(self).__name__} drew nothing: no symbol of its expansion is in "
                f"`draw` ({''.join(sorted(self.draw))})"
            )
        return Design(paths, meta=spec(self))

    def _walk(self, symbols: str) -> tuple[Path, ...]:
        """Run the turtle over ``symbols``, returning one path per stroke."""
        x, y = 0.0, 0.0
        heading = self.start_angle
        stack: list[tuple[float, float, float]] = []
        stroke: list[Point] = [(x, y)]
        strokes: list[Path] = []

        def flush() -> None:
            # A single point is a position, not a stroke; emitting it would put
            # a stray dot wherever the turtle happened to lift the pen.
            if len(stroke) > 1:
                strokes.append(self._close(tuple(stroke)))

        for symbol in symbols:
            match symbol:
                case _ if symbol in self.draw:
                    x, y = x + self.step * math.cos(heading), y + self.step * math.sin(heading)
                    stroke.append((x, y))
                case _ if symbol in self.move:
                    x, y = x + self.step * math.cos(heading), y + self.step * math.sin(heading)
                    flush()
                    stroke = [(x, y)]
                case "+":
                    heading += self.angle
                case "-":
                    heading -= self.angle
                case "|":
                    heading += math.pi
                case "[":
                    stack.append((x, y, heading))
                case "]":
                    if not stack:
                        raise ValueError(
                            f"{type(self).__name__} popped an empty branch stack: its "
                            f"expansion has a ']' with no matching '['"
                        )
                    flush()
                    x, y, heading = stack.pop()
                    stroke = [(x, y)]
                case _:
                    # Grammar-only symbols (X, Y, ...) drive the rewriting and
                    # mean nothing to the turtle.
                    pass

        flush()
        return tuple(strokes)

    def _close(self, points: tuple[Point, ...]) -> Path:
        """Return ``points`` as a path, closing the seam if the class asked for it."""
        if not self.closed:
            return Path(points)
        # Turtle arithmetic never lands exactly back on the origin, so closure
        # is decided by proximity and the redundant final vertex is dropped.
        if len(points) > 2 and math.dist(points[0], points[-1]) <= self.step * _CLOSURE_TOLERANCE:
            return Path(points[:-1], closed=True)
        return Path(points, closed=True)
