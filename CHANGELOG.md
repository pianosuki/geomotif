# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`geomotif` evolved from an unpublished spiral-only point generator called
`spiralgen`. Nothing was ever released under that name, so there is no
migration path to document — the lineage is recorded here only so the early
history reads honestly.

## [Unreleased]

### Added

- **`Design`, `Path`, `Bounds`** (`geomotif.core.types`) — the universal
  result type: stroked polylines plus loose points plus reproducibility
  metadata. Immutable throughout, with `+` for overlay, `fit()` for canvas
  normalization and `flipped_y()` for y-down coordinate spaces. NaN and
  infinity are rejected at construction rather than propagating silently
  into exported output.
- **`Motif` / `SupportsBuild`** (`geomotif.core.motif`) — the extension
  contract. Implement `build()` and inherit `generate()`, which resamples to
  a point count or a fixed step distance. Inheritance is optional: anything
  with a `build() -> Design` method is accepted everywhere a motif is.
- **Arc-length engine** (`geomotif.core.sampling`) — `ArcTable`, `densify`,
  `resample_path` and `resample`, generalized from the old spiral generator
  to work on *any* polyline. Every motif therefore gets arc-length placement
  and the whole spacing-curve family for free, including motifs with no
  closed-form parametrization. Adds fixed-`step` placement for plotter
  output, `by="parameter"` for the old parametric behaviour, and
  `distribute=` to spread a point budget across a multi-path design.
- **Transform layer** (`geomotif.core.transform`) — `Affine` (composable
  with `@`, invertible) plus the composite operators `radial_repeat`,
  `tile`, `mirror_axis`, `symmetry_group`, `jitter`, `layer`, `fit_to`,
  `clip_to` and `offset_path`.
- **Registry** (`geomotif.core.registry`) — `register`, `names`, `families`,
  `get`, `create` and `describe`, with parameter introspection derived from
  dataclass fields and lazy third-party discovery via the
  `geomotif.motifs` entry-point group.
- **Motif base classes** (`geomotif.bases`) — the extensibility story, and
  most of the catalogue's implementation. Pick the base that matches how your
  design is defined and write the one method it asks for:
  `ParametricMotif` (`position(u)`), `PolarMotif` (`radius(theta)`),
  `MultiCurveMotif` (several strands at once), `LSystemMotif` (an axiom,
  rewrite rules and a turn angle, drawn with a turtle that branches),
  `SegmentMotif` (nodes and edges, optionally chained into polylines) and the
  two tiling bases, `LatticeTiling` (a cell repeated on basis vectors and
  clipped to a region) and `SubstitutionTiling` (seed tiles subdivided to a
  depth, generic over your own tile type).
- **`PolygonMotif`** (`geomotif.bases`) — the base for shapes defined by
  their corners rather than by a formula. Kept separate from
  `ParametricMotif` because sampling a polygon at evenly spaced parameters
  rounds its corners off unless a sample happens to land on each one; a
  pentagon here costs five points rather than five hundred. `outlines()` is
  plural so that a figure made of several loops — the star polygon `{6/2}` is
  two overlaid triangles — comes back as several strokes rather than one
  path with an invented edge between them.
- **`PolarMotif.with_turns()`** — the sweep said in revolutions rather than
  radians, which is how a wound curve is actually described:
  `LogarithmicSpiral(b=0.2).with_turns(5, clockwise=True)`.
- **The spiral family** (`geomotif.motifs.spirals`) — `ArchimedeanSpiral`,
  `LogarithmicSpiral`, `GoldenSpiral`, `FibonacciSpiral`, `FermatSpiral`,
  `HyperbolicSpiral`, `Lituus`, `TheodorusSpiral`, `EulerSpiral`,
  `CircleInvolute`, joining `SpiralBetween`. The six that are polar functions
  of theta share a `SpiralBase` and are a single line of maths each; the
  other four are not polar functions at all and say so by using a different
  base. `EulerSpiral` brings a dependency-free Fresnel integral, evaluated by
  power series to machine precision within the range the curve is actually
  drawn over.
- **The primitives** (`geomotif.motifs.primitives`) — `Circle`, `Ellipse`,
  `Arc`, `Sector`, `Line`, `Rectangle`, `RoundedRectangle`,
  `RegularPolygon`, `StarPolygon`, `Star`, `Superellipse`, `Squircle`,
  `ReuleauxPolygon`, `Egg`, `PointGrid` and `PoissonDiscPoints`. The point
  fields seed a private `random.Random`, so a design is reproducible from its
  metadata and building one never disturbs the global random stream.
- **The named curves** (`geomotif.motifs.curves`) — `Heart` (the valentine
  and the cardioid form), `Cardioid`, `Lemniscate`, `LemniscateOfGerono`,
  `CassiniOval`, `Limacon`, `Butterfly`, `FishCurve`, `BowCurve`, `Astroid`,
  `Deltoid`, `Nephroid`, `Folium`, `Cochleoid`, `Cycloid`, `Trochoid`,
  `Witch` and `Cornoid`. Two conventions hold across the module: `size` is
  the curve's largest extent, so curves composed at the same `size` come out
  the same size, and `center` is the curve's own origin — a cardioid's cusp,
  a lemniscate's crossing point — rather than the middle of its bounding
  box. `CassiniOval` handles its topology change explicitly: below the focal
  separation it returns two strokes, one per lobe, and it refuses the
  degenerate case in favour of `Lemniscate`, which draws it in one.
