# Refactor Plan: `spiralgen` → **`geomotif`**, a general geometry design plotter library

**Status:** approved — name, base-class abstraction, and Python floor all decided; ready to execute
**Author:** drafted 2026-07-27
**Scope:** rework the package from a single-purpose spiral generator into an extensible
library for generating and plotting *any* graphable geometric design, with the spiral
remaining as one motif among many.

---

## 1. Where we are today

The current package is small, clean, and does one thing well:

| File | Lines | Role |
|---|---:|---|
| `src/spiralgen/generator.py` | 164 | `generate_spiral()` — the whole engine |
| `src/spiralgen/curves.py` | 197 | `SpacingCurve` ABC + 8 easing curves |
| `src/spiralgen/io.py` | 92 | CSV / TXT / JSON export |
| `src/spiralgen/plotting.py` | 163 | matplotlib helpers (optional extra) |
| `src/spiralgen/demo.py` | 121 | showcase entry point |
| `tests/` | 268 | generator, curves, io |

**What is genuinely good here and must survive the refactor:**

1. **True arc-length positioning.** `generate_spiral` measures the curve with a dense
   polyline, builds a cumulative-length table, and inverts it so that "equal spacing"
   means equal *real* distance. This is the crown jewel and the reason the output is
   useful for dot art and object placement. Today it is welded to one curve; it should
   become a service that applies to *every* motif.
2. **Pluggable spacing curves.** A clean ABC with `ease(t)`, modal in/out/in-out
   machinery in one shared base, and correct normalization. Needs almost no change.
3. **The modern-Python texture.** PEP 695 `type` aliases, `@override`, `match`
   statements, ABCs, `TYPE_CHECKING`-guarded imports, keyword-only API surface,
   `py.typed`, strict mypy, ruff with a broad rule selection, `uv`, hatchling,
   pre-commit, a three-job CI matrix, a Makefile, Keep-a-Changelog.
4. **Zero-dependency core**, with matplotlib isolated behind an extra.
5. **Docstring quality.** NumPy-style parameter blocks, and comments that explain
   *why* (the degenerate-center `match`, the truncating `zip`, the backend fallback).

**The current spiral, precisely:** `position(u)` interpolates radius linearly against a
linearly-interpolated angle — i.e. `r = a + bθ`. That is an **Archimedean spiral**
(specifically the endpoint-constrained arithmetic spiral). It is *one* of at least a
dozen classical spirals, and the refactor should name it as such and add the rest.

---

## 2. What we are building

A library where:

- A **design** is a first-class value: a bundle of polyline paths plus loose points,
  with bounds, transforms, resampling, and export.
- A **motif** is a small, declarative, introspectable object that knows how to build a
  design. Users subclass one of a handful of base classes — usually writing 3–10 lines
  of maths — and get arc-length resampling, spacing curves, transforms, SVG/DXF export,
  CLI exposure, and the conformance test suite for free.
- Third parties can ship their own motifs in their own packages and have them
  auto-discovered.

The decisions already locked in:

| Decision | Choice |
|---|---|
| **Name** | **`geomotif`** — confirmed free on PyPI (§3) |
| **Base class** | **`Motif`**, with `ParametricMotif` / `PolarMotif` / `LSystemMotif` / `SegmentMotif` / `TilingMotif` beneath it (§4.2, §5) |
| **Python floor** | **`>=3.12`**, tested on 3.12 / 3.13 / 3.14 (§10.1) |
| Core result type | Unified `Design` (paths + loose points + metadata) |
| Dependencies | Zero-dep core; numpy/scipy-dependent motifs behind extras |
| Back-compat | Clean break — no `generate_spiral()` shim |
| Extra surfaces | SVG/DXF export, real CLI, plugin registry, transform layer — all in |

---

## 3. Naming — **decided: `geomotif`**

The project is renamed **`geomotif`** (*geo-mo-teef*): geometry + motif. It says
exactly what the library does to anyone reading a PyPI page, a GitHub repo, or a
resume, and it carries strong search relevance for "geometric pattern generator
python". The name is used identically across all four surfaces:

| Surface | Value                                                |
|---|------------------------------------------------------|
| PyPI distribution | `geomotif`                                           |
| Import name | `import geomotif`                                    |
| Source tree | `src/geomotif/`                                      |
| GitHub repo | `github.com/pianosuki/geomotif`                      |
| CLI command | `geomotif`                                           |
| Plugin entry-point group | `geomotif.motifs`                                    |
| Optional extras | `geomotif[plot]`, `geomotif[scipy]`, `geomotif[all]` |

**PyPI availability confirmed** — `geomotif` is unregistered and free to claim. Worth
reserving it with a `0.0.0` placeholder release early, well before you are ready to
publish for real, along with the matching GitHub repo.

The name also settles the library's central abstraction: the base class users subclass
is **`Motif`** (§4.2). That gives the whole project one word for one idea —

```python
from geomotif import Motif, PolarMotif       # the library and its abstraction agree
```

— and it resolves what would otherwise be a naming collision, because the small
repeated unit fed to `radial_repeat()` or a `Mandala` ring (§4.5, §6.12) *is* itself a
`Motif`. One term, one meaning, everywhere. The docs lean on
**motif → transform → design** as the mental model throughout:

| Term | Meaning |
|---|---|
| `Motif` | A parameterized recipe for geometry — what you subclass and what you register |
| *transform* | An `Affine` or composite operator applied to what a motif produced |
| `Design` | The concrete result: paths + loose points + metadata, ready to plot or export |

<details>
<summary><strong>Alternatives considered</strong> (kept for the record)</summary>


