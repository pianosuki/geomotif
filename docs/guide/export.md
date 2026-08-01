# Exporting

Six file formats and one recipe format, and none of them needs a dependency.
The core is zero-dependency all the way out to the file.

| You want | Function | Reads back |
|---|---|---|
| coordinates for another tool | [`save_points`][geomotif.io.points.save_points] | no |
| coordinates **with the strokes kept apart** | [`save_design`][geomotif.io.points.save_design] | JSON only |
| a picture | [`save_svg`][geomotif.io.svg.save_svg] | no |
| something to cut, mill or plot | [`save_dxf`][geomotif.io.dxf.save_dxf] | no |
| the *recipe*, not the points | [`save_spec`][geomotif.io.spec.save_spec] | yes |
| a still picture | [`save_png`][geomotif.io.png.save_png], [`save_jpeg`][geomotif.io.jpeg.save_jpeg] | no |
| a moving picture | [`save_gif`][geomotif.io.gif.save_gif] | no |

## Coordinates

```python
from geomotif import save_points

save_points(design, "points.csv")  # x,y header + one row per point
save_points(design, "points.txt", precision=0)  # tab-separated whole integers
save_points(design, "points.json", precision=2)  # JSON array of [x, y] pairs
```

The format comes from the file suffix (`.csv`, `.txt`/`.tsv`, `.json`) or from
`fmt=`. `precision` rounds; `precision=0` writes whole integers rather than
`1.0`, and each step below that rounds to tens, hundreds and so on.

`save_points` flattens everything into one list, which is exactly right when
the destination only wants coordinates — a spreadsheet, a game map, a particle
system.

## Snapping to a grid

`precision` rounds the **file**. Each writer has its own, they do not have to
agree, and the design in memory still holds every digit — so a plot of it is
not quite the thing you exported.

[`Design.snapped`][geomotif.core.types.Design.snapped] rounds the **design**
instead. Do it once, and every writer, the plot and the gallery all show the
same numbers:

```python
aligned = design.snapped()  # nearest whole unit
half_mm = design.snapped(0.5)  # a grid no number of decimals can express
lattice = design.snapped(5.0, mode="half-up")
```

Three things it does that `precision` cannot.

**Any grid, not only powers of ten.** Decimal places give you ones, tenths and
hundredths. `snapped(0.5)`, `snapped(0.25)` and `snapped(5.0)` are the asks
that actually turn up — half-millimeter plotter steps, a pegboard, a tile size.

**A rounding rule you chose.** The default `half-even` is what Python's `round`
and therefore `precision` have always done: a coordinate exactly halfway goes
to the *even* neighbour, so a long list of halves does not drift upward.
`half-up` sends it away from zero instead, which is the rounding most people
were taught. `floor`, `ceil` and `trunc` always go the same way, for a
one-sided tolerance.

!!! note "`half-up` means away from zero"

    Not toward +∞. A design and its mirror image have to snap to mirror-image
    grids, and the toward-+∞ reading would shift one of the two by a whole step
    at every halfway point.

**Somewhere to put the collapsed points.** A coarse grid lands neighbouring
points on top of each other, and those are zero-length segments: no ink, and a
pen-down/pen-up the plotter spends time on anyway. `snapped` drops them, along
with any stroke left with fewer than two points, and carries each surviving
stroke's style across with it. Pass `drop_duplicates=False` to keep the point
count exactly as it was — what a fixed-size buffer or a per-point parallel
array needs:

```python
design.snapped(10.0)  # 200 points in, maybe 52 out
design.snapped(10.0, drop_duplicates=False)  # 200 in, 200 out, some identical
```

Only *consecutive* repeats go. A point landing on an earlier, non-adjacent
point of the same stroke is a crossing rather than a redundancy — a figure
eight on a coarse grid still has to go round both loops.

`snapped` puts the points on the grid; `precision=0` writes them as `3` rather
than `3.0`. Use both:

```python
save_points(design.snapped(), "points.csv", precision=0)
save_points(design.snapped(0.5), "points.csv", precision=1)
```

!!! warning "Snapping and arc-length spacing pull against each other"

    Equal spacing here means equal *real* distance, and a grid does not care.
    Points an equal distance apart come out equal only to within half a step.
    Snap **after** resampling, and keep the step well under the spacing if the
    evenness is what you were there for.

    The picture writers have their own version of this: both `to_svg` and
    `save_plotter_svg` fit the design into the canvas as they write, so they
    rescale a snapped design and the grid does not survive into the file. Snap
    is exact for `save_points`, `save_design`, the CLI's stdout, and DXF —
    which writes the design's own coordinates untouched.

## Coordinates with the strokes kept apart

