<h1 align="center">geomotif</h1>

<p align="center">
  <em>Generate and plot geometric designs, and control exactly where the points along them land.</em>
</p>

<p align="center">
  <img src="docs/assets/spiral.golden.svg" width="140" alt="golden spiral">
  <img src="docs/assets/rose.maurer.svg" width="140" alt="Maurer rose">
  <img src="docs/assets/fractal.hilbert.svg" width="140" alt="Hilbert curve">
  <img src="docs/assets/tiling.penrose-p3.svg" width="140" alt="Penrose P3 tiling">
  <img src="docs/assets/knot.celtic-grid.svg" width="140" alt="Celtic knot plait">
  <img src="docs/assets/mandala.svg" width="140" alt="mandala">
</p>

<p align="center">
  <a href="https://pypi.org/project/geomotif/"><img src="https://img.shields.io/pypi/v/geomotif" alt="PyPI"></a>
  <a href="https://pypi.org/project/geomotif/"><img src="https://img.shields.io/pypi/pyversions/geomotif" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://pianosuki.github.io/geomotif/explore/"><strong>Open the explore stage &rarr;</strong></a>
</p>

```bash
pip install geomotif
```

Zero dependencies for the core, Python 3.12+. matplotlib and scipy are optional
extras, and nothing on the path from a motif to an SVG file needs either.

