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
  arithmetic spiral, preserving the old generator's exact geometry.

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