When *where the pen lifts* matters, flattening loses the only thing you needed.
[`save_design`][geomotif.io.points.save_design] keeps it:

```python
from geomotif import load_design, save_design

save_design(design, "design.csv")  # a `path` column naming each point's stroke
save_design(design, "design.txt")  # a blank line between strokes
save_design(design, "design.json")  # structured -- and the only one that reads back

design = load_design("design.json")
```

The CSV `path` column is empty for the loose points, because they belong to no
stroke. The TXT form separates strokes with a blank line, which is what plotter
toolchains already read as "lift the pen".

`load_design` decodes the metadata without rebuilding the motif, so a design
saved by a plugin still loads on a machine that does not have that plugin
installed.

## SVG

```python
from geomotif import save_svg, to_svg

save_svg(design, "design.svg", width=800, background="#fff")
markup = to_svg(design, width=800, height=800, stroke="#333", stroke_width=1.5)
```

Two decisions are worth knowing about.

**The writer transforms the coordinates, not the canvas.** The design is fitted
into the canvas *before* anything is written, rather than being scaled by a
`viewBox`. So `stroke_width=1.0` means one unit of the file you are actually
looking at, whatever the design happened to measure — and rounding to
`precision` shrinks the file rather than throwing away detail that a later
scale would magnify back into visible steps.

**y is flipped by default.** SVG's y-axis grows downward and every motif here is
drawn the other way up, so `flip_y=True` is the default and a design comes out
the way you drew it.

Give `width` and `height` for an exact canvas, one of them to keep the
proportions, or neither to keep the design's own size plus `padding`. Loose
points become `<circle>` elements — that is the dot-art path — and `title=`
becomes the document `<title>`, so a gallery file labels itself.

## DXF

```python
from geomotif import save_dxf

save_dxf(design, "design.dxf", layer="CUTS")
```

DXF **R12**, deliberately. R12 is the version everything reads, so the writer
emits `POLYLINE`/`VERTEX`/`SEQEND` rather than `LWPOLYLINE` — which arrived
with R14 and would give up the compatibility R12 was chosen for.

A closed path carries the closed flag rather than a repeated final vertex, the
layer is declared in the file's own layer table, and the header records the
drawing extents so "zoom to fit" works the moment it opens. DXF is y-up like
the motifs themselves, so nothing is mirrored and the design keeps its own
measurements.

!!! info "Checked against real readers"

    Both writers were validated against third-party parsers — `ezdxf` and
    `svgelements` — during development, and the test suite takes every motif in
    the catalog through both formats and parses them back with readers
    written in nothing but the standard library. Neither third-party parser is
    a dependency.

## Specs: the recipe, not the points

A **spec** records the motif and its parameters instead of the geometry they
produced. It survives a change of point count, it is a file you can edit by
hand, and it is a great deal smaller — a mandala's recipe is 1.5 KB against
330 KB of coordinates:

```python
from geomotif import load_spec, save_spec

save_spec(motif, "design.json")
motif = load_spec("design.json")
design = motif.generate(2000)  # ...at whatever resolution you want today
```

```json
{
  "geomotif": "1.1.0",
  "motif": "spiral.fibonacci",
  "params": {
    "quarters": 9,
    "size": 10.0
  }
}
```

**One nested shape at every depth.** A parameter that is itself a motif — the
composers take one — is written as the same `{"motif": ..., "params": ...}`
object as the whole file, so a mandala's rings need no second notation. A
parameter that is a value dataclass (`Bounds`, `Ring`, `IFSMap`) becomes a
`{"$type": ...}` object naming its class.

Every motif in the catalog round-trips exactly, bar the two whose parameter
*is* a Python function: `polar.expression` and `string-art.envelope` are
parameterized by code rather than by data, and asking for their spec says so by
name rather than writing a file that will not load.

!!! warning "A spec is data, and data does not get to choose what you import"

    Loading a spec will not import a module the file names. `$type` resolution
    is restricted to `geomotif` itself plus any package that already declares a
    `geomotif.motifs` entry point — the packages that provide motifs on this
    machine anyway — and the resolved object has to be a dataclass class.
    Anything else is refused with the name it tried.

## Which one to reach for

- Sending points somewhere else → `save_points`.
- Driving a pen plotter, laser or mill → `save_dxf`, or `save_design` to `.txt`.
- Putting it on a web page or into an editor → `save_svg`.
- A single finished picture, anywhere and with nothing installed → `save_png`.
- Showing how it is drawn rather than what it is → `save_gif`, and
  [Animation](animation.md).
- Actually plotting it → `save_plotter_svg`, and
  [Plotting it for real](plotter.md).
- Saving your *work*, so you can change your mind about the resolution later →
  `save_spec`. It is the only one that is still useful after you have edited it.