| # | Name | How it reads | Why it fits | Risk |
|---|---|---|---|---|
| 1 | **traceform** | *trace-form* | "Trace" = plotting a path point by point; "form" = the geometry. Covers line art, dot art, and plotter output equally. Distinctive, easy to say and spell. | Low — likely free |
| 2 | **geomotif** | *geo-mo-teef* | Literally geometry + motif. Immediately says "geometric patterns" to anyone reading a resume or a PyPI page. Strong search relevance. | Low — likely free |
| 3 | **tessera** | *tess-er-a* | A single tile of a mosaic. Elegant, classical, unmistakably about geometric composition. Great logo potential. | Medium — short Latin names get squatted |
| 4 | **figura** | *fig-oo-ra* | Latin for shape/figure. Clean and professional; reads well in code (`from figura import Rose`). | Medium — generic, may be taken |
| 5 | **arabesque** | *ar-a-besk* | The most beautiful option; evokes ornamental geometry, girih, rosettes. | Medium — implies Islamic ornament specifically, slightly narrows the story; longer to type |
| 6 | **plotwright** | *plot-write* | "Wright" = maker. Sounds like a serious tool. Pairs naturally with a CLI. | Medium — Playwright association |
| 7 | **kolam** | *koh-lum* | South Indian dot-and-line geometric art — *exactly* this library's subject matter (dots plus curves around them). Culturally rich and almost certainly free. | Medium — obscure to Western audiences; consider whether you want to carry the cultural reference |
| 8 | **curveforge** | *curve-forge* | Direct, maker-y, obviously about curves. | Low–medium — "-forge" is a crowded suffix |
| 9 | **spiroform** | *spy-ro-form* | Keeps lineage with `spiralgen` while generalizing. | Medium — still sounds spiral-first, which is the thing we're fixing |
| 10 | **lineform** | *line-form* | Plain, descriptive, safe. | Medium — a bit flat, possibly taken |
| 11 | **glyphon** | *glif-on* | Coined, memorable, tech-forward. | Low — but meaning is opaque |
| 12 | **geomancer** | *gee-o-man-ser* | Memorable and playful (geomancy = divination by figures drawn in earth). Great README voice. | Medium — mystical framing may read less "serious engineering" |

The runners-up were `traceform` (broadest, most neutral) and `tessera` (most elegant,
highest squatting risk). They remain the fallbacks if `geomotif` turns out to be taken.

</details>

The old `spiralgen` name is retired entirely — nothing has been published, so there is
nothing to deprecate (see §11).

---

## 4. Core architecture

### 4.1 The data model

```python
# geomotif/core/types.py
type Point = tuple[float, float]

@dataclass(frozen=True, slots=True)
class Bounds:
    min_x: float; min_y: float; max_x: float; max_y: float
    @property
    def width(self) -> float: ...
    @property
    def height(self) -> float: ...
    @property
    def center(self) -> Point: ...

@dataclass(frozen=True, slots=True)
class Path:
    """One continuous polyline. `closed` means the last point connects back."""
    points: tuple[Point, ...]
    closed: bool = False

    def __iter__(self) -> Iterator[Point]: ...
    def __len__(self) -> int: ...
    @property
    def length(self) -> float: ...      # polyline length, wraps if closed
    @property
    def bounds(self) -> Bounds: ...

@dataclass(frozen=True, slots=True)
class Design:
    """The universal result: zero or more strokes plus zero or more loose points."""
    paths: tuple[Path, ...] = ()
    points: tuple[Point, ...] = ()          # dot art / point sets with no stroke
    meta: Mapping[str, object] = FROZEN_EMPTY

    def __iter__(self) -> Iterator[Point]:  # flattens paths then loose points
    def __len__(self) -> int:
    def __add__(self, other: Design) -> Design:      # overlay / merge
    @property
    def bounds(self) -> Bounds: ...
    def transformed(self, m: Affine) -> Design: ...
    def resampled(self, count=None, *, step=None, spacing=None, ...) -> Design: ...
    def fit(self, width, height, *, padding=0.0, flip_y=False) -> Design: ...
```

Everything is immutable, so designs compose without aliasing surprises and can be
cached, hashed by structure, and safely shared between threads.

> **Implementation note (real trap):** `functools.cached_property` does **not** work on
> `slots=True` dataclasses. `Path.length` and `Design.bounds` must be either plain
> recomputing properties (fine — they are O(n) and rarely hot) or backed by an explicit
> private field written via `object.__setattr__` in `__post_init__`. Do **not** silently
> drop `slots=True` to get `cached_property`; the memory win matters at 100k points.
> The arc-length table is a separate explicit object (§4.3) precisely so the hot path
> has somewhere to live.

`Design.meta` carries the motif name and resolved parameters (including any resolved
random seed). This is what makes designs reproducible, serializable to a JSON spec, and
self-labelling in the gallery.

### 4.2 The motif contract

```python
# geomotif/core/motif.py
@runtime_checkable
class SupportsBuild(Protocol):
    """Structural contract — any object with build() works everywhere."""
    def build(self) -> Design: ...

class Motif(ABC):
    """Convenience base: implement build(), inherit everything else."""

    @abstractmethod
    def build(self) -> Design:
        """Return the design at its natural/native resolution."""

    def generate(
        self,
        count: int | None = None,
        *,
        step: float | None = None,
        spacing: SpacingCurve | Callable[[float], float] | None = None,
        distribute: Distribution = "length",
    ) -> Design:
        """Build, then resample to `count` points (or a fixed `step` distance)."""
        return resample(self.build(), count, step=step, spacing=spacing,
                        distribute=distribute)
```

`Motif` is the **name** of the abstraction as well as of the library — subclassing it
is the one thing a user must learn to extend `geomotif`, and `class MyFlower(Motif)`
says precisely what it is. `SupportsBuild` is its structural twin, following the
`typing.SupportsInt` convention: anything with a `build() -> Design` method is accepted
everywhere a `Motif` is, so users are never *forced* to inherit. The ABC exists to hand
you `generate()`, transforms and registration for free, not to police the type.

Two entry points, clearly separated:

- `build()` — the motif's own idea of itself, at native resolution.
- `generate()` — what you actually plot: a specific number of points, distributed the
  way you asked.

Because `generate()` lives on the base and delegates to a generic resampler that works
on *any* polyline, **the arc-length engine and every spacing curve automatically apply
to every motif in the library, including fractals, tilings, and string art.** That is
the single most important structural idea in this plan.

`distribute` controls how a total `count` is spread across a multi-path design:

| Value | Behaviour |
|---|---|
| `"length"` (default) | Proportional to each path's arc length — uniform visual density |
| `"even"` | `count // len(paths)` per path — uniform per-stroke detail |
| `"per_path"` | `count` points on *each* path |

Passing `step=` instead of `count=` gives a fixed real distance between consecutive
points and lets the count fall out of the geometry. This is the mode you want for
plotter output and dot placement.

### 4.3 Sampling engine

`geomotif/core/sampling.py` — the extracted, generalized heart of the old
`generator.py`:

