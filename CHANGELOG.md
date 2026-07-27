# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`geomotif` evolved from an unpublished spiral-only point generator called
`spiralgen`. Nothing was ever released under that name, so there is no
migration path to document — the lineage is recorded here only so the early
history reads honestly.

## [Unreleased]

### Changed

- Renamed the package `spiralgen` → `geomotif`, ahead of the rework from a
  single-purpose spiral generator into a general geometric design library.
  Import name, source tree, distribution name and console script all move
  together; the demo command is now `geomotif-demo`.
- Lowered the Python floor from 3.14 to **3.12**, now tested on 3.12, 3.13
  and 3.14 across Linux, macOS and Windows. Every modern-syntax flourish in
  the codebase (PEP 695 `type` aliases, `@override`, `match`) is 3.12-safe,
  so nothing was given up to gain the far larger installed base.

### Fixed

- `geomotif.generator` and `geomotif.io` now carry
  `from __future__ import annotations`. Their `TYPE_CHECKING`-guarded imports
  were only safe under 3.14's deferred annotation evaluation (PEP 649); on
  3.12 and 3.13, importing the package raised `NameError` at module load.

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
