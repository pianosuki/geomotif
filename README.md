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

Zero dependencies for the core; matplotlib and scipy are optional extras.
Requires Python 3.12+.

> **Status:** the engine, the data model and the motif bases are complete, and
> the catalogue is filling in — 146 motifs today: the spirals, the primitives,
> the named curves, the roulettes, the polar/harmonic family, the fractals,
> the graph and number art, string art, the tilings, sacred geometry,
> guilloché, the mandala composers, Islamic strapwork, Celtic knotwork, the
> polyhedra, the optical illusions and the Voronoi family. Designs export to
> SVG, DXF, CSV, TXT and JSON, and to a spec file that records the recipe
> rather than the points; there is a `geomotif` command line for all of it.
> Next up is plugin packaging, then the docs site and gallery. Everything
> below already works for every motif, and for yours.

## Install

```bash
pip install geomotif           # core (no dependencies)
pip install 'geomotif[plot]'   # with matplotlib plotting helpers
pip install 'geomotif[scipy]'  # with the Voronoi/Delaunay family
pip install 'geomotif[all]'    # both
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
from geomotif.motifs import Icosahedron, PenroseP3, Triquetra, VoronoiCells
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

**Voronoi & Delaunay** (`geomotif.motifs.voronoi`, needs `[scipy]`) —
`Delaunay` (the triangulation), `Voronoi` (its dual, drawn as borders, each
one once), `VoronoiCells` (the same map as closed regions, with an optional
`inset`) and `LloydRelaxation` (points nudged to the middle of their own
cells until a clumped scatter comes out even). All four are one construction:
a cell is the region clipped by the bisector against each Delaunay
neighbour — no other bisector reaches it. These motifs are the only ones with
a dependency, and they carry `requires="scipy"`, so a machine without it can
still list and describe them; only building one raises.

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
registry.describe("voronoi.diagram").available  # False without the [scipy] extra
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

### Shipping it as a plugin

One entry point in your `pyproject.toml` is the whole contract:

```toml
[project.entry-points."geomotif.motifs"]
my_motifs = "my_package:register_all"
```

geomotif reads that group the first time anything touches its registry, so a
plugin nobody uses costs nothing to have installed. Once yours is installed it
is indistinguishable from a builtin: `geomotif list` shows it, `geomotif show`
documents it, `geomotif render` renders it, and it serializes to a spec.

[`examples/plugin/`](examples/plugin) is a complete worked one — Gielis's
superformula as an installable package, in about forty lines.

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

## Exporting

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

`save_points` flattens everything to one list. When the *strokes* matter —
where a plotter lifts the pen — use `save_design`, which keeps them apart:

```python
from geomotif import save_design, load_design

save_design(design, "design.csv")  # path,x,y — each row names its stroke
save_design(design, "design.txt")  # blank line between strokes
save_design(design, "design.json")  # structured, and the only one that reads back

design = load_design("design.json")
```

### SVG and DXF

Both writers are pure standard library — the core stays dependency-free all
the way out to the file:

```python
from geomotif import save_svg, save_dxf

save_svg(design, "design.svg", width=800, background="#fff")
save_dxf(design, "design.dxf", layer="CUTS")
```

SVG is for anything that displays; DXF R12 for anything that cuts, mills or
plots. They disagree about which way y points, and each writer settles that
rather than leaving it to you: SVG is y-down, so `flip_y=True` is the default
and a design comes out the way you drew it; DXF is y-up like the motifs
themselves, so nothing is mirrored and the design keeps its own measurements.

`to_svg` fits the design into the canvas before writing, so `stroke_width`
means one unit of the file you are looking at whatever the design measured.
Give `width` and `height` for an exact canvas, one of them to keep the
proportions, or neither to keep the design's own size plus `padding`. Loose
points become `<circle>` elements — that is the dot-art path — and the motif's
name becomes the document `<title>`, so a gallery file labels itself.

`to_dxf` writes `POLYLINE`/`VERTEX` rather than `LWPOLYLINE`, because
`LWPOLYLINE` arrived with R14 and R12 is the version everything reads. A
closed path carries the closed flag rather than a repeated final vertex, the
layer is declared in the file's own layer table, and the header records the
drawing extents so "zoom to fit" works when it opens.

### Specs: the recipe, not the points

A **spec** records the motif and its parameters rather than the geometry they
produced. It survives a change of point count, it is a file you can edit by
hand, and it is a great deal smaller — a mandala's recipe is 1.5 KB against
330 KB of coordinates:

```python
from geomotif import save_spec, load_spec

