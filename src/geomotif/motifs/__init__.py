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
`fractals`    Koch, Hilbert, Gosper, the dragons and the Sierpinski
              family as grammars; carpets, trees and the Apollonian
              gasket by recursion; the Barnsley fern by chaos game
`graphs`      Complete and circulant graphs, chord diagrams, and the
              times-table cardioid of :class:`~.graphs.ModularMultiplication`
`stringart`   Straight threads whose envelope is a curve: the strung
              corner, the strung polygon, and the general engine
`tilings`     Periodic tilings on a lattice, both Penrose tilings, the
              Ammann-Beenker quasicrystal and Truchet's tossed tiles
`sacred`      Circles on a hexagonal grid: the vesica, the seed, the
              flower, Metatron's cube, the Sri Yantra
`guilloche`   The woven line work of banknotes and watch dials
============  ==========================================================

Composed figures -- mandalas, kaleidoscopes, snowflakes -- are motifs made
out of these, and live in :mod:`geomotif.compose`.
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
from .fractals import (
    ApollonianGasket,
    BarnsleyFern,
    CantorSet,
    DragonCurve,
    GosperCurve,
    HilbertCurve,
    HTree,
    IFSAttractor,
    IFSMap,
    KochAntisnowflake,
    KochCurve,
    KochSnowflake,
    LevyCCurve,
    MinkowskiIsland,
    MinkowskiSausage,
    MooreCurve,
    PeanoCurve,
    PythagorasTree,
    SierpinskiArrowhead,
    SierpinskiCarpet,
    SierpinskiTriangle,
    Terdragon,
    TwinDragon,
    VicsekFractal,
)
from .graphs import (
    BipartiteGraph,
    ChordDiagram,
    CompleteGraph,
    CyclicGraph,
    ModularAddition,
    ModularMultiplication,
    PrimeChords,
)
from .guilloche import GuillocheBand, GuillochePattern, GuillocheRosette
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
from .sacred import (
    FlowerOfLife,
    FruitOfLife,
    GoldenRectangle,
    MetatronsCube,
    SeedOfLife,
    SriYantra,
    VesicaPiscis,
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
from .stringart import (
    StringArtCircle,
    StringArtCorner,
    StringArtEnvelope,
    StringArtPolygon,
)
from .tilings import (
    AmmannBeenker,
    CairoPentagonal,
    HerringboneTiling,
    HexagonalTiling,
    PenroseP2,
    PenroseP3,
    PenroseTiling,
    RhombilleTiling,
    RobinsonTriangle,
    SnubSquare,
    SquareTiling,
    TriangularTiling,
    TruchetTiling,
    TruncatedSquare,
)

__all__ = [
    "GOLDEN_ANGLE",
    "PHI",
    "AmmannBeenker",
    "ApollonianGasket",
    "Arc",
    "ArchimedeanSpiral",
    "Astroid",
    "BarnsleyFern",
    "BipartiteGraph",
    "BowCurve",
    "Butterfly",
    "CairoPentagonal",
    "CantorSet",
    "Cardioid",
    "CassiniOval",
    "ChordDiagram",
    "Circle",
    "CircleInvolute",
    "Cochleoid",
    "CompleteGraph",
    "Cornoid",
    "CyclicGraph",
    "Cycloid",
    "Deltoid",
    "DragonCurve",
    "Egg",
    "Ellipse",
    "Epicycles",
    "Epicycloid",
    "Epitrochoid",
    "EulerSpiral",
    "FermatSpiral",
    "FibonacciSpiral",
    "FishCurve",
    "FlowerOfLife",
    "Folium",
    "FruitOfLife",
    "GoldenRectangle",
    "GoldenSpiral",
    "GosperCurve",
    "GuillocheBand",
    "GuillochePattern",
    "GuillocheRosette",
    "HTree",
    "Harmonic",
    "Harmonograph",
    "Heart",
    "HeartForm",
    "HerringboneTiling",
    "HexagonalTiling",
    "HilbertCurve",
    "HyperbolicSpiral",
    "Hypocycloid",
    "Hypotrochoid",
    "IFSAttractor",
    "IFSMap",
    "KochAntisnowflake",
    "KochCurve",
    "KochSnowflake",
    "Lemniscate",
    "LemniscateOfGerono",
    "LevyCCurve",
    "Limacon",
    "Line",
    "Lissajous",
    "Lituus",
    "LogarithmicSpiral",
    "MaurerRose",
    "MetatronsCube",
    "MinkowskiIsland",
    "MinkowskiSausage",
    "ModularAddition",
    "ModularMultiplication",
    "MooreCurve",
    "Nephroid",
    "PeanoCurve",
    "Pendulum",
    "PenroseP2",
    "PenroseP3",
    "PenroseTiling",
    "Phyllotaxis",
    "PointGrid",
    "PoissonDiscPoints",
    "PolarExpression",
    "PrimeChords",
    "PythagorasTree",
    "Rectangle",
    "RegularPolygon",
    "ReuleauxPolygon",
    "RhombilleTiling",
    "RobinsonTriangle",
    "Rose",
    "RoundedRectangle",
    "Sector",
    "SeedOfLife",
    "SierpinskiArrowhead",
    "SierpinskiCarpet",
    "SierpinskiTriangle",
    "SnubSquare",
    "SpiralBase",
    "SpiralBetween",
    "Spirograph",
    "SquareTiling",
    "Squircle",
    "SriYantra",
    "Star",
    "StarPolygon",
    "StringArtCircle",
    "StringArtCorner",
    "StringArtEnvelope",
    "StringArtPolygon",
    "Superellipse",
    "Terdragon",
    "TheodorusSpiral",
    "TriangularTiling",
    "Trochoid",
    "TruchetTiling",
    "TruncatedSquare",
    "TwinDragon",
    "VesicaPiscis",
    "VicsekFractal",
    "VogelSpiral",
    "Witch",
]