- **The roulettes** (`geomotif.motifs.roulettes`) — `Hypotrochoid`,
  `Epitrochoid`, `Hypocycloid`, `Epicycloid`, `Spirograph` (ring teeth,
  wheel teeth and which hole the pen goes in) and `Epicycles`, which stacks
  any number of `(radius, frequency, phase)` arms and plots the tip. Two
  arms give every trochoid, several dozen give a Fourier series. The ring
  and wheel radii are whole numbers because the ratio has to be rational for
  the curve to close at all; the classes work out how many revolutions that
  takes rather than making you say.
- **Roses, harmonics and the sunflower** (`geomotif.motifs.polar`) — `Rose`
  with the petal count actually right (`n` petals when `n*d` is odd and
  `2*n` when it is even, swept exactly to closure so no petal is traced
  twice), `MaurerRose`, `Lissajous`, `Harmonic`, `Harmonograph` with its
  `Pendulum` value type, `Phyllotaxis` / `VogelSpiral`, and
  `PolarExpression` for a radius function that does not deserve a class.
  `GOLDEN_ANGLE` is exported alongside them.
- **The fractals** (`geomotif.motifs.fractals`) — reached three ways, because
  the difference is worth seeing. Sixteen are an axiom, a rewrite rule and a
  turn angle drawn with a turtle: `KochCurve`, `KochSnowflake`,
  `KochAntisnowflake`, `MinkowskiSausage`, `MinkowskiIsland`,
  `SierpinskiTriangle`, `SierpinskiArrowhead`, `DragonCurve`, `TwinDragon`,
  `Terdragon`, `LevyCCurve`, `HilbertCurve`, `MooreCurve`, `PeanoCurve`,
  `GosperCurve` and `VicsekFractal`. Five place smaller copies of themselves
  rather than walk a path, which is a statement about squares and circles
  instead of about a stroke, so they are built directly: `SierpinskiCarpet`,
  `CantorSet`, `PythagorasTree` (Bosman's squares, whose children's areas add
  up to their parent's at every lean — the theorem, drawn), `HTree` and
  `ApollonianGasket`, generated through Descartes' circle theorem so the
  curvatures of the default packing come out integral. Two arrive by chaos
  game as loose points: `IFSAttractor`, with its `IFSMap` value type, and
  `BarnsleyFern`. Both seed a private generator and normalize their cloud to
  the `size` asked for, since an attractor's own coordinates are an artefact
  of whichever numbers the maps happen to contain.
- **Graph and number art** (`geomotif.motifs.graphs`) — `CompleteGraph`,
  `CyclicGraph` (the circulant, so several step sizes overlay into a rosette),
  `BipartiteGraph`, `ChordDiagram` for connections that come from data rather
  than from arithmetic, `ModularMultiplication` — the times table drawn as
  chords, whose envelope is a cardioid for the two times table and an
  epicycloid with one fewer cusp than the factor after that — plus
  `ModularAddition` and `PrimeChords`, which joins two numbers whenever they
  add up to a prime.
- **String art** (`geomotif.motifs.stringart`) — straight threads whose
  envelope is a curve. `StringArtCorner` (two arms and the parabola between
  them), `StringArtPolygon` (that corner at every corner of a polygon) and
  `StringArtEnvelope`, the general "nail `i` on one curve to nail `rule(i)` on
  another" engine that the rest of the module and the whole of `graphs` are
  special cases of. `StringArtCircle` is an alias for
  `ModularMultiplication`: circle string art and the times table are the same
  construction, so it is one class under two names rather than two classes
  drawing one picture.
- **Tilings** (`geomotif.motifs.tilings`) — eight periodic ones stamped on a
  lattice (`SquareTiling`, `TriangularTiling`, `HexagonalTiling`,
  `RhombilleTiling`, `CairoPentagonal`, `TruncatedSquare`, `SnubSquare` and
  `HerringboneTiling`, which works at any brick proportion rather than only
  two-to-one), the two aperiodic Penrose tilings, and `AmmannBeenker`.
  `PenroseP3` and `PenroseP2` are built from the same two Robinson triangles
  and differ only in where the seam runs: along the base gives the thin and
  thick rhombs, along a leg gives the kite and the dart. `AmmannBeenker` is a
  plain `Motif` rather than a substitution, built by de Bruijn's multigrid —
  four families of parallel lines laid across each other, one tile per
  crossing — because the line arrangement is checkable directly where the
  eightfold inflation rule is only checkable by eye. `TruchetTiling` places
  its own cells, since one cell stamped everywhere is exactly what a random
  tiling is not.
- **Sacred geometry** (`geomotif.motifs.sacred`) — `VesicaPiscis`,
  `SeedOfLife`, `FlowerOfLife`, `FruitOfLife` and `MetatronsCube`, which are
  one construction carried five steps further each time, plus `SriYantra` and
  `GoldenRectangle`.
- **Guilloché** (`geomotif.motifs.guilloche`) — `GuillocheRosette`,
  `GuillocheBand` and `GuillochePattern`, the engine-turned line work of
  banknotes and watch dials. Each stroke is the sum of two waves running
  opposite ways, which is what makes a phase shift change a curve's shape
  instead of sliding it sideways.
- **Composers** (`geomotif.compose`) — motifs made of other motifs:
  `Mandala` and its `Ring`, `Kaleidoscope`, `Snowflake`, `SpokePattern` and
  `LayeredRings`. Their unit is anything with a `build()` method, so a
  composed figure can itself be the unit of another composition. The
  parameter is called `unit` rather than `motif` because `motif` is the key
  `spec()` reserves for a design's own name.
- **`registry.NAME_KEY`** and a guard that goes with it: registering a motif
  with a parameter called `motif` now raises, instead of silently
  overwriting the design's own name in `Design.meta` and leaving a spec that
  cannot be rebuilt.
- **`registry.spec()`** — a motif's registered name plus its resolved
  parameters, which is what the bases attach to every design they build. A
  design can therefore say what made it, and be rebuilt from that.
- **`@register(example=...)`** — constructor arguments producing a
  representative instance. The gallery will render it; the conformance suite
  exercises it today, and requires one from any motif whose parameters have
  no defaults.
- **Registry-driven conformance suite** — one contract, checked against every
  registered motif automatically: it builds, it is finite, it has extent, it
  resamples to exactly the count asked for, it is reproducible, its metadata
  round-trips back through the registry, it exports, and it is documented.
  Adding a motif from here on costs no test-writing effort.
- **Spacing curves** — `ReversedSpacing` (mirror any curve, including plain
  callables), `CompositeSpacing` (chain eases), `TableSpacing` (draw the
  curve by hand from control points), and `coerce_spacing`, one place that
  decides what counts as a spacing curve.
- **`SpiralBetween`** (`geomotif.motifs.spirals`) — the endpoint-constrained
  arithmetic spiral, preserving the old generator's exact geometry. Also
  reachable as `ArchimedeanSpiral.between(...)`, since it is that same curve
  parameterized by where it has to start and stop.

### Removed

- `generate_spiral()` and the `geomotif.generator` module. Its behaviour
  lives on as `SpiralBetween(start, end, center=..., turns=...,
  clockwise=...).generate(count, spacing=...)`.
- The `y_down` flag. Which way y points is a property of the target
  coordinate space, not of a motif, so it is now `Design.flipped_y()` or
  `fit(..., flip_y=True)` — strictly more general, and it applies to every
  motif rather than to one.
- `geomotif.curves`, renamed to `geomotif.core.spacing`. This frees the name
  `curves` for the named-curve motif family, where a reader will look for it.

### Changed

- Renamed the package `spiralgen` → `geomotif`, ahead of the rework from a
  single-purpose spiral generator into a general geometric design library.
  Import name, source tree, distribution name and console script all move
  together; the demo command is now `geomotif-demo`.
- `Motif` declares empty `__slots__`, so `@dataclass(frozen=True,
  slots=True)` on a motif now actually takes effect. A single class without
  slots anywhere in the MRO silently hands every instance a `__dict__` back.
- Ruff gains `D` (pydocstyle, numpy convention), `ARG`, `RSE` and `A`, as
  planned for the point where the public surface grew.
- Lowered the Python floor from 3.14 to **3.12**, now tested on 3.12, 3.13
  and 3.14 across Linux, macOS and Windows. Every modern-syntax flourish in
  the codebase (PEP 695 `type` aliases, `@override`, `match`) is 3.12-safe,
  so nothing was given up to gain the far larger installed base.

### Fixed

- Modules with `TYPE_CHECKING`-guarded imports now carry
  `from __future__ import annotations`. Those guards were only safe under
  3.14's deferred annotation evaluation (PEP 649); on 3.12 and 3.13,
  importing the package raised `NameError` at module load.
- Registry lookups now import the builtin motif catalogue themselves.
  Previously `names()` reported only the motifs whose modules the caller had
  already imported, so a fresh interpreter saw an empty registry.

## [0.1.0] — unreleased

### Added

- `generate_spiral()` — points along an arbitrary spiral between a start and
  end point around a configurable center (default origin), with direction,
  extra turns, pluggable spacing, and a `y_down` flag for screen-style
  coordinate systems.
- `save_points()` — export coordinates to CSV, TXT/TSV, or JSON with
  optional rounding.
- True arc-length positioning (default): equal spacing means equal real x,y
  distance between consecutive points; `arc_length=False` for parametric
  spacing.
- Spacing curve family: `LinearSpacing`, `PowerSpacing`, `QuadraticSpacing`,
  `CubicSpacing`, `SineSpacing`, `ExponentialSpacing`, `CircularSpacing`,
  `SmoothstepSpacing`, all built on the `SpacingCurve` ABC.
- Optional matplotlib helpers (`geomotif.plotting`) behind the `plot` extra.
- `geomotif-demo` console command / `python -m geomotif` showcase.
