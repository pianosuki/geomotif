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
`curves`      The named curves: hearts, cardioids, lemniscates, Cassini
              ovals, limacons, astroids, cycloids and the rest
`roulettes`   What one circle draws rolling around another --
              trochoids, cycloids, the Spirograph, and the stacked
              rotating arms of :class:`~.roulettes.Epicycles`
`polar`       Roses and Maurer roses, Lissajous figures, harmonics,
              the harmonograph and the sunflower's phyllotaxis
============  ==========================================================
"""

from .curves import (
    Astroid,
    BowCurve,
    Butterfly,
    Cardioid,
    CassiniOval,
    Cochleoid,
    Cornoid,
    Cycloid,
    Deltoid,
    FishCurve,
    Folium,
    Heart,
    HeartForm,
    Lemniscate,
    LemniscateOfGerono,
    Limacon,
    Nephroid,
    Trochoid,
    Witch,
)
from .polar import (
    GOLDEN_ANGLE,
    Harmonic,
    Harmonograph,
    Lissajous,
    MaurerRose,
    Pendulum,
    Phyllotaxis,
    PolarExpression,
    Rose,
    VogelSpiral,
)
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
from .roulettes import (
    Epicycles,
    Epicycloid,
    Epitrochoid,
    Hypocycloid,
    Hypotrochoid,
    Spirograph,
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
    "GOLDEN_ANGLE",
    "PHI",
    "Arc",
    "ArchimedeanSpiral",
    "Astroid",
    "BowCurve",
    "Butterfly",
    "Cardioid",
    "CassiniOval",
    "Circle",
    "CircleInvolute",
    "Cochleoid",
    "Cornoid",
    "Cycloid",
    "Deltoid",
    "Egg",
    "Ellipse",
    "Epicycles",
    "Epicycloid",
    "Epitrochoid",
    "EulerSpiral",
    "FermatSpiral",
    "FibonacciSpiral",
    "FishCurve",
    "Folium",
    "GoldenSpiral",
    "Harmonic",
    "Harmonograph",
    "Heart",
    "HeartForm",
    "HyperbolicSpiral",
    "Hypocycloid",
    "Hypotrochoid",
    "Lemniscate",
    "LemniscateOfGerono",
    "Limacon",
    "Line",
    "Lissajous",
    "Lituus",
    "LogarithmicSpiral",
    "MaurerRose",
    "Nephroid",
    "Pendulum",
    "Phyllotaxis",
    "PointGrid",
    "PoissonDiscPoints",
    "PolarExpression",
    "Rectangle",
    "RegularPolygon",
    "ReuleauxPolygon",
    "Rose",
    "RoundedRectangle",
    "Sector",
    "SpiralBase",
    "SpiralBetween",
    "Spirograph",
    "Squircle",
    "Star",
    "StarPolygon",
    "Superellipse",
    "TheodorusSpiral",
    "Trochoid",
    "VogelSpiral",
    "Witch",
]
