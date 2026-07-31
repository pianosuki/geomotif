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
`1.0`.

`save_points` flattens everything into one list, which is exactly right when
the destination only wants coordinates — a spreadsheet, a game map, a particle
system.

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
    `svgelements` — during development, and the test suite takes all 146
    motifs through both formats and parses them back with readers written in
    nothing but the standard library. Neither third-party parser is a
    dependency.

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
  "geomotif": "1.0.0",
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

Every motif in the catalogue round-trips exactly, bar the two whose parameter
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
- Showing how it is drawn rather than what it is → `save_gif`, and
  [Animation](animation.md).
- Actually plotting it → `save_plotter_svg`, and
  [Plotting it for real](plotter.md).
- Saving your *work*, so you can change your mind about the resolution later →
  `save_spec`. It is the only one that is still useful after you have edited it.
