"""The motif catalogue.

Motifs are imported from their family modules rather than from the top-level
package: there will eventually be well over a hundred of them, and a flat
namespace that large is unusable. Import what you need::

    from geomotif.motifs import Circle, GoldenSpiral
    from geomotif.motifs.spirals import GoldenSpiral

or construct one by name through :mod:`geomotif.core.registry`.

============  ==========================================================
Module        Contents
============  ==========================================================
`spirals`     Archimedean, logarithmic, golden, Fibonacci, Fermat,
              hyperbolic, lituus, Theodorus, Euler, involute, and the
              endpoint-constrained :class:`~.spirals.SpiralBetween`
`primitives`  Circles, arcs, sectors, rectangles, regular and star
              polygons, superellipses, Reuleaux curves, grids and
              Poisson-disc point fields
============  ==========================================================
"""

from .primitives import (
    Arc,
    Circle,
    Egg,
    Ellipse,
    Line,
    PointGrid,
    PoissonDiscPoints,
    Rectangle,
    RegularPolygon,
    ReuleauxPolygon,
    RoundedRectangle,
    Sector,
    Squircle,
    Star,
    StarPolygon,
    Superellipse,
)
from .spirals import (
    PHI,
    ArchimedeanSpiral,
    CircleInvolute,
    EulerSpiral,
    FermatSpiral,
    FibonacciSpiral,
    GoldenSpiral,
    HyperbolicSpiral,
    Lituus,
    LogarithmicSpiral,
    SpiralBase,
    SpiralBetween,
    TheodorusSpiral,
)

__all__ = [
    "PHI",
    "Arc",
    "ArchimedeanSpiral",
    "Circle",
    "CircleInvolute",
    "Egg",
    "Ellipse",
    "EulerSpiral",
    "FermatSpiral",
    "FibonacciSpiral",
    "GoldenSpiral",
    "HyperbolicSpiral",
    "Line",
    "Lituus",
    "LogarithmicSpiral",
    "PointGrid",
    "PoissonDiscPoints",
    "Rectangle",
    "RegularPolygon",
    "ReuleauxPolygon",
    "RoundedRectangle",
    "Sector",
    "SpiralBase",
    "SpiralBetween",
    "Squircle",
    "Star",
    "StarPolygon",
    "Superellipse",
    "TheodorusSpiral",
]
