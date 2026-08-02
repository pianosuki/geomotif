# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The first piece of the 1.3.0 explore overhaul: parameter ranges move from
guessed to declared. A motif can now say how far a slider should reach, and
every consumer of `ParamInfo` reads the bound from the same place.

### Added

- **`catalog.json`, the registry serialized for the web explorer.**
  `tools/gendocs.py` now emits `docs/assets/explore/catalog.json` alongside
  `catalog.md`: every registered motif's name, family, summary, full doc,
  availability, registered example, and parameters — including the `Range`
  bounds and the `Literal` choices a dropdown would offer. The web explorer
  (landing in 1.3.0) reads this once at load time and builds its controls
  from it, so the page needs no server and no Python. Committed like
  `catalog.md`, with a matching freshness test in `test_gendocs.py` and a
  `make explore-catalog` target; the existing `make docs-check` catches
  drift because it already watches `docs/assets`.

- **`Range`, a min/max/step helper for motif parameters.** A new
  `geomotif.core.range.Range` maps cleanly onto `dataclasses.field`'s
  `metadata=` argument (the same route `help` text already takes), so a
  parameter declares its bound next to its default in one line:
  `n: int = field(default=5, metadata=Range(1, 50, step=1))`. `Range` is a
  frozen `Mapping`, so the keys are additive — a field that carries one
  carries both `help` and `Range`, and a parameter without a `Range` still
  falls back to the heuristic. Exported from `geomotif` and
  `geomotif.core`.
- **`ParamInfo.min`, `.max`, `.step`.** `registry.describe()` now reports
  the declared range alongside the default and the help text, so the CLI,
  the docs, the gallery and the web explorer all read the same bound. The
  three are `None` when a motif has not declared a bound, in which case a
  consumer falls back to its own heuristic rather than guessing zero.
- **Curated ranges for the most-used motifs.** The polar, harmonic, spiral,
  fractal, curve and primitive families now declare `Range` on every
  numeric parameter a slider can move — petal counts, depths, scales,
  radii, side counts and point counts. Motifs without a natural bound keep
  the heuristic, so the catalog is usable even before every motif is
  curated.

- **`keyframes`, a multi-parameter animation primitive in `geomotif.animate`.**
  Where `sweep` varies one parameter across a list of values, `keyframes`
  varies several at once, each across its own time points in `[0, 1]`:
  `keyframes(Rose(), {"n": [(0.0, 3), (1.0, 9)]}, frames=48)`. Numeric
  parameters interpolate component-wise with an easing curve from
  `geomotif.core.spacing` (`linear`, `quadratic`, `cubic`, `sinusoidal`,
  `exponential`, `circular`, with a `name:mode` suffix for ease-out variants);
  `bool`, `Literal` and `str` parameters step at the next keyframe; integer
  parameters round and deduplicate, so adjacent frames that round to the same
  value share one built `Design`. Per-track easing overrides the global one.
  An eased value a motif rejects falls back to the last frame that built, with
  a `keyframes_fallback` note in its metadata. A small `compose(motions,
  frames)` helper chains `draw_on_overlay` / `spin_overlay` post-passes onto a
  run of frames, so a Hilbert curve can draw itself on while its `depth`
  sweeps. This is the primitive the 1.3.0 web explorer's animation editor is
  built on, so an animation shared from the browser reproduces in the CLI
  byte-for-byte.
- **`animation` key in spec files.** `io/spec.py` learns an optional top-level
  `animation` key carrying the recipe for a moving picture: `{"type":
  "keyframes", "tracks": {...}, "frames": N, "fps": X, "hold": K, "easing":
  "...", "overlay": [...]}` -- the same JSON the CLI's `--animation` flag reads
  and the web explorer encodes into a share URL. `to_spec` takes an optional
  `animation=` mapping; `from_spec` ignores the key when building the still
  motif, so an old spec keeps loading unchanged.
- **`geomotif render --animation spec.json`.** The new flag reads a full spec
  (motif + params + `animation`), runs the `keyframes` primitive, applies any
  `overlay` post-passes, and writes a `.gif` through the existing pure-stdlib
  writer. The recipe's `fps` is authoritative, so a shared animation plays at
  the same speed on the command line as in the browser. Mutually exclusive
  with a positional motif name and `--spec`.