save_spec(motif, "design.json")
motif = load_spec("design.json")
design = motif.generate(2000)  # ...at whatever resolution you want today
```

```json
{
  "geomotif": "1.0.0",
  "motif": "spiral.fibonacci",
  "params": {
    "quarters": 9,
    "size": 10.0
  }
}
```

A parameter that is itself a motif — the composers take one — nests as the
same object, so a mandala's rings serialize without a second notation. Every
motif in the catalogue round-trips exactly, bar the two whose parameter *is* a
Python function: those are defined by code, not data, and say so when asked.
Loading a spec never imports a module the file names, only value types from
packages that already provide motifs here.

## Command line

Pure `argparse`, so the core stays dependency-free:

```bash
geomotif list                                   # every motif, grouped by family
geomotif list --family fractal
geomotif show rose                              # docs, parameters, defaults
geomotif render rose --n 5 --samples 400 --out rose.svg
geomotif render spiral.golden --samples 300 --ease power:2.5 --out s.csv
geomotif render fractal.hilbert --depth 6 --out h.dxf --fit 800x800
geomotif render --spec my-design.json --out out.svg
geomotif gallery --out docs/gallery             # all 146, plus a manifest
geomotif demo
```

A motif's flags come from its dataclass fields — `--n`, `--depth`,
`--center 0,0`, `--merge/--no-merge` — the same declaration that drives
`describe()` and the spec format. `geomotif show NAME` or
`geomotif render NAME --help` lists them.

Two consequences worth knowing:

- **Not every parameter can be said on a command line.** A motif taking a
  Python function, another motif, or a point set has no sensible flag; those
  take their value from the motif's registered example, so all 146 render.
  `geomotif render voronoi.cells --inset 0.2` works — the point set is the
  example's, and the inset is yours.
- **The sampling options are `--samples`, `--stride` and `--ease`**, not the
  more obvious words: `points`, `count`, `step` and `spacing` are all motif
  parameter names already, and argparse has one namespace.

Without `--out` the points go to stdout as CSV, so the command pipes.
`--fit 800x600` scales onto a canvas; `--ease` takes `linear`, `power:2.5`,
`exp:out:6`, `smoothstep` and the rest.

## Plotting

To see the points on a graph (requires the `plot` extra):

```python
import matplotlib.pyplot as plt
from geomotif.plotting import plot_design, plot_comparison, DARK

plot_design(design, show_points=True, center=(0, 0), title="my spiral")
plt.show()
```

`plot_comparison` is the library's premise in one figure — one motif, one
point count, several spacing curves:

```python
from geomotif import PowerSpacing, ExponentialSpacing, SmoothstepSpacing

fig = plot_comparison(
    spiral,
    [None, PowerSpacing(2.5), ExponentialSpacing(mode="out", strength=6), SmoothstepSpacing()],
)
```

`plot_grid` draws several designs side by side, and every function takes a
`palette=` — `LIGHT` or `DARK` — so a dark-mode figure is a different
argument rather than a different code path.

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
pip install -e . --group dev    # editable install + pytest, matplotlib, scipy
pytest                          # run the test suite
```

Build and publish:

```bash
python -m build                 # or: uv build / hatch build
twine upload dist/*             # or PyPI trusted publishing via CI
```

## License

[MIT](LICENSE)
