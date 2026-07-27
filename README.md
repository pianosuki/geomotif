# geomotif

[![PyPI](https://img.shields.io/pypi/v/geomotif)](https://pypi.org/project/geomotif/)
[![Python](https://img.shields.io/pypi/pyversions/geomotif)](https://pypi.org/project/geomotif/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A library for generating and plotting geometric designs, and for controlling
exactly where the points along them land.

A **motif** is a parameterized recipe for geometry; applying a **transform**
gives a **design**, which is what you plot or export. Write a motif once and
you get arc-length resampling, every spacing curve, the transform layer and
export for free.

Positioning is **true arc-length** by default: equal spacing means the same
real x,y distance between every consecutive pair of points, no matter how
tightly the curve winds. Built for designs where the physical distance
between points is what matters — generative art, plotter art, game object
placement, particle layouts, UI motion paths.

Zero dependencies for the core; matplotlib is an optional extra for
visualization. Requires Python 3.12+.

> **Status:** the engine, the data model and the motif bases are complete, and
> the catalogue is filling in — 142 motifs today: the spirals, the primitives,
> the named curves, the roulettes, the polar/harmonic family, the fractals,
> the graph and number art, string art, the tilings, sacred geometry,
> guilloché, the mandala composers, Islamic strapwork, Celtic knotwork, the
> polyhedra and the optical illusions. Voronoi and Delaunay are next, behind a
> `[scipy]` extra. Everything below already works for all of them, and for
> yours.

## Install

```bash
pip install geomotif           # core (no dependencies)
pip install 'geomotif[plot]'   # with matplotlib plotting helpers
```

## Quickstart

```python
from geomotif import PowerSpacing
from geomotif.motifs import SpiralBetween

spiral = SpiralBetween(
    start=(200, 0),  # required — first point (always included)
    end=(20, 0),  # required — last point (always included)
    center=(0, 0),  # point the spiral winds around (default shown)
    clockwise=True,  # rotation direction (default clockwise)
    turns=3,  # extra full revolutions (default 0)
)

design = spiral.generate(100, spacing=PowerSpacing(2.5))

for x, y in design:
    ...
```

`build()` gives the motif at its native resolution; `generate()` gives you
the points you actually plot. Everything after the count is keyword-only:

```python
spiral.generate(100)  # 100 points, equally spaced
spiral.generate(100, spacing=PowerSpacing(2.5))  # eased distribution
spiral.generate(step=5.0)  # a point every 5 units of real distance
spiral.generate(100, by="parameter")  # parametric instead of arc-length
```

`step=` is the mode you want for plotter output and dot placement: the gap is
fixed and the count falls out of the geometry.

## What's in the box

```python
from geomotif.motifs import Icosahedron, PenroseP3, Triquetra, VesicaPiscis
from geomotif.compose import Mandala, Ring
```

**Spirals** (`geomotif.motifs.spirals`) — `ArchimedeanSpiral` (evenly spaced
windings), `LogarithmicSpiral` (constant growth *ratio*), `GoldenSpiral`,
`FibonacciSpiral` (the quarter-arc approximation everyone actually draws —
both are here because they are not the same curve), `FermatSpiral`,
`HyperbolicSpiral`, `Lituus`, `TheodorusSpiral`, `EulerSpiral` (the clothoid,
via stdlib Fresnel integrals), `CircleInvolute` and `SpiralBetween`.

**Primitives** (`geomotif.motifs.primitives`) — `Circle`, `Ellipse`, `Arc`,
`Sector`, `Line`, `Rectangle`, `RoundedRectangle`, `RegularPolygon`,
`StarPolygon` (the `{n/k}` family — `{6/2}` correctly comes back as two
triangles), `Star`, `Superellipse`, `Squircle`, `ReuleauxPolygon` (constant
width), `Egg`, `PointGrid` and `PoissonDiscPoints`.

**Named curves** (`geomotif.motifs.curves`) — `Heart` (both the valentine and
the cardioid form), `Cardioid`, `Lemniscate`, `LemniscateOfGerono`,
`CassiniOval` (which comes back as two strokes when it really is two lobes),
`Limacon`, `Butterfly`, `FishCurve`, `BowCurve`, `Astroid`, `Deltoid`,
`Nephroid`, `Folium`, `Cochleoid`, `Cycloid`, `Trochoid`, `Witch` and
`Cornoid`. Anything with one free scale takes `size`, which is the largest
extent of its bounding box — so a heart and a butterfly at the same `size`
come out the same size.

**Roulettes** (`geomotif.motifs.roulettes`) — `Hypotrochoid`, `Epitrochoid`,
`Hypocycloid`, `Epicycloid`, `Spirograph` (in the toy's own terms: ring teeth,
wheel teeth and which hole the pen goes in) and `Epicycles`, which stacks any
number of rotating arms and plots the tip. Two arms is a trochoid, a few is a
planetary orbit, several dozen is a Fourier series.

**Polar and harmonic** (`geomotif.motifs.polar`) — `Rose` (with the petal
count right: `n` petals or `2n`, depending on a parity rule most
implementations get wrong), `MaurerRose`, `Lissajous`, `Harmonic`,
`Harmonograph`, `Phyllotaxis`/`VogelSpiral` (the sunflower seed head) and
`PolarExpression` for a one-off radius function.

**Fractals** (`geomotif.motifs.fractals`) — sixteen of them are a grammar and
nothing else: `KochCurve`, `KochSnowflake`, `KochAntisnowflake`,
`MinkowskiSausage`, `MinkowskiIsland`, `SierpinskiTriangle`,
`SierpinskiArrowhead`, `DragonCurve`, `TwinDragon`, `Terdragon`, `LevyCCurve`,
`HilbertCurve`, `MooreCurve`, `PeanoCurve`, `GosperCurve` and
`VicsekFractal`. The ones that place smaller copies of themselves rather than
walk a path are built directly: `SierpinskiCarpet`, `CantorSet`,
`PythagorasTree`, `HTree` and `ApollonianGasket` (Descartes' circle theorem,
so the curvatures come out integral). And two arrive by chaos game as loose
points: `IFSAttractor` and `BarnsleyFern`.

**Graph and number art** (`geomotif.motifs.graphs`) — `CompleteGraph`,
`CyclicGraph` (the circulant), `BipartiteGraph`, `ChordDiagram` for
connections that come from data, `ModularMultiplication` (the times-table
cardioid — join `i` to `2i` around a circle and a cardioid appears),
`ModularAddition` and `PrimeChords`.

**String art** (`geomotif.motifs.stringart`) — straight threads whose
*envelope* is a curve: `StringArtCorner` (the parabola everybody has made),
`StringArtPolygon`, `StringArtCircle` and `StringArtEnvelope`, the general
"point `i` on this curve to point `rule(i)` on that one" engine the rest are
special cases of.

**Tilings** (`geomotif.motifs.tilings`) — periodic ones stamped on a lattice:
`SquareTiling`, `TriangularTiling`, `HexagonalTiling`, `RhombilleTiling` (the
tumbling blocks), `CairoPentagonal`, `TruncatedSquare`, `SnubSquare` and
`HerringboneTiling` (at any brick proportion, not only two-to-one). Aperiodic
ones that never repeat: `PenroseP3` (the rhombs) and `PenroseP2` (the kite and
dart), which are the same two Robinson triangles glued along the base and
along a leg respectively, plus `AmmannBeenker`, the eightfold quasicrystal,
built by laying four families of parallel lines across each other. And
`TruchetTiling`, which tosses a coin per cell.

**Sacred geometry** (`geomotif.motifs.sacred`) — one construction, five
figures: `VesicaPiscis` → `SeedOfLife` → `FlowerOfLife` → `FruitOfLife` →
`MetatronsCube`. Plus `SriYantra` and `GoldenRectangle`, whose nested squares
are the frame the Fibonacci spiral is drawn in.

**Guilloché** (`geomotif.motifs.guilloche`) — the engine-turned line work of
banknotes and watch dials: `GuillocheRosette`, `GuillocheBand` and
`GuillochePattern`. Two frequencies running opposite ways, so shifting the
phase changes each stroke's shape rather than sliding it sideways.

**Islamic strapwork** (`geomotif.motifs.girih`) — `GirihTile` draws any of the
five tiles the patterns are built from, all of them the same side long and
every angle a multiple of 36°. `TenfoldGirih` lays them out; `InterlockingDecagons`
applies Hankin's rule to the result and the tiles vanish, leaving ten-pointed
stars. Plus `Rosette` (the shamsa: a star, a blunter star inside it, and so
on), `RosetteTiling` and `HexStarLattice`.

**Celtic knots** (`geomotif.motifs.knots`) — `Triquetra`, `EndlessKnot`,
`CircularCelticKnot`, `SquareCelticKnot` and `CelticGrid`, the plait every
knotwork panel is built on. Over-and-under is worked out rather than declared:
the crossings are found, two-coloured so that each strand alternates, and the
under-strand is drawn with a gap in it — which is what a pen plotter can draw.

**Polyhedra** (`geomotif.motifs.solids`) — the five Platonic solids and the
truncated icosahedron, as wireframes, through an orthographic, isometric or
perspective `Projection`. Each is a table of corners and one rule: join every
pair as close together as any pair gets. `Polyhedron` takes your own corners
and edges.

**Optical illusions** (`geomotif.motifs.illusions`) — `PenroseTriangle`,
`PenroseStairs`, `ImpossibleCube`, `NeckerCube`, `CafeWall` and
`MoirePattern`. The two Penrose figures are built in space and then flattened:
their walks genuinely fail to close, by exactly the amount an isometric view
cannot show.

**Composers** (`geomotif.compose`) — motifs made of other motifs: `Mandala`
(rings of a repeated unit), `Kaleidoscope` (one unit under a `Cn` or `Dn`
symmetry group), `Snowflake` (six arms, mirrored, grown from a seed),
`SpokePattern` and `LayeredRings`. Their unit is any object with a `build()`
method, so a composed figure can itself be the unit of another composition.

Anything registered is also reachable by name, with its parameters
introspectable:

```python
from geomotif.core import registry

registry.families()  # ('curve', 'fractal', 'girih', 'graph', 'guilloche', ...)
registry.names(family="spiral")  # ('spiral.archimedean', 'spiral.between', ...)
registry.create("polygon.star", points=7, step=3)
registry.describe("egg").params  # name, type, default, help for each
```

## Write your own motif

Usually it is the maths and nothing else. Pick the base that matches how your
design is *defined* and write the one method it asks for:

```python
import math
from dataclasses import dataclass

from geomotif import PolarMotif, register


@register("my-flower", family="polar")
@dataclass(frozen=True, slots=True)
class MyFlower(PolarMotif):
    """A seven-lobed flower with a ripple on it."""

    k: float = 7.0

    def radius(self, theta: float) -> float:
        return math.sin(self.k * theta) + 0.4 * math.cos(17 * theta)
```

That class now has arc-length resampling, every spacing curve, the transform
layer, export, plotting and lookup by name — `MyFlower(k=5).generate(400)`
just works, and so does `registry.create("my-flower", k=5)`.

| Base | You implement |
|---|---|
| `ParametricMotif` | `position(u) -> Point` |
| `PolarMotif` | `radius(theta) -> float` |
| `MultiCurveMotif` | `curves() -> Iterable[Curve]` |
| `PolygonMotif` | `outlines() -> Iterable[Sequence[Point]]` |
| `LSystemMotif` | an axiom, rewrite rules and a turn angle |
| `SegmentMotif` | `nodes()` and `edges()` |
| `LatticeTiling` | `cell()` and `basis()` |
| `SubstitutionTiling` | `seed()`, `subdivide()` and `outline()` |

The one distinction worth getting right is `ParametricMotif` vs
`PolygonMotif`: a curve is *measured* at evenly spaced parameters, a polygon
is *listed*. Measuring a pentagon at 512 samples rounds all five of its
corners off, so shapes defined by their corners list them instead.

If none of them fits, subclass `Motif` and write `build()` by hand — one
method, returning a `Design`:

```python
from geomotif import Design, Motif, Path, register


@register("zigzag", family="primitive")
@dataclass(frozen=True, slots=True)
class Zigzag(Motif):
    """A zigzag of `teeth` triangles."""

    teeth: int = 5
    height: float = 10.0

    def build(self) -> Design:
        points = tuple((float(i), self.height if i % 2 else 0.0) for i in range(self.teeth * 2 + 1))
        return Design((Path(points),))
```

You are not required to inherit at all: anything with a `build() -> Design`
method satisfies the `SupportsBuild` protocol and is accepted everywhere a
motif is.

## Designs, paths and points

A `Design` holds stroked `Path` polylines plus loose `points` that carry no
stroke (dot art, scatter fields). It iterates as a flat stream of points, so
it drops straight into anything expecting coordinates:

```python
len(design)  # total point count
design.bounds  # Bounds(min_x, min_y, max_x, max_y)
design + other  # overlay
design.fit(800, 600, padding=20)  # scale and center onto a canvas
design.flipped_y()  # y-down (screen/SVG) coordinates
```

Everything is immutable — operations return a new design.

## Transforms and composition

```python
from geomotif import Affine, radial_repeat, tile, jitter

rosette = radial_repeat(petal, 12)  # the mandala workhorse
lattice = tile(cell, 8, 8, dx=20, dy=20, stagger=0.5)
turned = design.transformed(Affine.rotate(math.pi / 6))
loose = jitter(design, 0.5, seed=7)  # reproducible irregularity
```

`Affine` composes with `@` — `(m @ n)(p) == m(n(p))`, so the right-hand
transform applies first.

## Exporting points

Send the coordinates to any other tool — editors, plotters, spreadsheets,
game map formats — with `save_points`:

```python
from geomotif import save_points

save_points(design, "points.csv")  # x,y header + one row per point
save_points(design, "points.txt", precision=0)  # tab-separated whole integers
save_points(design, "points.json", precision=2)  # JSON array of [x, y] pairs
```

The format is inferred from the file suffix (`.csv`, `.txt`/`.tsv`,
`.json`) or forced with `fmt=`. `precision` rounds coordinates;
`precision=0` writes whole integers.

## Plotting

To see the points on a graph (requires the `plot` extra):

```python
import matplotlib.pyplot as plt
from geomotif.plotting import plot_spiral

plot_spiral(list(design), center=(0, 0), title="my spiral")
plt.show()
```

Or run the built-in showcase:

```bash
geomotif-demo             # interactive window (or python -m geomotif)
geomotif-demo demo.png    # save to a file instead
```

## Spacing curves

All curves subclass `SpacingCurve` — implement `ease(t)` mapping
[0, 1] → [0, 1] to make your own; any plain callable works too. Most take
`mode="in"` (spacing gradually increases), `"out"` (gradually decreases), or
`"in_out"`.

| Curve | Character |
|---|---|
| `LinearSpacing()` | equal spacing (default) |
| `PowerSpacing(exponent, mode)` | general "by how much" control; 1 = equal |
| `QuadraticSpacing(mode)` | classic t² easing |
| `CubicSpacing(mode)` | classic t³ easing |
| `SineSpacing(mode)` | gentle bias |
| `ExponentialSpacing(mode, strength)` | dramatic clustering, tunable |
| `CircularSpacing(mode)` | quarter-arc profile |
| `SmoothstepSpacing()` | inherently in-out, dense at both ends |
| `ReversedSpacing(curve)` | mirror any curve, including plain callables |
| `CompositeSpacing(*curves)` | chain eases left to right |
| `TableSpacing(points)` | draw the curve by hand from control points |

## Notes on geometry

- Angles use the standard math convention (y-up). For a coordinate system
  whose y-axis points down (screen/raster style), call `design.flipped_y()`
  or pass `flip_y=True` to `fit`.
- Spacing is measured in distance *along the curve*. When gaps are small
  relative to the local radius (the usual case), the straight-line distance
  between neighbors is effectively identical; only a gap that curls around a
  large fraction of a tight turn dips noticeably below its along-curve
  length.
- `by="parameter"` restores parametric spacing (equal steps through the
  curve's own parametrization), which visually compresses toward tight
  sections — occasionally useful as a design effect.
- Degenerate inputs are handled gracefully: an endpoint on the center yields
  a radial line; identical start and end with `turns=0` yields coincident
  points; NaN and infinity are rejected at `Path` construction rather than
  propagating silently into your output.

## Development

```bash
git clone <repo-url> && cd geomotif
pip install -e . --group dev    # editable install + pytest + matplotlib
pytest                          # run the test suite
```

Build and publish:

```bash
python -m build                 # or: uv build / hatch build
twine upload dist/*             # or PyPI trusted publishing via CI
```

## License

[MIT](LICENSE)
