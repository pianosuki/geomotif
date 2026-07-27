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
> the catalogue is filling in — 27 motifs today: the full spiral family and
> the primitives. Named curves, roulettes, fractals, tilings and the rest are
> next. Everything below already works for all of them, and for yours.

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
from geomotif.motifs import GoldenSpiral, ReuleauxPolygon, StarPolygon
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

Anything registered is also reachable by name, with its parameters
introspectable:

```python
from geomotif.core import registry

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