```python
class ArcTable:
    """Cumulative-length table over a polyline, with O(log n) inverse lookup."""
    def __init__(self, points: Sequence[Point], *, closed: bool = False) -> None: ...
    @property
    def total(self) -> float: ...
    def point_at(self, distance: float) -> Point: ...     # linear interp within segment
    def point_at_fraction(self, s: float) -> Point: ...

def densify(fn: Callable[[float], Point], *, samples: int) -> tuple[Point, ...]: ...
def resample_path(path: Path, count=None, *, step=None, spacing=None) -> Path: ...
def resample(design: Design, count=None, *, step=None, spacing=None,
             distribute="length") -> Design: ...
```

The existing `bisect`-based inversion, the `_MIN_SAMPLES` / `_SAMPLES_PER_TURN`
adaptive density heuristic, and the degenerate zero-length handling all move here
essentially unchanged — just widened from "spiral" to "any polyline".

### 4.4 Spacing curves

`curves.py` → `geomotif/core/spacing.py`, otherwise **kept as-is**. It is already good.
Small additions:

- `ReversedSpacing(curve)` — mirror any curve.
- `CompositeSpacing(*curves)` — chain eases.
- `TableSpacing(points)` — arbitrary user-supplied control points, monotone-interpolated.
- A `SpacingLike` type alias (`SpacingCurve | Callable[[float], float]`) and one
  `_coerce_spacing()` helper, replacing the ad-hoc `callable()` check in the old
  generator.

The module rename also frees the name `curves` for `motifs/curves.py` (heart,
butterfly, lemniscate…), which is where a reader would expect to find it.

### 4.5 Transforms and composition

`geomotif/core/transform.py`:

```python
@dataclass(frozen=True, slots=True)
class Affine:
    a: float; b: float; c: float; d: float; e: float; f: float

    @classmethod
    def identity(cls) -> Self: ...
    @classmethod
    def translate(cls, dx: float, dy: float) -> Self: ...
    @classmethod
    def rotate(cls, angle: float, *, about: Point = (0.0, 0.0)) -> Self: ...
    @classmethod
    def scale(cls, sx: float, sy: float | None = None, *, about=(0,0)) -> Self: ...
    @classmethod
    def mirror(cls, angle: float = 0.0, *, through: Point = (0.0, 0.0)) -> Self: ...
    @classmethod
    def shear(cls, kx: float, ky: float = 0.0) -> Self: ...

    def __matmul__(self, other: Affine) -> Affine: ...   # composition
    def __call__(self, p: Point) -> Point: ...
```

Composite operators (functions taking and returning a `Design`):

| Operator | Purpose |
|---|---|
| `radial_repeat(design, n, *, about, mirror=False)` | The mandala/rosette workhorse |
| `tile(design, cols, rows, *, dx, dy, stagger=0.0)` | Lattice repetition |
| `mirror_axis(design, angle, *, through)` | Reflection symmetry |
| `symmetry_group(design, group)` | Full cyclic `Cn` / dihedral `Dn` application |
| `jitter(design, amount, *, seed)` | Controlled hand-drawn irregularity |
| `layer(*designs)` / `Design.__add__` | Overlay |
| `fit_to(design, width, height, *, padding, flip_y)` | Canvas normalization |
| `clip_to(design, bounds)` | Trim to a rectangle |
| `offset_path(path, distance)` | Parallel/inset strokes (guilloché, knot outlines) |

This layer is why the motif catalogue stays sane: mandalas, snowflakes, rosettes,
kaleidoscopes and most tessellations are `radial_repeat`/`tile` applied to a simple
motif, not thirty hardcoded classes.

`y_down` support (currently a `generate_spiral` flag) becomes `Affine.scale(1, -1)` /
`Design.flipped_y()` / the `flip_y=` argument on `fit_to` and the SVG writer. That is
strictly more general and removes a confusing per-motif flag.

### 4.6 Registry and plugins

`geomotif/core/registry.py`:

```python
@register("rose")                    # or @register() → derives "rose" from Rose
@dataclass(frozen=True)
class Rose(PolarMotif): ...

def names() -> tuple[str, ...]: ...
def get(name: str) -> type[Motif]: ...
def create(name: str, /, **params: object) -> Motif: ...
def describe(name: str) -> MotifInfo: ...   # docstring + param specs from dataclass fields
```

Third-party discovery via `importlib.metadata.entry_points(group="geomotif.motifs")`,
loaded lazily on first registry access so import time stays flat. A plugin package
declares:

```toml
[project.entry-points."geomotif.motifs"]
my_motifs = "my_package.motifs:register_all"
```

**Why every builtin motif is a frozen dataclass:** `dataclasses.fields()` then yields
name, type, default and `metadata` for each parameter — which drives (a) automatic CLI
flag generation, (b) `describe()` for docs and the gallery, (c) JSON round-tripping of
a design spec, and (d) free `__repr__`/`__eq__`. One decision, four payoffs, zero
duplicated metadata. Validation lives in `__post_init__` with the same
`raise ValueError(f"... got {value}")` style the codebase already uses.

---

## 5. Motif base classes

Five bases cover roughly 90% of `ideas.txt`. This is where the "write your own design"
promise is delivered.

### 5.1 `ParametricMotif` — anything with `position(u)`

```python
class ParametricMotif(Motif):
    domain: ClassVar[tuple[float, float]] = (0.0, 1.0)
    closed: ClassVar[bool] = False
    resolution: int = 2048          # dense samples used to measure arc length

    @abstractmethod
    def position(self, u: float) -> Point: ...

    @override
    def build(self) -> Design:      # densify + wrap in a single Path
```

### 5.2 `PolarMotif` — anything with `radius(theta)`

```python
class PolarMotif(ParametricMotif):
    @abstractmethod
    def radius(self, theta: float) -> float: ...
    # position() derived; handles negative radii, theta_span, center offset
```

Writing a new motif becomes genuinely trivial — this is the headline example for the
README, and it is the whole extensibility story in eight lines:

```python
from geomotif import PolarMotif, register

@register("my-flower")
@dataclass(frozen=True)
class MyFlower(PolarMotif):
    k: float = 7.0
    theta_span: float = math.tau

    def radius(self, theta: float) -> float:
        return math.sin(self.k * theta) + 0.4 * math.cos(17 * theta)
```

That class immediately gains: arc-length resampling, all eight spacing curves,
transforms, SVG/DXF/CSV export, matplotlib plotting, a CLI subcommand with `--k` and
`--theta-span` flags, a gallery entry, and full conformance test coverage.

### 5.3 `LSystemMotif` — turtle graphics from a grammar

