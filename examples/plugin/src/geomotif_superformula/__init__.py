"""A third-party geomotif motif, complete.

The Gielis superformula, which is not in geomotif's own catalog and does not
need to be. Once this package is installed, ``superformula`` is listed by
``geomotif list --family curve``, described by ``geomotif show superformula``,
rendered by ``geomotif render superformula --m 7 --out s.svg``, serialized to a
spec file, and held to the same conformance contract every builtin meets --
without geomotif knowing this package exists.

The motif itself is the part worth copying. Pick the base that matches how your
shape is *defined*, write the one method it asks for, and everything else comes
with it. A superformula is a radius as a function of angle, so the base is
:class:`~geomotif.PolarMotif` and the method is ``radius(theta)``. That is the
whole of it: no sampling code, no export code, no CLI code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from geomotif import PolarMotif, register

__all__ = ["Superformula", "register_all"]


@register("superformula", family="curve", example={"m": 7.0, "resolution": 700})
@dataclass(frozen=True, slots=True)
class Superformula(PolarMotif):
    """Gielis's superformula: one equation for a great many natural outlines.

    ``m`` is how many corners the shape has, and the three ``n`` exponents
    decide whether those corners are points, lobes or bulges. ``m = 4`` with
    all three exponents large gives a rounded square; ``m = 0`` gives a
    circle, since the angular term stops varying.

    Parameters
    ----------
    m : float, optional
        Rotational symmetry -- the number of corners.
    n1, n2, n3 : float, optional
        Shape exponents, all positive. Below 1 the corners pinch to points;
        above 1 they swell outward.
    a, b : float, optional
        Scale of the two axes. Equal values give a shape with ``m``-fold
        symmetry; unequal ones stretch it.
    size : float, optional
        Radius at a corner, which for these exponents is the widest reach.

    Notes
    -----
    Every corner is a corner in the radius too, so a sample has to land on one
    to reach it. ``resolution`` counts segments rather than points, which
    makes the rule an easy one: any multiple of ``m`` puts a sample on all
    ``m`` corners at once. That is why this motif's registered example asks
    for 700 rather than leaving it to the automatic count -- at 512 segments
    the corners come out between 99.09 and 100, and only the one at
    ``theta_start`` is exact.

    Exponents below 1 go further and turn each corner into a genuine cusp,
    where the radius has infinite slope. Those never resolve: raise
    ``resolution`` and every tip lengthens together without any of them
    converging. That is the shape being honest about itself rather than a
    bug. Exponents of 1 or more are well behaved.
    """

    m: float = 6.0
    n1: float = 1.0
    n2: float = 1.0
    n3: float = 1.0
    a: float = 1.0
    b: float = 1.0
    size: float = field(default=100.0, kw_only=True)

    def __post_init__(self) -> None:
        for name in ("n1", "n2", "n3", "a", "b", "size"):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be > 0, got {value}")

    def radius(self, theta: float) -> float:
        """Return the superformula radius at ``theta``, in radians."""
        quarter = self.m * theta / 4.0
        total = (
            abs(math.cos(quarter) / self.a) ** self.n2 + abs(math.sin(quarter) / self.b) ** self.n3
        )
        # The two terms vanish together only for exponents that make it
        # possible; the shape has no radius there, and the origin is the
        # honest answer rather than a division by zero.
        if total == 0.0:
            return 0.0
        return self.size * total ** (-1.0 / self.n1)


def register_all() -> None:
    """Entry-point hook. Importing this module is what registers the motifs.

    geomotif imports whatever the entry point names and then calls it, so the
    ``@register`` decorator above has already run by the time this function is
    entered. The hook still earns its place: it is the name that forces the
    import, and it is where a plugin whose motifs are spread over several
    modules would import the rest of them.
    """