### Changed

- **`geomotif explore` sweeps a declared range when there is one.** A
  parameter with a `Range` is now sampled across that range (in whole steps
  for an integer with a `step`, linearly for a float) rather than around its
  default with the `_SPREAD` heuristic. The heuristic stays as the fallback
  for parameters without a declared range, so pages that worked before keep
  working.

## [1.2.2] — 2026-08-02

The documentation release: a pass over the guides against the code, fixing
what was wrong and what read wrong. No behavior changes; the library is
unchanged.

### Fixed

- **The 'centerd' typo.** The American-spelling test catches the British
  forms it bans but not the plain misspelling 'centerd', which had settled
  into five module docstrings and four test names. All ten now read
  'centered'.
- **Reproducibility, restated.** The 'Metadata and reproducibility' section
  claimed any random seed lands in `meta`; only a motif-parameter seed does
  (the way `PoissonDiscPoints.seed` is). An operator's seed -- `jitter`'s --
  is not recorded, so regenerating the same jittered points means keeping
  hold of it yourself.
- **The CLI guide's `--ease` example.** `--ease power:exp:out:6` does not
  parse; `--ease exponential:out:6` does, and is what the example now says.
- **The exporter guide's quick reference** is a table first, with the longer
  notes below it. The front page lists PNG and JPEG among the exports, the
  extending guide reaches for `ParametricMotif` or `PolygonMotif` first,
  and both now say 'ten formats' rather than five.
- **The animation guide's Raster note** names the fields (`width`, `height`,
  `pixels`, `palette`, `mode`) and points at `rasterize_rgba` for the
  truecolor writers, rather than the `rgba()` method the code does not have.
- The points guide gets a concrete `RegularPolygon(sides=5)` example, the
  plotting guide recommends `save_png` as the no-matplotlib still, and the
  front-page example shows `SpiralBetween` with keyword arguments, matching
  the README.

## [1.2.1] — 2026-08-02

The JPEG interop fix: the stills the encoder writes now render identically in
libjpeg and Pillow, closing the gap the 1.2.0 entry warned about.

### Fixed

- **JPEG AC coefficients were written in the wrong zig-zag order.** The
  `_ZIGZAG` table held ITU-T T.81 Annex A's standard mapping (scan position →
  row-major index), but both the encoder (`jpeg.py`) and the suite's decoder
  (`tests/readback.py`) looked it up backwards (row-major index → scan
  position). Because both sides shared the mistake, the round-trip passed
  while external decoders placed every AC coefficient in the wrong frequency.
  The table is now stored inverted, matching what both call sites actually
  need.
- **JPEG quantization tables were written in natural rather than scan
  order.** The DQT payload must list its 64 steps in zig-zag scan order
  (Annex A), but `_dqt_table` emitted them row-major and `_parse_quant` read
  them back the same way. External decoders therefore dequantized with the
  step for the wrong frequency. Both now use scan order, so files are
  standard and the interop check in verification 2 passes.
- The "honest caveat" paragraph is gone from the `geomotif.io.jpeg` module
  docstring, and the export guide's "A word about JPEG" note no longer steers
  readers away to PNG/GIF for exactness. A JPEG opened in another tool now
  matches what the suite's own reader produces, to within IDCT rounding.

## [1.2.0] — 2026-08-01

The raster overhaul: stills join the zero-dependency picture pipeline, and
the one hard-coded GIF becomes a full set of knobs.

### Added

- **PNG stills, pure standard library** (`geomotif.io.png` — `save_png`,
  `to_png`) — a design renders once, antialiased or hard-edged, into a
  full-color frame and is encoded with `zlib` and per-chunk CRCs. Truecolor
  RGB by default, RGBA on request, or indexed through the same median-cut
  quantizer the GIF uses; `--compression 0-9` tunes the deflate level. Renders
  from `render --out rose.png` with no matplotlib and no extra install.