```python
class LSystemMotif(Motif):
    axiom: ClassVar[str]
    rules: ClassVar[Mapping[str, str]]
    angle: ClassVar[float]              # turn angle in radians
    depth: int = 4
    # '+' '-' turn, 'F'/'A'/'B' draw, 'f' move, '[' ']' push/pop → multiple paths
```

One base class yields Koch, Koch snowflake, Sierpinski triangle and arrowhead, Dragon,
Terdragon, Lévy C, Hilbert, Moore, Peano, Gosper, Vicsek, Pythagoras tree, H-tree and
Minkowski sausage — each as ~4 lines of class body.

### 5.4 `SegmentMotif` — straight lines between point sets

```python
class SegmentMotif(Motif):
    @abstractmethod
    def nodes(self) -> Sequence[Point]: ...
    @abstractmethod
    def edges(self) -> Iterable[tuple[int, int]]: ...
    # build() emits one 2-point Path per edge (optionally merged into polylines)
```

Covers complete graphs `Kₙ`, chord diagrams, modular multiplication circles (`i → k·i
mod n`), modular addition, prime chords, and all of string art.

### 5.5 `TilingMotif` — motif × lattice, or substitution

```python
class LatticeTiling(Motif):
    """Periodic tilings: a motif repeated on basis vectors, clipped to a region."""
    basis: tuple[Point, Point]
    region: Bounds

class SubstitutionTiling(Motif):
    """Aperiodic tilings: seed tiles + a subdivision rule, iterated `depth` times."""
    depth: int = 4
```

Covers square/triangular/hexagonal/rhombille/Cairo/truncated-square/snub-square,
Truchet tiles, Penrose P2 and P3, Ammann–Beenker, and girih.

### 5.6 Escape hatch

Anything that fits none of the above (Voronoi, Celtic knots, polyhedral projections)
subclasses `Motif` directly and writes `build()` by hand. That is exactly one method.

---

## 6. Motif catalogue

Everything below is drawn from `ideas.txt`, plus the basic shapes you asked for and the
full spiral family. **Phase** refers to §9.

### 6.1 Spirals — `motifs/spirals.py` (Phase 3a)

| Class | Definition | Notes |
|---|---|---|
| `ArchimedeanSpiral` | `r = a + bθ` | What the library does today |
| `LogarithmicSpiral` | `r = a·e^{bθ}` | The general logarithmic/equiangular spiral |
| `GoldenSpiral` | log spiral with `b = ln(φ)/(π/2)` | Preset; `φ` growth per quarter turn |
| `FibonacciSpiral` | quarter-arcs in a golden rectangle | The *drawn* approximation, distinct from the true golden spiral — worth having both |
| `FermatSpiral` | `r = a√θ` | Parabolic spiral, both branches |
| `HyperbolicSpiral` | `r = a/θ` | Asymptotic; needs a θ floor |
| `Lituus` | `r = a/√θ` | |
| `TheodorusSpiral` | discrete √n construction | Polyline by nature |
| `EulerSpiral` | clothoid, curvature ∝ arc length | Needs a Fresnel-integral helper (pure stdlib, series + asymptotic) |
| `CircleInvolute` | unwinding-string spiral | |
| `SpiralBetween` | endpoint-constrained | **Preserves today's exact behaviour**: start, end, center, turns, direction. Also exposed as `ArchimedeanSpiral.between(...)` |

Every spiral shares a `SpiralBase(PolarMotif)` handling turns, direction, θ-range and
center, so each concrete class is a one-line `radius()`.

### 6.2 Primitives — `motifs/primitives.py` (Phase 3a)

`Circle`, `Ellipse`, `Arc`, `Sector`, `Line`, `Rectangle`, `RoundedRectangle`,
`RegularPolygon(n, rotation)`, `StarPolygon(n, step)` (the `{n/k}` family — pentagram,
hexagram, and every other), `Star(points, inner_ratio)` (the "5-pointed star" people
actually mean), `Superellipse(n)` / `Squircle`, `ReuleauxPolygon(n)`, `Egg`,
`PointGrid`, `PoissonDiscPoints(seed)`.

### 6.3 Named curves — `motifs/curves.py` (Phase 3b)

`Heart` (both the cardioid form and the classic `16sin³t` curve), `Cardioid`,
`Lemniscate` (Bernoulli — the infinity symbol), `LemniscateOfGerono`,
`CassiniOval` (with the one-lobe/two-lobe transition handled explicitly),
`Limacon`, `Butterfly`, `FishCurve`, `BowCurve`, `Astroid`, `Deltoid`, `Nephroid`,
`Folium`, `Cochleoid`, `Cycloid`, `Trochoid`, `Witch`, `Cornoid`.

### 6.4 Roulettes & epicycles — `motifs/roulettes.py` (Phase 3b)

