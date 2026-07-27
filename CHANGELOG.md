# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`geomotif` evolved from an unpublished spiral-only point generator called
`spiralgen`. Nothing was ever released under that name, so there is no
migration path to document — the lineage is recorded here only so the early
history reads honestly.

## [1.0.0] — 2026-07-27

The first release, and the whole of the rework from `spiralgen` in one entry.

**Why 1.0.0 rather than 0.1.0.** The library is complete against what it set
out to be: the arc-length engine generalized from one curve to every polyline,
a data model, eight motif base classes, 146 motifs across 18 families, a
transform layer, five export formats plus a spec format, a command line,
third-party plugins, and a conformance suite that holds all of it — builtin and
third-party alike — to one contract. There is nothing here waiting to be
finished before the public API can be relied on, and pretending otherwise with
a leading zero would only make the version number less informative. What 1.0.0
promises is written down in
[the API policy](https://pianosuki.github.io/geomotif/api-policy/).

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
- **Islamic strapwork** (`geomotif.motifs.girih`) — `GirihTile` draws any of
  the five canonical tiles, generated from one table of interior angles since
  all five share a side and use only multiples of 36 degrees. `TenfoldGirih`
  lays decagons edge to edge on a rhombic lattice, where the gap between them
  turns out to be exactly a girih bowtie; `InterlockingDecagons` applies
  Hankin's rule to that tiling and the tiles disappear, leaving interlocked
  ten-pointed stars. The rule is implemented as simultaneous growth -- two
  lines stop only when their tips meet, and carry straight on where they
  merely cross -- because stopping at the first line met cuts the elongated
  hexagon's long straps down to stubs. Plus `Rosette`, `RosetteTiling` and
  `HexStarLattice`.
- **Celtic knots** (`geomotif.motifs.knots`) — `Triquetra` (three half-circles
  that join into one strand, which is to say a trefoil), `EndlessKnot`,
  `CircularCelticKnot`, `SquareCelticKnot` and `CelticGrid`, the plait with
  barriers that every knotwork panel is built from. Over-and-under is derived
  rather than declared: the crossings are found geometrically and two-coloured
  so that each strand alternates and each crossing disagrees with itself, and
  the under-strand is drawn with a gap in it, which is what a pen plotter can
  draw. The endless knot's corner joins nest at three corners and swap at the
  fourth -- nesting all four splits the figure into two separate rings, and
  the swap is what makes it endless.
- **Polyhedra** (`geomotif.motifs.solids`) — the five Platonic solids and
  `TruncatedIcosahedron`, plus `Polyhedron` for a shape of your own and
  `Projection` for orthographic, isometric or perspective views with yaw,
  pitch and roll. Every solid in the catalogue is a table of corners and one
  shared rule: join every pair as close together as any pair gets, which is
  the edge set of any solid whose corners are all alike. The tests check the
  tables against Euler's `V - E + F = 2`.
- **Optical illusions** (`geomotif.motifs.illusions`) — `PenroseTriangle`,
  `PenroseStairs`, `ImpossibleCube`, `NeckerCube`, `CafeWall` and
  `MoirePattern`. Both Penrose figures are built in space and then flattened
  rather than drawn flat and nudged into place: an isometric view sends
  `(t, t, t)` to nothing, so a walk that fails to close by exactly that much
  closes on the page. That is why the staircase's four flights cannot all be
  the same length, and the tests assert the closure error rather than the
  picture.
- **`examples/plugin/`** — a complete third-party motif as an installable
  package: Gielis's superformula, which geomotif's own catalogue does not
  have and does not need. One entry point and one `@register` decorator are
  the whole contract; once installed it is listed, described, rendered,
  spec'd and CLI-flagged exactly like a builtin, and geomotif never learns it
  exists. CI installs it and checks that end to end, since the suite can only
  simulate the discovery half. The motif documents a real wrinkle rather than
  hiding it: every corner is a corner in the radius too, so a sample has to
  land on one to reach it — `resolution` counts segments, so any multiple of
  `m` catches all `m` corners, and exponents below 1 make cusps that no
  resolution ever resolves.
- **The `geomotif` command line** (`geomotif.cli`) — `list`, `show`, `render`,
  `gallery` and `demo`, in pure `argparse`. A motif's flags are generated from
  its dataclass fields, which is what every builtin motif being a dataclass
  has been buying all along: one declaration drives `describe()`, the spec
  format and now the CLI. `--merge/--no-merge` for booleans, `choices` for a
  `Literal` parameter (resolved through a named type alias where there is
  one), and `--center 0,0` / `--region -60,-60,60,60` for the geometric ones.
  A parameter the command line cannot express — a function, another motif, a
  point set — takes its value from the motif's registered example, so every
  one of the 146 renders. `geomotif gallery` writes all of them to SVG with a
  manifest whose entries are specs, in about two seconds.
- **`plot_design`, `plot_grid`, `plot_comparison`** (`geomotif.plotting`) —
  the plotting helpers, generalized from spirals to designs. `plot_design`
  draws each stroke as a line, closing the closed ones, and always draws the
  loose points, since a scatter motif has nothing else to show; stroke
  *vertices* are opt-in, because a four-thousand-vertex fractal with markers
  is a smear. `plot_comparison` is the library's premise in one image: one
  motif, one point count, several spacing curves. Colours moved into a
  `Palette` value with `LIGHT` and `DARK`, so a dark-mode figure is a
  different argument rather than a different code path.
- **SVG** (`geomotif.io.svg`) — `to_svg` and `save_svg`, pure standard
  library. The design is fitted into the canvas before anything is written
  rather than scaled by a `viewBox`, so `stroke_width` means one unit of the
  file you are looking at and rounding to `precision` shrinks the file
  instead of discarding detail a later scale would magnify. `flip_y` defaults
  on, because SVG's y grows downward and every motif here is written the other
  way up. Loose points become `<circle>` elements, the motif's name becomes
  the document `<title>`, and every attribute is escaped — a colour and a
  title both come from outside.
- **DXF** (`geomotif.io.dxf`) — `to_dxf` and `save_dxf`, writing DXF R12,
  also pure standard library. `POLYLINE`/`VERTEX`/`SEQEND` rather than
  `LWPOLYLINE`, which arrived with R14 and would give up the compatibility R12
  was chosen for. A closed path carries the closed flag instead of a repeated
  final vertex, a named layer is declared in the file's layer table rather
  than left for the reader to invent, and the header records the drawing
  extents. DXF is y-up like the motifs themselves, so nothing is mirrored.
  The output was checked against `ezdxf` and the SVG against `svgelements`;
  neither is a dependency, and the suite's own readers are stdlib-only.
- **Specs** (`geomotif.io.spec`) — `to_spec`, `from_spec`, `save_spec` and
  `load_spec` serialize the *motif and its parameters* rather than the points
  they produced. A mandala's recipe is 1.5 KB against 330 KB of coordinates,
  it survives a change of point count, and it is a file you can edit by hand.
  A parameter that is itself a motif — the composers take one — nests as the
  same `{"motif": ..., "params": ...}` object, so a spec needs no second
  notation to describe a mandala's rings; a value dataclass such as `Bounds`
  becomes a `{"$type": ...}` object naming its class. All 146 motifs
  round-trip exactly bar the two whose parameter *is* a Python function,
  which are defined by code rather than data and refuse by name. Loading a
  spec will not import a module the file names, only value types from
  packages that already provide motifs — a spec is data, and data does not
  get to choose what a process imports.
- **`save_design` / `load_design`** (`geomotif.io.points`) — the multi-path
  writer, for when the strokes matter and not only the coordinates: CSV grows
  a `path` column naming the stroke each point belongs to (empty for a design's
  loose points, which belong to none), TXT separates strokes with the blank
  line every plotter toolchain already reads as "lift the pen", and JSON keeps
  the whole structure including the recipe. `save_points` is unchanged and
  still flattens — the two now differ by exactly one thing.
- **Voronoi & Delaunay** (`geomotif.motifs.voronoi`, `[scipy]` extra) —
  `Delaunay`, `Voronoi` (the diagram as borders, each drawn once, chainable
  with `merge=True`), `VoronoiCells` (the same map as closed regions, with an
  `inset` for the cracked-mud look) and `LloydRelaxation`. All four come from
  one construction: a site's cell is the region clipped by the perpendicular
  bisector against each of its *Delaunay neighbours*, and no other bisector
  reaches it — which is why one triangulation answers every question the
  module asks. The tests check that the cells' areas sum to the region's,
  which fails if a bisector is missed or one that does not belong is used.
  scipy earns its place on the cocircular case: a plain square grid gives
  Qhull an arbitrary choice of diagonal, and a hand-rolled triangulator that
  makes that choice inconsistently contradicts itself.
- **`requires=` is now honoured** (`geomotif.core.registry`) — `MotifInfo`
  gained an `available` property, and the motifs behind an extra import their
  dependency when a design is *built* rather than when their module is
  imported. A machine without scipy can still list, describe and document the
  Voronoi family; only building one raises, with the install command in the
  message. CI gained a job that installs the core with no optional
  dependencies at all and runs the suite, so the zero-dependency promise is
  checked rather than asserted.
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
- **A documentation site** — MkDocs Material with an API reference generated
  from the docstrings by mkdocstrings, guides to the arc-length engine, the
  data model, the five export formats, plotting and the command line, plus
  `docs/extending.md` (the three tiers, the conformance contract, publishing a
  plugin) and `docs/api-policy.md`, which writes down what the version number
  is a promise about.
- **A generated gallery** — every registered motif rendered to SVG at its
  registered example, beside the Python, the command line and the spec that
  reproduce exactly that file. `tools/gendocs.py` writes it, along with the
  reference pages and `docs/catalogue.md`, and doubles as the mkdocs `hooks:`
  entry so a build is never a step behind the registry. The gallery and the
  reference are rebuilt every time and never committed; the catalogue and the
  six images the README leads with are committed, because GitHub renders a
  README without running mkdocs — and are therefore drift-checked by
  `make docs-check`, by CI, and by `tests/test_gendocs.py`.
- **The README's numbers are tested.** `tests/test_readme.py` parses the family
  table and checks every count against the registry, that the table covers each
  family exactly once, and that the totals and the spec example's version are
  the real ones. The count was wrong within an hour of being written, which is
  the argument for the test.
- **Release automation** — a Pages workflow that rebuilds and deploys the site
  on every push to main, and a PyPI workflow that publishes on a `v*` tag
  through trusted publishing, with no API token in the repository. It refuses
  to build when the tag and `__version__` disagree.
- **Repository documentation** — `CONTRIBUTING.md` (how to add a motif, and the
  house style that until now only existed in the code), `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, issue and pull-request templates, and Dependabot on the
  Actions.

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

- `describe().params` now lists a motif's own parameters before the ones it
  inherits. `dataclasses.fields()` gives the opposite order because that is
  what the generated `__init__` needs, but it is the wrong order to read:
  `describe("rose").params` used to open with `resolution` and
  `describe("tiling.square").params` with `region`, burying the parameter the
  motif is actually about. `geomotif show rose` now leads with `--n`.
  Construction is unaffected.
- The console script is now `geomotif`, and the showcase moved under it as
  `geomotif demo`; `python -m geomotif` routes to the same command line.
  `geomotif-demo` is gone.
- `plot_spiral` and `plot_spiral_grid` became `plot_design` and `plot_grid`,
  taking a `Design` rather than a list of points -- which is what lets them
  draw a closed path closed and a scatter motif at all.
- `geomotif.io` is now a package rather than a module, split into
  `io.points` (coordinates and designs) and `io.spec` (recipes). Everything
  it exported is re-exported unchanged, so `from geomotif import save_points`
  and `from geomotif.io import save_points` both still work.
- `registry.spec()` accepts anything with `build()` rather than only a
  `Motif` subclass, matching the rest of the library's structural stance.
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

## 0.1.0 — never released, as `spiralgen`

Recorded so the early history reads honestly. Nothing was ever published under
this name or number; `geomotif` 1.0.0 is the first release of anything.

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

[1.0.0]: https://github.com/pianosuki/geomotif/releases/tag/v1.0.0