- **JPEG stills, pure standard library** (`geomotif.io.jpeg` — `save_jpeg`,
  `to_jpeg`) — the same RGBA frame encoded as baseline JPEG: RGB to YCbCr
  with 4:2:0 chroma subsampling, an 8x8 DCT, quality-scaled quantization, and
  Huffman coding against the reference tables. `--quality 0-100` scales the
  quantization (default 85). `.jpg` and `.jpeg` render from `render --out`
  with no matplotlib and no extra install. As of 1.2.1 the files it writes
  render identically in libjpeg and Pillow (see the `[1.2.1]` entry).
- **Stills vs animation** — PNG and JPEG are single stills of the finished
  design; the animation flags are ignored rather than refused, so
  `render rose --motion spin --out rose.png` degrades gracefully to a still.
- **Canvas and styling flags for raster output** — `--canvas WxH` (the pixel
  canvas, independent of the geometry-fitting `--fit`), `--stroke-width`,
  `--dot-radius`, `--ink`, `--background`, `--padding`, and `--loop` for GIF.
- **Antialiasing and dithering** — `--antialias` supersamples edges and blends
  them by coverage; `--aa-level N` and `--dither`/`--no-dither` control how the
  result is squeezed into GIF's 256-color budget.
- **Transparent backgrounds** — `--transparent` leaves a `.png` or `.gif`'s
  background empty so the drawing sits over whatever the page shows. A PNG is
  written truecolor-with-alpha with the background at alpha 0 and antialiased
  edges as straight alpha; a GIF flags index 0 as its transparent color in
  every frame. A `.jpg` has no alpha, so the flag is ignored there the way an
  animation flag is for a still.

### Changed

- **`colors_in` is the name; `colours_in` is deprecated.** The British spelling
  shipped in 1.1.0 keeps working and warns it will go away in a major.
- **American spelling is the house style**, documented in `docs/style-guide.md`
  and enforced by `tests/test_spelling.py` — including the docs reference page
  being renamed to `catalog.md`.

## [1.1.0] — 2026-07-31

The stretch release: color and layers, symmetric point sets, a faster
arc-length inversion, animation and a GIF writer, plotter output, an explorable
gallery, and snapping to a grid. All of it additive — a design with no styles
writes the file it always did, and every motif in the catalog builds the
geometry it built before.

Two of them ended somewhere other than where they set out. The numpy fast path
was written, measured, and deleted in favour of a pure-Python one that turned
out to be faster (see **Changed**); and the symmetric point sets ship marked
**experimental**, because what "evenly spaced" should mean when the symmetry
group makes it impossible is still an open question.

### Added

- **color and layers** (`geomotif.core.style`) — `Style`, `styled`,
  `styles_of`, `point_styles_of`, `layer_names` and `by_layer`. A style is
  attached per stroke and per loose point, and rides in `Design.meta` rather
  than in `Path`, because none of it changes the maths. Styles survive every
  transform, are laid end to end by `+` so `layer(red, blue)` keeps both, are
  dropped alongside a stroke that resampling drops, and are carried onto every
  fragment `clip_to` cuts a stroke into.
- **Layered output** — SVG writes each layer as the group Inkscape and `vpype`
  read, plus per-element `stroke`, `stroke-width` and `fill` wherever a style
  differs from the document's own; DXF writes real DXF layers and the seven
  colors its indexed palette can name; matplotlib draws a styled stroke in its
  own color and width. A design carrying no styles writes exactly the file it
  wrote before.
- Styles round-trip through `save_design`/`load_design` and through a spec,
  written beside the parameters rather than among them.
