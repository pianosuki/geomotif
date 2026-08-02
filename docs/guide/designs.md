# Designs, paths and transforms

## The data model

There are four types, and three of them are trivial.

`Point` is `tuple[float, float]`. Not a class — a
tuple, so it unpacks, compares, hashes and goes straight into anything that
expects a pair of numbers.

[`Bounds`][geomotif.core.types.Bounds] is an axis-aligned rectangle with
`width`, `height`, `center`, `union()`, `padded()` and `in`.

[`Path`][geomotif.core.types.Path] is one stroke: a tuple of points, plus
`closed`. It knows its own `length` and `bounds`.

[`Design`][geomotif.core.types.Design] is the universal result — some strokes,
some loose points, and metadata:

```python
design.paths  # tuple[Path, ...]  -- the strokes
design.points  # tuple[Point, ...] -- points that carry no stroke
design.meta  # the motif name and its resolved parameters
```

The split between `paths` and `points` is the difference between a line and a
scatter, and it survives all the way to the exporters: a path becomes a `<path>`
or a DXF `POLYLINE`, a loose point becomes a `<circle>` or a DXF `POINT`. Dot
art and stipple are loose points; a plotter drawing is paths.

A design iterates as a flat stream of coordinates, so it drops into anything
that just wants numbers:

```python
for x, y in design:
    place_object(x, y)

len(design)  # total point count, strokes and loose points together
design.bounds  # over everything
design + other  # overlay
```

Everything is immutable. `Design`, `Path` and `Bounds` are all frozen slotted
dataclasses, every operation returns a new value, and NaN and infinity are
rejected at construction rather than propagating silently into an exported
file.

## The operations on a design

```python
design.fit(800, 600, padding=20)  # scale and center onto a canvas
design.flipped_y()  # y-down (screen/SVG) coordinates
design.transformed(matrix)  # apply an affine
design.resampled(400)  # the same engine generate() uses
```

`fit` scales **uniformly** — a design is never distorted — and centers it in
whichever axis has slack. So the axis that limits the scale fills the canvas
and the other one is centerd inside it, which is what you want and is worth
knowing before you assert on the result.

## Affine transforms

[`Affine`][geomotif.core.transform.Affine] is the usual 2×3 matrix, with named
constructors and `@` for composition:

```python
import math

from geomotif import Affine

m = Affine.rotate(math.pi / 6) @ Affine.scale(2.0)
design.transformed(m)
```

`@` reads right to left, the way function composition does:
`(m @ n)(p) == m(n(p))`, so the right-hand transform applies first. Every
`Affine` is invertible with `.inverse()` unless it is degenerate, in which case
it says so.

## Turning one shape into a pattern

The composite operators in [`geomotif.core.transform`][geomotif.core.transform]
are where a motif becomes a pattern. They take a design and return a design, so
they compose with each other and with anything a motif built:

```python
from geomotif import clip_to, jitter, layer, mirror_axis, radial_repeat, snap, symmetry_group, tile

petal = my_motif.build()
cell = my_cell.build()

rosette = radial_repeat(petal, 12)  # the mandala workhorse
lattice = tile(cell, 8, 8, dx=20, dy=20, stagger=0.5)  # brickwork if stagger != 0
mirrored = mirror_axis(design, math.pi / 4)
group = symmetry_group(design, "D6")  # the dihedral groups by name
loose = jitter(design, 0.5, seed=7)  # reproducible irregularity
aligned = snap(design, 0.5)  # every point onto a half-unit grid
inside = clip_to(design, bounds)  # segment-level, not point-level
stack = layer(background, middle, foreground)
```

Three of those have a detail worth calling out.

`jitter` takes a `seed`, and the same seed always reproduces the same result —
the RNG lives only inside the call, so a reproducible irregularity does not
depend on the global `random` state. The seed is not recorded in `meta`; keep
hold of it yourself if you want to regenerate the same points.

`snap` is `jitter`'s opposite number and the rounding you would otherwise have
to do per file. It takes any grid rather than a number of decimal places, and
drops the points a coarse grid stacked on top of each other, because those are
zero-length segments the plotter would spend time on for no ink. It is also the
one operator here that gives something up: grid alignment costs you a little of
the exact arc-length spacing. See [Snapping to a grid](export.md#snapping-to-a-grid).

`clip_to` clips **segments**, not points. Dropping the points that fall outside
a rectangle leaves a stroke that jumps the gap; clipping the segments cuts each
one at the boundary and splits the stroke there, which is what a plotter needs
and what a viewer expects to see.

## Composing motifs out of motifs

[`geomotif.compose`][geomotif.compose] holds motifs whose *parameter* is another
motif:

```python
from geomotif.compose import Kaleidoscope, LayeredRings, Mandala, Ring, Snowflake, SpokePattern
from geomotif.motifs import Circle, StarPolygon

mandala = Mandala(
    rings=(
        Ring(unit=StarPolygon(points=7, step=3, radius=14.0), count=12, radius=80.0),
        Ring(unit=Circle(radius=10.0), count=24, radius=120.0),
    )
)
```

The unit is anything with a `build()` method, which means a composed figure can
itself be the unit of another composition. It also means the composers accept
your motifs on exactly the same terms as the builtin ones.

## Metadata and reproducibility

`Design.meta` carries the motif's name and its resolved parameters — including
any random seed that was generated rather than given. That is what makes a
design self-describing: the gallery labels its images from it, `to_spec` writes
a recipe from it, and `load_design` reads it back on a machine that does not
have the motif that produced it.

`meta` is a read-only mapping, and overlaying two designs merges it
right-biased. A composed design no longer describes a single motif, so the
composers set their own `meta` on the result rather than trusting that merge.