`Hypotrochoid`, `Epitrochoid`, `Hypocycloid`, `Epicycloid`, `Spirograph` (a friendly
wrapper taking ring/wheel/hole in the physical toy's terms), and

```python
@dataclass(frozen=True)
class Epicycles(ParametricMotif):
    """N stacked rotating arms: (radius, frequency, phase) each. Plot the tip."""
    arms: tuple[tuple[float, float, float], ...]
```

`Epicycles` alone covers the "orbit patterns" idea (planet → moon → moon-of-moon),
generalizes every roulette, and gives you a Fourier-series drawing engine for free.

### 6.5 Polar & harmonic — `motifs/polar.py` (Phase 3b)

`Rose` (`r = cos(kθ)`, with rational `k = n/d` handled correctly for the petal count),
`MaurerRose` (a rose sampled at integer degree steps and chorded — spectacular line
art), `Rhodonea` variants, `Lissajous`, `Harmonic` (sums of sines on x and y — the
`sin(3t)+0.4sin(17t)` idea), `Harmonograph` (with damping), `Phyllotaxis` /
`VogelSpiral` (the sunflower point set — the best pure dot-art motif in the whole
library), and `PolarExpression` for arbitrary user callables.

### 6.6 Guilloché — `motifs/guilloche.py` (Phase 3d)

`GuillocheRosette` (layered epitrochoids with phase offsets), `GuillocheBand`
(travelling sine bands along a spine), `GuillochePattern` (composed rosette + band, the
banknote look). Built on `Epicycles` + `offset_path` + `radial_repeat`.

### 6.7 Fractals — `motifs/fractals.py` (Phase 3c)

L-system based: `KochCurve`, `KochSnowflake`, `KochAntisnowflake`, `MinkowskiSausage`,
`SierpinskiTriangle`, `SierpinskiArrowhead`, `DragonCurve`, `TwinDragon`, `Terdragon`,
`LevyCCurve`, `HilbertCurve`, `MooreCurve`, `PeanoCurve`, `GosperCurve`,
`PythagorasTree`, `HTree`, `VicsekFractal`.

Recursive/geometric: `SierpinskiCarpet`, `CantorSet`, `ApollonianGasket`.

IFS point sets: `BarnsleyFern`, `IFSAttractor(maps, seed)` — dot art, seeded and
reproducible.

### 6.8 Graph & number art — `motifs/graphs.py` (Phase 3c)

`CompleteGraph(n)` (K₅…K₁₂), `ChordDiagram(n, edges)`,
`ModularMultiplication(n, factor)` (the times-table cardioid — connect `i → k·i mod n`),
`ModularAddition`, `PrimeChords(n)`, `CyclicGraph`, `BipartiteGraph`.

String art — `motifs/stringart.py`: `StringArtCorner` (two edges, parabolic envelope),
`StringArtPolygon`, `StringArtCircle` (produces cardioids/nephroids from chords),
`StringArtEnvelope(curve, rule)` — the general "connect point *i* on curve A to point
*f(i)* on curve B" engine that subsumes the rest.

### 6.9 Tilings — `motifs/tilings.py` (Phase 3d)

Periodic: `SquareTiling`, `TriangularTiling`, `HexagonalTiling`, `RhombilleTiling`,
`CairoPentagonal`, `TruncatedSquare` (octagon–square), `SnubSquare`, `HerringboneTiling`,
`TruchetTiling(seed)`.

Aperiodic: `PenroseP2` (kite & dart), `PenroseP3` (thin & thick rhombs),
`AmmannBeenker` — all via `SubstitutionTiling`.

### 6.10 Islamic geometric patterns — `motifs/girih.py` (Phase 3e)

`Rosette(points, layers)` (the 8- and 12-point rosettes), `GirihTiles` (the five
canonical tiles with their strapwork lines), `TenfoldGirih`, `InterlockingDecagons`,
`HexStarLattice`, `RosetteTiling`. Built from `LatticeTiling` + `radial_repeat` +
`offset_path`.

### 6.11 Sacred geometry — `motifs/sacred.py` (Phase 3d)

`VesicaPiscis`, `SeedOfLife`, `FlowerOfLife(rings)`, `FruitOfLife`, `MetatronsCube`,
`SriYantra`, `GoldenRectangle`. Mostly circle packings plus chord sets — cheap to
implement, extremely popular, great gallery images.

### 6.12 Mandalas & symmetry — `compose/mandala.py` (Phase 3d)

Not motifs so much as composers:

```python
Mandala(rings=[
    Ring(Petal(), count=12, radius=40),
    Ring(RegularPolygon(6), count=6, radius=80, rotate=math.pi / 6),
])
```

plus `Snowflake(motif, seed)` (6-fold + mirror, the dendritic/branching-crystal idea),
`Kaleidoscope(motif, group)`, `SpokePattern`, `LayeredRings`.

### 6.13 Celtic knots — `motifs/knots.py` (Phase 3e)

`Triquetra` (trinity knot — parametric, easy), `EndlessKnot`, `CircularCelticKnot`,
`SquareCelticKnot`, `CelticGrid(rows, cols, breaks)` — the standard grid+breakpoint
construction. Over/under weaving is rendered as **deliberate gaps in the under-strand**,
which is exactly what a `Design` of multiple paths expresses naturally, and which also
plots correctly on a pen plotter.

### 6.14 Polyhedral projections — `motifs/solids.py` (Phase 3e)

`Tetrahedron`, `Cube`, `Octahedron`, `Dodecahedron`, `Icosahedron`,
`TruncatedIcosahedron` (buckyball), plus `Polyhedron(vertices, edges)` for custom ones.
A tiny `Projection` helper (orthographic / isometric / perspective, with rotation) turns
3D vertex+edge tables into 2D `Design`s. Optional `SchlegelDiagram`.

### 6.15 Optical illusions & moiré — `motifs/illusions.py` (Phase 3e)

`PenroseTriangle`, `ImpossibleCube`, `NeckerCube`, `PenroseStairs`, `CafeWall`,
`MoirePattern(a, b, offset)` (two overlaid radiating/concentric families — falls out of
the transform layer almost for free).

### 6.16 Voronoi & Delaunay — `motifs/voronoi.py` (Phase 3f, `[scipy]` extra)

`Delaunay(points)`, `Voronoi(points, bounds)`, `LloydRelaxation(points, iterations)`.
Guarded import with a clear actionable error message, mirroring the existing
`plotting.py` pattern:

```python
raise ImportError(
    "geomotif.motifs.voronoi requires scipy. Install it with: pip install 'geomotif[scipy]'"
) from None
```

Registry entries for these are marked `requires="scipy"` so `list`/`gallery` can report
them as unavailable rather than exploding.

### 6.17 Constraint-based symmetric point sets — `motifs/symmetry.py` (Phase 6, stretch)

The most speculative item in `ideas.txt` and the one closest to your 15-point star
problem. Scope it deliberately small for v1:

`SymmetricPointSet(count, group)` — generate points under a cyclic `Cn` or dihedral
`Dn` group, with optional equal-distance constraints solved by a simple iterative
relaxation, then connect by a rule (`nearest_k`, `equal_distance`, `all_pairs`,
custom predicate). Ship it as clearly experimental, or defer entirely if Phase 6 slips.

---

## 7. Input/output

### 7.1 Point export — `io/points.py`

The existing `save_points()` survives essentially intact (CSV / TXT-TSV / JSON,
suffix inference, `precision=`). Additions:

- `save_design()` — the multi-path-aware version. JSON gains a structured mode
  (`{"paths": [{"points": [...], "closed": false}], "points": [...], "meta": {...}}`);
  CSV/TXT gain an optional `path` index column or blank-line stroke separator.
- `load_design()` — read the structured JSON back.
- `save_spec()` / `load_spec()` — serialize the *motif and its parameters* rather than
  the points. Tiny files, exact reproduction, and the basis of the gallery manifest.

### 7.2 SVG — `io/svg.py` (pure stdlib)

```python
def to_svg(design, *, width=None, height=None, padding=8.0, stroke="#0b0b0b",
           stroke_width=1.0, fill="none", background=None, dot_radius=None,
           flip_y=True, precision=3, group_by_path=True) -> str: ...
def save_svg(design, path, **kwargs) -> Path: ...
```

Notes: `flip_y=True` by default because SVG is a y-down space and users expect their
maths-convention design to appear right way up. Loose `Design.points` render as
`<circle>` elements when `dot_radius` is set — that is the dot-art path. Coordinates
are rounded to `precision` to keep files small. All text is escaped via
`xml.sax.saxutils.escape`.

### 7.3 DXF — `io/dxf.py` (pure stdlib)

A minimal ASCII **DXF R12** writer emitting `LWPOLYLINE`/`POLYLINE` and `POINT`
entities. R12 is a small, stable, exhaustively documented format and a hand-rolled
writer is ~120 lines — well within reach, and it preserves the zero-dependency core.
If it proves fiddly, the fallback is `ezdxf` behind a `[dxf]` extra; the writer's
interface is identical either way, so this is a swap, not a redesign.

### 7.4 Plotting — `plotting.py`

Generalized from spiral-specific to design-generic, keeping the existing (very nice)
light-mode palette and `_style_axes` styling:

- `plot_design(design, *, ax, title, color, show_paths, show_points, dot_size, ...)`
- `plot_grid(panels, *, ncols, panel_size, suptitle)` — the current
  `plot_spiral_grid`, renamed
- `plot_comparison(motif, spacings)` — one motif, several spacing curves side by side
  (the single best image for the README)

Optional dark-mode palette variable so gallery images match a dark docs theme.

---

## 8. CLI

Replaces the demo-only entry point. Pure `argparse` (stdlib — preserves zero-dep).

```
$ geomotif list                                  # every registered motif, grouped by family
$ geomotif list --family fractal
$ geomotif show rose                             # docstring, parameters, types, defaults
$ geomotif render rose --k 5 --points 400 --out rose.svg
$ geomotif render spiral.golden --turns 4 --points 300 --spacing power:2.5 --out s.csv
$ geomotif render hilbert --depth 6 --step 4 --out h.dxf --fit 800x800 --precision 0
$ geomotif render --spec my-design.json --out out.svg
$ geomotif gallery --out docs/gallery            # render every motif (docs build uses this)
$ geomotif demo                                  # the current showcase, preserved
```

Flags for each motif are generated from its dataclass fields (name → `--kebab-case`,
type → argparse `type=`, default → `default=`, docstring/`field(metadata=...)` → help
text). Output format is inferred from the `--out` suffix, exactly as `save_points`
already does. `--spacing` accepts a compact `name:arg` mini-syntax
(`linear`, `power:2.5`, `exp:out:6`, `smoothstep`).

Console script entry: `geomotif = "geomotif.cli:main"`, and `python -m geomotif` routes to the
same `main()`.

---

## 9. Migration phases

Each phase ends green: `make check` passes (ruff, ruff-format, mypy strict, pytest).

### Phase 0 — Groundwork (~½ day)

- `git init` if not already a repo (**it currently is not**), initial commit of the
  present state so the refactor is reviewable as a diff.
- Claim `geomotif` on GitHub, and optionally reserve it on PyPI with a `0.0.0`
  placeholder release (the name is already confirmed unregistered).
- Rename `src/spiralgen/` → `src/geomotif/`; update `pyproject.toml` (name, description,
  keywords, URLs, `[tool.hatch.version].path`, `[tool.ruff.lint.isort].known-first-party`,
  script entry `geomotif = "geomotif.cli:main"`), `Makefile` (`--cov=geomotif`, demo
  target), README, CHANGELOG, CI, the pre-commit config, and `examples/`.
- Apply the **`requires-python = ">=3.12"`** change and everything that follows from it
  — ruff `target-version = "py312"`, mypy `python_version = "3.12"`, the three
  classifiers, and the CI matrix `["3.12", "3.13", "3.14"]`. Exact diffs in §10.1. No
  source changes are required; run `make check` on 3.12 to confirm.
- Delete the stale `dist/spiralgen-0.1.0*` artifacts.
- Add `docs/` scaffolding and a `.gitignore` entry for generated gallery output.

### Phase 1 — Core model (~1–1½ days)

- `core/types.py` — `Point`, `Bounds`, `Path`, `Design`.
- `core/spacing.py` — moved `curves.py` + the small additions in §4.4.
- `core/sampling.py` — `ArcTable`, `densify`, `resample_path`, `resample`, lifted from
  `generator.py`.
- `core/motif.py` — `SupportsBuild` Protocol, `Motif` ABC, `Distribution` alias.
- `core/transform.py` — `Affine` + composite operators.
- `core/registry.py` — registration, lookup, `describe()`, entry-point discovery.
- Tests for each; the old `test_generator.py` arc-length assertions are re-pointed at
  `resample()` directly (they are good tests and should not be lost).
- **Delete `generator.py`.**

### Phase 2 — Motif bases (~1 day)

`bases/parametric.py` (`ParametricMotif`, `PolarMotif`, `MultiCurveMotif`),
`bases/lsystem.py` (grammar expansion + turtle, with `[`/`]` branching),
`bases/segments.py` (`SegmentMotif`), `bases/tiling.py` (`LatticeTiling`,
`SubstitutionTiling`).

Plus the **conformance test suite** (§12) — written *now*, before the motifs, so every
motif added from here on is tested the moment it is registered.

### Phase 3 — The motif library (~4–6 days, parallelizable)

| Sub-phase | Content | § |
|---|---|---|
| 3a | Spirals + primitives — **feature parity with today, plus basics** | 6.1, 6.2 |
| 3b | Named curves, roulettes/epicycles, polar & harmonic | 6.3–6.5 |
| 3c | Fractals, graph & number art, string art | 6.7, 6.8 |
| 3d | Tilings, sacred geometry, mandalas, guilloché | 6.6, 6.9, 6.11, 6.12 |
| 3e | Girih, Celtic knots, polyhedra, illusions | 6.10, 6.13–6.15 |
| 3f | Voronoi/Delaunay behind the `[scipy]` extra | 6.16 |

**3a is the checkpoint at which the library is already strictly better than
`spiralgen`.** Everything after is additive and can ship incrementally as 0.3, 0.4, …

### Phase 4 — I/O, CLI, plugins (~1½ days)

`io/points.py` (extended), `io/svg.py`, `io/dxf.py`, generalized `plotting.py`,
`cli.py`, entry-point discovery wired up, plus an `examples/plugin/` package
demonstrating a third-party motif end to end.

### Phase 5 — Docs, gallery, release (~1½ days)

- MkDocs Material + mkdocstrings; API reference generated from docstrings.
- **Auto-generated gallery**: a script iterates the registry, renders each motif to
  SVG at a sensible default, and emits a gallery page with the code snippet beside each
  image. CI regenerates it and fails if it drifts, so the docs can never go stale.
- Rewritten README with real images, a motifs table, and the "write your own motif in
  10 lines" section front and centre.
- `docs/extending.md` — the three tiers (polar → parametric → full `Motif`) and how to
  publish a plugin.
- GitHub Pages deploy workflow; PyPI publish workflow via **trusted publishing** (OIDC,
  no API token in secrets) on tag push.
- CHANGELOG entry documenting the rename and the new architecture.

### Phase 6 — Stretch

Constraint-based symmetric point sets (§6.17), numpy fast path (opt-in, same public
API), animation/GIF export, an interactive gallery with parameter sliders, `vpype`
integration for plotter post-processing, colour/layer support in `Design.meta`.

**Total for phases 0–5: roughly 10–13 focused days.** Phases 3b–3f are individually
optional for a first release.

---

## 10. Other considerations worth flagging

### 10.1 Python floor — **decided: `>=3.12`**

`requires-python = ">=3.14"` would give near-zero installs: 3.14 is brand new, most
people are on 3.11–3.13, and most CI images default lower. Nothing in the codebase
actually needs 3.14 — every modern-syntax feature in use is 3.12-safe:

| Feature | Available since | Used in |
|---|---|---|
| PEP 695 `type X = ...` aliases | 3.12 | `curves.py`, `generator.py`, `io.py`, `plotting.py` |
| `typing.override` | 3.12 | every subclass in `curves.py` |
| `match` statements | 3.10 | `generator.py`, `io.py`, `curves.py` |
| `dataclass(slots=True)` | 3.10 | new in this refactor |
| `itertools.pairwise` | 3.10 | `generator.py` |

So the floor drops to **3.12** with **zero code changes** — every flourish is kept and
the realistic user base is gained. (3.11 would additionally require replacing
`type X = ...` with `TypeAlias` and pulling `override` from `typing_extensions` — not
worth it; 3.12 is the sweet spot.)

Concretely, Phase 0 updates:

```toml
requires-python = ">=3.12"

classifiers = [
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
]

[tool.ruff]
target-version = "py312"

[tool.mypy]
python_version = "3.12"
```

and the CI matrix becomes `python-version: ["3.12", "3.13", "3.14"]` across all three
operating systems (9 test jobs). The lint job pins to 3.12 so ruff and mypy check
against the *floor*, not the ceiling — otherwise a 3.13-only idiom could slip in
unnoticed. A CI guard worth adding: run `ruff check --target-version py312` explicitly
so any accidental use of a newer-than-floor feature fails the build.

### 10.2 Determinism and seeding

Truchet tiles, jitter, IFS attractors, Poisson-disc sampling and Voronoi are
stochastic. Rules: every stochastic motif takes `seed: int | None = None`; each
instantiates its **own** `random.Random(seed)` and never touches the global RNG; the
resolved seed is written into `Design.meta` so any image can be reproduced exactly. A
conformance test asserts that the same seed yields identical output.

### 10.3 Numerical robustness

Named policies, documented and tested: division-by-zero guards on asymptotic spirals
(θ floor for hyperbolic/lituus); negative-radius convention for polar curves (reflect
vs. clip — pick reflect, document it); zero-length paths and coincident points (the
existing graceful degradation is the model to follow); floating-point closure tolerance
for `closed=True` paths; NaN/inf rejection at `Path` construction with a clear error.
The existing degenerate-center `match` block in `generate_spiral` is exactly the right
spirit — carry it forward.

### 10.4 Performance

Arc-length tables are O(n) to build and O(log n) to query; that is already fine. Where
it matters: the `densify` resolution should stay *adaptive* (the current
`_MIN_SAMPLES` / `_SAMPLES_PER_TURN` heuristic generalizes to "samples ∝ total
curvature/turns"), and `Design` operations should avoid quadratic path concatenation.
Add `pytest-benchmark` in the dev group with a couple of guard benchmarks (100k-point
resample, deep L-system) so a regression is visible. Reach for numpy only if a real
benchmark demands it, and then only as an opt-in fast path behind the same API.

### 10.5 Type-safety details

Keep mypy `strict` and the extra error codes. Specific care points: `Affine.__matmul__`
returning `Self`; `Mapping[str, object]` (not `dict`) for `meta` so `Design` stays
genuinely immutable; `@runtime_checkable` on `SupportsBuild`; the registry typed as
`dict[str, type[Motif]]` with `create()` returning `Motif`; generic `Sequence[Point]`
inputs but `tuple[Point, ...]` outputs everywhere.

### 10.6 API stability

Curate `__all__` in the top-level `__init__.py` — export the core model, the bases, the
spacing curves, the transforms, and the registry helpers, but **not** all ~140 motif
classes (import those from `geomotif.motifs.*`, or construct via the registry). A flat
namespace with 140 names is unusable and makes every rename a breaking change. Document
the public-vs-internal boundary in `docs/api-policy.md` and keep the underscore
convention for internals.

### 10.7 Repository hygiene

`git init` (currently not a repo). Add `CONTRIBUTING.md` (which base class to pick, how
to add a motif, the conformance-test contract), `SECURITY.md`, a `CODE_OF_CONDUCT.md`,
GitHub issue/PR templates, and Dependabot for Actions. Remove the stale `dist/` build
of `spiralgen-0.1.0` after the rename. Add repo topics on GitHub
(`generative-art`, `geometry`, `plotter-art`, `creative-coding`, `pen-plotter`) — that
is most of your discoverability.

### 10.8 Positioning and audience

The README should lead with images, then the three sentences that explain what makes
this different from every other "draw a spirograph" repo:

1. **Arc-length-exact point placement** with pluggable easing — you control not just
   the motif but the *distribution of points along it*.
2. **One extensible model** — every motif, builtin or third-party, gets resampling,
   transforms, composition, and export for free.
3. **Zero dependencies** in the core, with SVG/DXF output that goes straight to a pen
   plotter, a laser cutter, or any downstream tool.

Framed generically: generative art, plotter art, dot/line art, level and object
placement, particle layouts, motion paths, CAD/laser toolpaths.

### 10.9 Non-goals (state these explicitly)

Not a rendering engine (no fills, gradients, shading, or rasterization beyond the
matplotlib helper). Not a CAD kernel (no booleans, offsets beyond simple parallel
strokes, or constraint solving — §6.17 is a deliberate toe in that water). Not a
general vector-graphics I/O library (SVG/DXF *out*, not in). Not 3D — polyhedra are
projected to 2D and that is the extent of it.

---

## 11. Back-compat

Nothing has been published (the PyPI/GitHub URLs in `pyproject.toml` are still `TODO`
placeholders and `dist/` is a local build). So: **clean break, no shims.**

- The new package starts at **`0.1.0` under the new name** — a new project, not a
  continuation. `spiralgen` is never published.
- `CHANGELOG.md` opens with a note recording the lineage ("evolved from an
  unpublished spiral-only generator") so the history is honest without carrying dead
  code.
- `generate_spiral()` disappears. Its exact behaviour lives on as
  `SpiralBetween` / `ArchimedeanSpiral.between(start, end, center=..., turns=...,
  clockwise=...)`, and the README shows the before/after in a two-line snippet.

If you decide to publish `spiralgen` before this lands, revisit — that changes the
answer to a deprecation shim plus a `spiralgen` → `geomotif` redirect package.

---

## 12. Testing strategy

The current tests are good but motif-specific. The refactor's headline testing idea is
a **registry-driven conformance suite** that every motif passes automatically:

```python
@pytest.mark.parametrize("name", sorted(registry.names()))
def test_conformance(name: str) -> None:
    motif = registry.create(name)                # all-defaults instantiation
    design = motif.build()
    assert_all_coordinates_finite(design)
    assert_nonempty(design)
    assert_closed_paths_are_closed(design)
    for count in (2, 3, 50, 501):
        out = motif.generate(count)
        assert len(out) == count                 # exact, for single-path motifs
    assert_deterministic(motif)                  # same seed → identical output
    assert_bounds_sane(design)
    assert_svg_round_trips(design)
```

Adding a motif therefore costs zero test-writing effort and still gets meaningful
coverage. On top of that:

- **Property-based tests** (add `hypothesis` to the dev group) for the invariants that
  matter: arc-length resampling produces near-equal gaps for `LinearSpacing` (the
  existing `max/min < 1.05` assertion, generalized); every `SpacingCurve` is monotone
  with `f(0)=0`, `f(1)=1`; `Affine` composition is associative and
  `m @ m.inverse() == identity`; `resample` is idempotent at the same count.
- **Analytic golden values** for motifs with known closed forms: circle circumference
  `2πr`, `Rose(k)` petal counts (odd `k` → `k` petals, even `k` → `2k`), `Lissajous`
  self-intersection counts, `KochSnowflake` perimeter `3·(4/3)ⁿ`, `HilbertCurve` point
  count `4ⁿ`. These catch real maths errors that a smoke test never would.
- **Snapshot tests** for the SVG writer (small designs, exact string comparison) so
  output-format changes are always deliberate.
- **Doctests** on the README and the "write your own motif" examples via
  `--doctest-glob` / `--doctest-modules`, so the docs cannot rot.
- Keep the existing per-module unit tests for spacing curves and I/O; port them
  wholesale.
- Coverage gate in CI (start at 90%, ratchet up).

---

## 13. Preserving the codebase's character

Explicit checklist for the refactor, since this is the stated priority:

- [ ] PEP 695 `type` aliases (`type Point = ...`) — used for every alias, no `TypeAlias`
- [ ] `@override` on every overriding method — already consistent, keep it that way
- [ ] `match` statements where they genuinely read better than `if`/`elif`
- [ ] ABCs for behaviour + `Protocol` for structural typing, used deliberately, not
      interchangeably
- [ ] Frozen, slotted dataclasses for all value types and all motifs
- [ ] Keyword-only arguments past the two or three obvious positionals
- [ ] `TYPE_CHECKING`-guarded imports for typing-only symbols (ruff `TC` already
      enforces this)
- [ ] Curated `__all__` in every module
- [ ] NumPy-style docstrings with full Parameters/Returns blocks on every public symbol
- [ ] Comments that explain *why*, never *what* — the existing bar is high, hold it
- [ ] Errors are specific and actionable: `raise ValueError(f"... , got {value!r}")`,
      guarded imports with install instructions
- [ ] `py.typed`, mypy strict, zero `# type: ignore` without a code and a reason
- [ ] Ruff rule set kept as-is; add `D` (pydocstyle, numpy convention), `ARG`, `RSE`,
      and `A` now that the surface is larger
- [ ] Zero dependencies in the core; every optional feature behind an extra with a
      guarded import and a clear message
- [ ] Keep-a-Changelog + SemVer discipline maintained through the rename

---

## 14. Open questions

**Settled:**

- ✅ **Name** — `geomotif`, confirmed free on PyPI (§3).
- ✅ **Base class** — `Motif`, with `ParametricMotif` / `PolarMotif` / `LSystemMotif` /
  `SegmentMotif` / `TilingMotif` beneath it, plus the `SupportsBuild` structural
  protocol for users who prefer not to inherit (§4.2, §5).
- ✅ **Python floor** — `>=3.12`, matrix-tested on 3.12 / 3.13 / 3.14 (§10.1).
- ✅ **Core result type** — unified `Design` (§4.1).
- ✅ **Dependencies** — zero-dep core, extras for numpy/scipy/matplotlib.
- ✅ **Back-compat** — clean break, no `generate_spiral()` shim (§11).
- ✅ **Extra surfaces** — SVG/DXF, CLI, plugin registry, transform layer all in scope.

**Still open:**

1. **DXF** — hand-rolled R12 writer (zero-dep, ~120 lines) versus `ezdxf` behind an
   extra. Plan assumes hand-rolled, with `ezdxf` as the escape hatch.
2. **Scope of the first release.** Ship at the end of Phase 3a (spirals + primitives +
   the whole new architecture, already a complete and coherent library) and add motif
   families as minor releases? Or hold until 3f and launch with the full catalogue?
   Recommendation: **ship at 3a**, then release roughly weekly — a growing gallery is
   far better marketing than one big drop, and it de-risks the whole plan.