- `select_styles`, `PATH_STYLE_KEY` and `POINT_STYLE_KEY`
  (`geomotif.core.types`) — the extension-facing half. An operator that drops,
  splits or reorders strokes hands `select_styles` the source index of each one
  it kept, and the styles follow the geometry rather than shifting onto the
  wrong stroke. Operators built out of `+` get this for free. See
  [extending](https://pianosuki.github.io/geomotif/extending/).
- **`SymmetricPointSet`** (`geomotif.motifs.symmetry`, family `symmetry`) —
  the first motif that is *solved for* rather than evaluated. Points are laid
  out in the orbits of a cyclic or dihedral group and then relaxed toward
  equal nearest-neighbour spacing, which is what makes the awkward cases
  possible: fifteen points with five-fold mirror symmetry needs one ten-point
  orbit and one five-point orbit sitting on the mirror lines, and comes out
  exactly evenly spaced. A count the group cannot arrange is refused with the
  nearest two it can. Symmetry is preserved by construction — only one
  representative per orbit moves — so no seed is involved and the result is
  exactly reproducible. Four rules for joining the points up, including
  `"equal-distance"`, which draws the edges the relaxation was equalizing.
  Marked **experimental**; see the API policy.
- **`ArcTable.points_at` / `points_at_fractions`** — batch inverse lookup.
  Resampling asks for a run of distances in increasing order, so the run walks
  the cumulative table once between them all instead of binary-searching the
  whole of it per point. Order is exploited but never assumed: a distance that
  goes backwards seeks again, so the answers are identical to `point_at` in a
  loop, bit for bit.
- **Animation** (`geomotif.animate`) — `draw_on` reveals a design
  progressively by arc length, so the pen moves at a constant speed rather than
  racing through the sparse parts of the geometry; `spin` turns it about a
  point; `sweep` rebuilds a motif once per value of one of its parameters.
  Each returns a plain tuple of designs, so frames compose with everything
  else. A partly drawn closed path comes back open, because half a square is
  not a square.
- **Animated GIF** (`geomotif.io.gif`) — `to_gif` and `save_gif`, LZW and all,
  in pure standard library. Every frame is drawn against the same world
  rectangle and the same color table, so a growing drawing stays put and a
  two-pen design animates in two colors. Underneath it,
  `geomotif.io.raster` turns a design into an indexed bitmap: `rasterize`,
  the `Raster` it returns, and `colors_in` for the palette a set of designs
  needs. All three are usable on their own. The GIF writer understands the
  same color names the DXF writer does, so a styled design that exports to
  one exports to the other.
- `geomotif render NAME --out x.gif` with `--motion draw-on|spin`, `--frames`,
  `--hold` and `--fps`. `--fit` doubles as the pixel canvas, which is 480×480
  without it. `draw-on` appends a quarter of `--frames` again as a hold on the
  finished drawing, so a loop pauses rather than restarting the instant it
  arrives; `--hold N` sets that pause yourself, and `--hold 0` turns it off.
- `ArcTable.segment` — the part of a polyline between two distances, with the
  ends interpolated and every vertex between them kept.
- **Plotter output** (`geomotif.io.plotter`) — `to_plotter_svg` and
  `save_plotter_svg` write a design at a named paper size in real millimeters
  (`width="210mm"`, not `width="210"`), with `PAPER`, `page_size` and
  `on_page` behind them. `optimize` joins strokes whose ends meet and then
  orders them so the pen travels as little as possible between them, and
  `pen_up_distance` measures the difference: a 6×6 Truchet tiling goes from 72
  strokes and 2742 units of pen-up travel to 13 and 533. Neither pass ever
  crosses a layer, since strokes on different layers are drawn by different
  pens, and neither changes the ink.
- **`to_vpype`** — hands a design to [vpype](https://vpype.readthedocs.io/)
  directly, one vpype layer per style layer, named and page-sized. `vpype` is
  not a dependency of the library; the import is guarded and says how to
  install it. It *is* a dependency of the tests: the `plotter` group and a CI
  job of its own exist so that the comparison of `optimize` against
  `vpype linemerge linesort`, and the read-back of geomotif's own plotter SVG
  through `vpype`'s reader, actually run rather than skipping quietly.
- `to_svg(..., units="mm")` — a physical unit for the document's `width` and
  `height`, from `UNITS`, with the `viewBox` left in plain numbers.
- `geomotif render NAME --out x.svg --paper a4 [--landscape] [--margin MM]
  [--optimize]`.
- **An explorable gallery** (`geomotif.explore`, `geomotif explore`) — one
  self-contained HTML page with a slider for every parameter a slider can move.
  Every frame is rendered ahead of time by geomotif's own SVG writer and
  embedded in the document, so the page needs no server, no build step and no
  JavaScript library, and works from a `file://` URL. One parameter moves at a
  time: each slider sweeps its own with the others left at the motif's example
  values, because rendering every combination would be a combinatorial
  explosion. A value the motif refuses is dropped from the sweep rather than
  reported, and a parameter with no single axis to drag along — a point, a set
  of coordinates, another motif — is listed on the page as held still.
  `to_html`, `save_html`, `sweeps_for` and `Sweep` are the Python side of it;
  `--steps`, `--size` and `--samples` set how many values a slider offers, how
  big each frame is, and how densely it is drawn.
- **Snapping to a grid** — `snap` (`geomotif.core.transform`) and
  `Design.snapped`, which round the *design* rather than each file as it is
  written, so every writer, the plot and the gallery agree on the numbers.
  Three things a writer's `precision=` cannot do: any grid rather than only
  powers of ten (`snapped(0.5)`, `snapped(5.0)`); a choice of rounding rule
  (`half-even`, the default and what `precision=` has always done, then
  `half-up`, `floor`, `ceil`, `trunc`, listed in `SNAP_MODES`); and somewhere
  to put the points a coarse grid lands on top of each other. Those are
  zero-length segments — no ink, and a pen-down/pen-up the plotter spends time
  on regardless — so they are dropped by default, along with any stroke left
  with fewer than two points, with each surviving stroke's style carried
  across. `drop_duplicates=False` keeps the point count exactly as it was, for
  a caller feeding a fixed-size buffer or a per-point parallel array.
  `half-up` rounds *away from zero* rather than toward +∞, so a symmetric
  design does not come off the grid asymmetric.
- `geomotif render NAME --snap STEP [--snap-mode MODE] [--keep-duplicates]`,
  applied after `--fit`. The writers that place a design themselves — `.svg`,
  `--paper` included, `.gif` and the matplotlib formats — rescale the grid
  away as they write; the coordinate formats and `.dxf` keep it exactly.
- New at the top level: `Style`, `styled`, `styles_of`, `point_styles_of`,
  `layer_names`, `by_layer`, `snap`, `SNAP_MODES`, `SnapMode`, `to_gif`,
  `save_gif`, `to_plotter_svg` and `save_plotter_svg`. Import paths are a 1.x
  promise, so they are listed rather than left to be discovered.

### Changed

- Resampling a large design is about 1.4x faster (200k points off a
  100k-vertex polyline: 355ms to 248ms), with byte-identical output.

  A numpy fast path was written and measured first, per the original plan, and
  then deleted: with `Point` being a tuple of Python floats, `np.asarray` on a
  200k-point design costs more (44ms) than the entire pure-Python loop it was
  meant to replace, and numpy lost on transforms, bounds and length outright.
  It won only on the inverse lookup — and the ordered walk that shipped instead
  beats it there too, 67ms against 104ms, with no dependency. The core stays
  zero-dependency because that turned out to be the faster answer as well as
  the simpler one.
- The DXF layer table now lists the layers a design actually uses rather than
  the single `layer=` argument. Structure-preserving, and a file that parsed
  still parses, but it is a change to what is emitted.
- The API policy now defines what **experimental** means and lists what
  carries the label, and its list of public modules gains `geomotif.animate`
  and `geomotif.explore`.
- `save_points` and `save_design` now document what a negative `precision`
  actually does — round to tens, hundreds and so on, rather than merely
  "write whole integers" — and it is pinned by a test rather than left as an
  accident of `round`. The behavior is unchanged.
- `to_svg` refuses a `units` string that is not one, rather than writing it
  into the document's `width` and `height` attributes unquoted.
- `rasterize` refuses a negative `padding`, which used to return a blank
  raster, matching what `Design.fit` has always done.
- `SymmetricPointSet` validates `connect` when it is constructed rather than
  when `edges()` is called, and takes a `center` given as any pair of numbers.

### Fixed

Found in an audit of the above before release; none of it ever shipped.

- `to_plotter_svg` and `save_plotter_svg` ignored `margin` entirely. The
  design was placed on the page and then fitted to the page a second time by
  the SVG writer, which scaled it back out to the paper edge — so every margin
  produced the same file, running to the very edge of a sheet most plotters
  cannot reach.
- `to_gif(loop=1)` looped forever. The Netscape block counts *repeats* after
  the first play, so the count that would mean "once" is the one that means
  "forever"; playing once is the absence of the block.
- The rasterizer scaled a design onto `width` pixels where a `width`-pixel row
  addresses `0..width-1`, so the far edges landed one past the end and were
  dropped. Invisible at the default padding, and half the picture at
  `padding=0`.
- `SymmetricPointSet` collapsed for a few counts under a dihedral group —
  `D4` with 13, 17 or 29 points, `D5` with 16 or 41, and others. A ring orbit
  seeded onto a mirror line meets its own reflection, which the relaxation
  scores as every neighbour perfectly evenly spaced, and settles into. Swept
  over `C2`–`C8` and `D2`–`D8` at every count they accept: fifteen collapsed,
  none does now, and the number of counts that come out exactly evenly spaced
  rises from 255 to 287.
- `draw_on` never drew a stroke of zero length, so the last frame was not
  quite the finished drawing and a design of nothing but degenerate strokes
  animated as nothing at all.
- `snap` dropped a duplicate loose point only when it happened to be adjacent
  in the tuple. Loose points are a set with no walk through them, so the
  result depended on an ordering that carries no information.
- `plot_design` tested a stroke width for truthiness, so `Style(width=0.0)`
  silently became the figure's default.
- The explore page printed `--clip False` under its sliders, which argparse
  rejects; a boolean parameter's flag is `--clip` or `--no-clip`.
- `save_html` took `(path, names)` where every other writer takes
  `(subject, path)`. Corrected before the signature became a promise.

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
  output, `by="parameter"` for the old parametric behavior, and
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
  most of the catalog's implementation. Pick the base that matches how your
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
  rather than declared: the crossings are found geometrically and two-colored
  so that each strand alternates and each crossing disagrees with itself, and
  the under-strand is drawn with a gap in it, which is what a pen plotter can
  draw. The endless knot's corner joins nest at three corners and swap at the
  fourth -- nesting all four splits the figure into two separate rings, and
  the swap is what makes it endless.
- **Polyhedra** (`geomotif.motifs.solids`) — the five Platonic solids and
  `TruncatedIcosahedron`, plus `Polyhedron` for a shape of your own and
  `Projection` for orthographic, isometric or perspective views with yaw,
  pitch and roll. Every solid in the catalog is a table of corners and one
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
  package: Gielis's superformula, which geomotif's own catalog does not
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
  motif, one point count, several spacing curves. colors moved into a
  `Palette` value with `LIGHT` and `DARK`, so a dark-mode figure is a
  different argument rather than a different code path.
- **SVG** (`geomotif.io.svg`) — `to_svg` and `save_svg`, pure standard
  library. The design is fitted into the canvas before anything is written
  rather than scaled by a `viewBox`, so `stroke_width` means one unit of the
  file you are looking at and rounding to `precision` shrinks the file
  instead of discarding detail a later scale would magnify. `flip_y` defaults
  on, because SVG's y grows downward and every motif here is written the other
  way up. Loose points become `<circle>` elements, the motif's name becomes
  the document `<title>`, and every attribute is escaped — a color and a
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
- **`requires=` is now honored** (`geomotif.core.registry`) — `MotifInfo`
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
  reference pages and `docs/catalog.md`, and doubles as the mkdocs `hooks:`
  entry so a build is never a step behind the registry. The gallery and the
  reference are rebuilt every time and never committed; the catalog and the
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

- `generate_spiral()` and the `geomotif.generator` module. Its behavior
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
- Registry lookups now import the builtin motif catalog themselves.
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

[1.2.2]: https://github.com/pianosuki/geomotif/releases/tag/v1.2.2
[1.2.1]: https://github.com/pianosuki/geomotif/releases/tag/v1.2.1
[1.2.0]: https://github.com/pianosuki/geomotif/releases/tag/v1.2.0
[1.1.0]: https://github.com/pianosuki/geomotif/releases/tag/v1.1.0
[1.0.0]: https://github.com/pianosuki/geomotif/releases/tag/v1.0.0