**[Documentation](https://pianosuki.github.io/geomotif/)** ·
**[Gallery](https://pianosuki.github.io/geomotif/gallery/)** ·
**[catalog](docs/catalog.md)** ·
**[Changelog](CHANGELOG.md)**

---

## The whole mental model

A **motif** is a parameterized recipe for geometry. Applying a **transform** to
what it produced gives a **design**, which is what you plot or export.

```python
from geomotif import PowerSpacing
from geomotif.motifs import SpiralBetween

spiral = SpiralBetween(
    start=(200, 0),  # required — first point (always included)
    end=(20, 0),  # required — last point (always included)
    center=(0, 0),  # point the spiral winds around (default shown)
    turns=3,  # extra full revolutions (default 0)
)

design = spiral.generate(100, spacing=PowerSpacing(2.5))

for x, y in design:
    ...
```

`build()` gives a motif at its native resolution; `generate()` gives you the
points you actually plot. Everything after the count is keyword-only:

```python
spiral.generate(100)  # 100 points, equally spaced
spiral.generate(100, spacing=PowerSpacing(2.5))  # eased distribution
spiral.generate(step=5.0)  # a point every 5 units of real distance
spiral.generate(100, by="parameter")  # parametric instead of arc-length
```

## Why arc length is the point

Most plotting code spaces points by *parameter* — equal steps through whatever
variable the formula happens to use. On a spiral that puts the points bunched
up at the tight end and stretched out at the wide end, which is not what "100
evenly spaced points" is supposed to mean.

geomotif measures the curve with a dense polyline, builds a cumulative-length
table, and inverts it. Equal spacing means the same **real x,y distance**
between every consecutive pair of points, however tightly the curve winds.

Because that engine works on *polylines* rather than on formulas, it applies to
every motif in the catalog, closed-form or not, and to yours. `step=` is the
mode you want for plotter output and dot placement: the gap is fixed and the
count falls out of the geometry.

→ [Where the points land](https://pianosuki.github.io/geomotif/guide/points/)

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

Six lines of substance, and that class now has arc-length resampling, every
spacing curve, the transform layer, export to ten formats, spec serialization,
generated command-line flags, lookup by name and the whole conformance suite.
`MyFlower(k=5).generate(400)` works, and so does
`geomotif render my-flower --k 5 --out flower.svg`.

| Base | You implement |
|---|---|
| `PolarMotif` | `radius(theta) -> float` |
| `ParametricMotif` | `position(u) -> Point` |
| `MultiCurveMotif` | `curves() -> Iterable[Curve]` |
| `PolygonMotif` | `outlines() -> Iterable[Sequence[Point]]` |
| `SegmentMotif` | `nodes()` and `edges()` |
| `LSystemMotif` | an axiom, rewrite rules and a turn angle |
| `LatticeTiling` | `cell()` and `basis()` |
| `SubstitutionTiling` | `seed()`, `subdivide()` and `outline()` |

The one distinction worth getting right is `ParametricMotif` vs `PolygonMotif`:
a curve is *measured* at evenly spaced parameters, a polygon is *listed*.
Measuring a pentagon at 512 samples rounds all five of its corners off, so
shapes defined by their corners list them instead.

If none of them fits, subclass `Motif` and write `build()` by hand — one
method, returning a `Design`. You are not required to inherit at all: anything
with a `build() -> Design` method satisfies the `SupportsBuild` protocol and is
accepted everywhere a motif is.

### Shipping it as a plugin

One entry point in your `pyproject.toml` is the whole contract:

```toml
[project.entry-points."geomotif.motifs"]
my_motifs = "my_package:register_all"
```

geomotif reads that group the first time anything touches its registry, so a
plugin nobody uses costs nothing to have installed. Once yours is installed it
is indistinguishable from a builtin: `geomotif list` shows it, `geomotif show`
documents it, `geomotif render` renders it with flags generated from your
fields, it serializes to a spec, and the conformance suite runs against it.

[`examples/plugin/`](examples/plugin) is a complete worked one — Gielis's
superformula as an installable package, in about forty lines. CI installs it
into a clean environment on every push, to prove the discovery half works
outside the test suite.

→ [Extending geomotif](https://pianosuki.github.io/geomotif/extending/)

## What's in the box

**147 motifs in 19 families** — the [full catalog](docs/catalog.md), and
the [gallery](https://pianosuki.github.io/geomotif/gallery/) with a picture of
every one.

| Family | | What is in it |
|---|--:|---|
| **spiral** | 11 | Archimedean, logarithmic, golden, Fibonacci (the quarter-arc approximation everyone actually draws — both are here because they are not the same curve), Fermat, hyperbolic, lituus, Theodorus, Euler/clothoid, circle involute, and the endpoint-to-endpoint `SpiralBetween` |
| **primitive** | 16 | circle, ellipse, arc, sector, line, rectangle, rounded rectangle, regular polygon, star polygon (the `{n/k}` family — `{6/2}` correctly comes back as two triangles), superellipse, squircle, Reuleaux polygon, egg, point grid, Poisson disc |
| **curve** | 18 | heart, cardioid, lemniscate, Cassini oval (two strokes when it really is two lobes), limaçon, butterfly, fish, bow, astroid, deltoid, nephroid, folium, cochleoid, cycloid, trochoid, witch of Agnesi, cornoid |
| **roulette** | 6 | hypotrochoid, epitrochoid, hypocycloid, epicycloid, Spirograph in the toy's own terms, and `Epicycles` — two arms is a trochoid, several dozen is a Fourier series |
| **polar** | 4 | rose (with the petal count right: `n` or `2n`, by a parity rule most implementations get wrong), Maurer rose, phyllotaxis, and a one-off radius function |
| **harmonic** | 3 | Lissajous, harmonic, and harmonograph |
| **fractal** | 23 | Koch, Minkowski, Sierpiński, dragon, Lévy C, Hilbert, Moore, Peano, Gosper, Vicsek — sixteen of them a grammar and nothing else — plus the carpet, Cantor set, Pythagoras tree, H-tree, Apollonian gasket (Descartes' circle theorem, so the curvatures come out integral), and two by chaos game |
| **graph** | 7 | complete, cyclic/circulant, bipartite, chord diagram, prime chords, and the modular times-table cardioid |
| **string-art** | 3 | the corner parabola everybody has made, the polygon and circle versions, and the general envelope engine the rest are special cases of |
| **tiling** | 12 | square, triangular, hexagonal, rhombille, Cairo pentagonal, truncated square, snub square, herringbone at any brick proportion; Penrose P3 and P2, Ammann–Beenker; and Truchet, which tosses a coin per cell |
| **sacred** | 7 | one construction, five figures: vesica → seed → flower → fruit → Metatron's cube, plus Sri Yantra and the golden rectangle |
| **guilloche** | 3 | the engine-turned line work of banknotes and watch dials |
| **girih** | 6 | the five Islamic strapwork tiles, tenfold layouts, Hankin's rule applied until the tiles vanish and ten-pointed stars are left, and the shamsa rosettes |
| **knot** | 5 | triquetra, endless knot, circular and square Celtic knots, and the plait every knotwork panel is built on — over-and-under worked out rather than declared |
| **solid** | 7 | the five Platonic solids and the truncated icosahedron as wireframes, through an orthographic, isometric or perspective projection |
| **illusion** | 6 | Penrose triangle and stairs, impossible cube, Necker cube, café wall, moiré. The two Penrose figures are built in space and then flattened: their walks genuinely fail to close, by exactly the amount an isometric view cannot show |
| **voronoi** | 4 | Delaunay, Voronoi, cells with an optional inset, and Lloyd's relaxation. The only motifs with a dependency — they declare `requires="scipy"`, so a machine without it can still list and describe them |
| **symmetry** | 1 | the experimental one: points constrained to the orbits of a `Cn`/`Dn` group and relaxed until neighbours sit the same distance apart — fifteen points with five-fold mirror symmetry, and the arithmetic that says which counts are possible at all |
| **mandala** | 5 | the composers: rings of a repeated unit, a kaleidoscope under a `Cn`/`Dn` group, a snowflake grown from a seed, spokes and layered rings — whose unit is *any* object with a `build()` method, including yours |

Anything registered is reachable by name, with its parameters introspectable:

```python
from geomotif.core import registry

registry.families()  # ('curve', 'fractal', 'girih', 'graph', 'guilloche', ...)
registry.names(family="spiral")  # ('spiral.archimedean', 'spiral.between', ...)
registry.create("polygon.star", points=7, step=3)
registry.describe("egg").params  # name, type, default for each
registry.describe("voronoi.diagram").available  # False without the [scipy] extra
```

## Designs, paths and points

A `Design` holds stroked `Path` polylines plus loose `points` that carry no
stroke (dot art, scatter fields). It iterates as a flat stream of points, so it
drops straight into anything expecting coordinates:

```python
len(design)  # total point count
design.bounds  # Bounds(min_x, min_y, max_x, max_y)
design + other  # overlay
design.fit(800, 600, padding=20)  # scale and center onto a canvas
design.flipped_y()  # y-down (screen/SVG) coordinates
```

Everything is immutable — operations return a new design — and NaN and infinity
are rejected at construction rather than propagating silently into your output.

```python
import math

from geomotif import Affine, jitter, radial_repeat, tile

rosette = radial_repeat(petal, 12)  # the mandala workhorse
lattice = tile(cell, 8, 8, dx=20, dy=20, stagger=0.5)
turned = design.transformed(Affine.rotate(math.pi / 6))
loose = jitter(design, 0.5, seed=7)  # reproducible irregularity
aligned = design.snapped(0.5)  # every point onto a half-unit grid
```

`Affine` composes with `@` — `(m @ n)(p) == m(n(p))`, so the right-hand
transform applies first.

→ [Designs, paths and transforms](https://pianosuki.github.io/geomotif/guide/designs/)

## Exporting

```python
from geomotif import save_design, save_dxf, save_gif, save_points, save_spec, save_svg

save_points(design, "points.csv")  # x,y — for anything that just wants numbers
save_design(design, "design.txt")  # strokes kept apart, a blank line between them
save_svg(design, "design.svg", width=800)  # anything that displays
save_dxf(design, "design.dxf", layer="CUTS")  # anything that cuts, mills or plots
save_gif(frames, "design.gif")  # an animation, LZW and all
save_spec(motif, "design.json")  # the recipe, not the points
```

Every writer is pure standard library — the core stays
dependency-free all the way out to the file. SVG fits the design into the
canvas before writing, so `stroke_width` means one unit of the file you are
looking at; DXF is R12, using `POLYLINE`/`VERTEX` rather than the R14-era
`LWPOLYLINE`, because R12 is the version everything reads.

A **spec** records the motif and its parameters instead of the geometry they
produced. It survives a change of point count, it is a file you can edit by
hand, and it is a great deal smaller — a mandala's recipe is 1.5 KB against
330 KB of coordinates:

```json
{
  "geomotif": "1.2.2",
  "motif": "spiral.fibonacci",
  "params": { "quarters": 9, "size": 10.0 }
}
```

A parameter that is itself a motif — the composers take one — nests as the same
object, so a mandala's rings serialize without a second notation. Every motif
in the catalog round-trips exactly, but the two whose parameter *is* a Python
function: those are defined by code, not data, and say so when asked.

→ [Exporting](https://pianosuki.github.io/geomotif/guide/export/)

## Command line

```bash
geomotif list                                   # every motif, grouped by family
geomotif show rose                              # docs, parameters, defaults
geomotif render rose --n 5 --samples 400 --out rose.svg
geomotif render spiral.golden --samples 300 --ease power:2.5 --out s.csv
geomotif render fractal.hilbert --depth 6 --out h.dxf --fit 800x800
geomotif render --spec my-design.json --out out.svg
geomotif render tiling.truchet --out plot.svg --paper a4 --optimize
geomotif render fractal.hilbert --out hilbert.gif --frames 60
geomotif render fractal.hilbert --out hilbert.gif --frames 60 --hold 12
geomotif explore rose --out rose.html           # sliders for its parameters
geomotif gallery --out gallery                  # all 147, plus a manifest
geomotif demo
```

Pure `argparse`, so the core stays dependency-free. A motif's flags come from
its dataclass fields — the same declaration that drives `describe()` and the
spec format. Two consequences worth knowing:

- **Not every parameter can be said on a command line.** A motif taking a
  Python function, another motif, or a point set has no sensible flag; those
  take their value from the motif's registered example, so all 147 render.
  `geomotif render voronoi.cells --inset 0.2` works — the point set is the
  example's, the inset is yours.
- **The sampling options are `--samples`, `--stride` and `--ease`**, not the
  more obvious words: `points`, `count`, `step` and `spacing` are already motif
  parameter names, and argparse has one namespace.

Without `--out` the points go to stdout as CSV, so the command pipes.

→ [The command line](https://pianosuki.github.io/geomotif/guide/cli/)

## Color, layers and pens

A `Style` says which pen draws a stroke — a layer name, a color, a width — and
rides in `Design.meta` rather than in `Path`, because none of it changes the
maths. Layers are what a two-pen drawing is made of:

```python
from geomotif import layer, styled
from geomotif.io.plotter import optimize, save_plotter_svg

drawing = layer(
    styled(outline.build(), layer="black", stroke="#000"),
    styled(shading.build(), layer="red", stroke="#c00"),
)
save_plotter_svg(optimize(drawing), "two-pens.svg", paper="a4")
```

That file is measured in real millimeters, opens in Inkscape as two named
layers, and loads into [`vpype`](https://vpype.readthedocs.io/) as two layers —
or skip the file with `to_vpype(design)`. `optimize` joins strokes whose ends
meet and orders what is left so the pen wastes less time in the air: a Truchet
tiling goes from 72 strokes and 2742 units of pen-up travel to 13 and 533,
drawing exactly the same ink. Neither pass ever crosses a layer, because
strokes on different layers are drawn by different pens.

→ [color and layers](https://pianosuki.github.io/geomotif/guide/style/) ·
[Plotting it for real](https://pianosuki.github.io/geomotif/guide/plotter/)

## Animation

```python
from geomotif.animate import draw_on, spin, sweep
from geomotif.io.gif import save_gif
from geomotif.motifs import HilbertCurve

save_gif(draw_on(HilbertCurve(depth=5).build(), frames=60), "hilbert.gif")
```

`draw_on` reveals a design the way a pen would, measuring progress in arc
length so the pen moves at a constant speed; `spin` turns it; `sweep` rebuilds
a motif once per value of one of its parameters. Each returns a plain tuple of
designs, so frames compose with every transform and every exporter. The GIF
writer is hand-rolled — color table, frame timing, LZW — so animation costs no
dependency either.

→ [Animation](https://pianosuki.github.io/geomotif/guide/animation/)

## Plotting

To see the points on a graph (requires the `plot` extra):

```python
import matplotlib.pyplot as plt

from geomotif.plotting import DARK, plot_comparison, plot_design

plot_design(design, show_points=True, center=(0, 0), title="my spiral")
plt.show()
```

`plot_comparison` is the library's premise in one figure — one motif, one point
count, several spacing curves. `plot_grid` draws several designs side by side,
and every function takes a `palette=` (`LIGHT` or `DARK`), so a dark-mode
figure is a different argument rather than a different code path.

## Spacing curves

All curves subclass `SpacingCurve` — implement `ease(t)` mapping [0, 1] → [0, 1]
to make your own; any plain callable works too. Most take `mode="in"` (spacing
gradually increases), `"out"` (gradually decreases) or `"in_out"`.

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

- Angles use the standard math convention (y-up). For a coordinate system whose
  y-axis points down (screen/raster style), call `design.flipped_y()` or pass
  `flip_y=True` to `fit`.
- Spacing is measured along the curve; for small gaps that is effectively
  identical to straight-line distance. Only a gap that curls around most of a
  tight turn dips noticeably below it.
- `by="parameter"` restores parametric spacing, which visually compresses
  toward tight sections — occasionally useful as a design effect.
- Degenerate inputs are handled gracefully: an endpoint on the center yields a
  radial line, and identical start and end with `turns=0` yields coincident
  points.

## Development

```bash
git clone https://github.com/pianosuki/geomotif && cd geomotif
pip install -e . --group dev    # editable install + pytest, matplotlib, scipy
make check                      # ruff, ruff-format, mypy strict, pytest
make docs-serve                 # the documentation site, with live reload
```

`make docs-gen` regenerates the derived documentation and `make docs-check`
fails if the committed part of it has fallen behind the code. Both run in CI,
along with the test suite on 3.12/3.13/3.14 across Linux, macOS and Windows, a
job that installs the package with no extras at all, and a job that installs
`examples/plugin/` into a clean environment.

## License

[MIT](LICENSE)
