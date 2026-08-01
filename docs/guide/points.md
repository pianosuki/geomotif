# Where the points land

This is the part of geomotif that is not like other geometry libraries, so it
is worth ten minutes.

## Two different meanings of "evenly spaced"

Take a spiral. Its formula is a radius and an angle, both functions of one
parameter. The easy way to draw it is to step that parameter evenly and connect
what comes out — and every point you place is then evenly spaced *in the
parameter*, which on a spiral means bunched up where the curve is tight and
stretched out where it is wide.

That is fine for a picture. It is wrong for anything where the distance between
the points is the thing you care about: dot art, bead layout, plotter stipple,
object placement, particle seeding, a motion path with a constant speed along
it.

geomotif's default is the other meaning. `generate(n)` gives you `n` points
whose *real x,y distance* from their neighbours is equal:

```python
from geomotif.motifs import ArchimedeanSpiral

design = ArchimedeanSpiral(b=10.0).generate(200)
```

You can ask for the parametric behavior when you want it — it is occasionally
a nice design effect — but you have to ask:

```python
design = ArchimedeanSpiral(b=10.0).generate(200, by="parameter")
```

## How it works

There is no closed form for the arc length of most interesting curves, and for
plenty of motifs there is no formula at all — an L-system is a walk, a Voronoi
diagram is the output of an algorithm. So the engine does not integrate
anything. It:

1. **Densifies** the shape into a polyline fine enough that the error of
   treating each piece as straight is below what you could plot
   ([`densify`][geomotif.core.sampling.densify]).
2. Builds a **cumulative-length table** over that polyline
   ([`ArcTable`][geomotif.core.sampling.ArcTable]).
3. **Inverts** it: given a target distance, binary-searches the table and
   interpolates within the segment it lands in.

Because step 2 only ever sees a list of points, every motif gets this for free —
including your own, and including motifs whose geometry arrived from an
algorithm rather than an equation.

Step 3 is where the time goes, and resampling asks for a whole run of distances
at once — in increasing order, because that is what walking along a curve means.
[`ArcTable.points_at`][geomotif.core.sampling.ArcTable.points_at] takes the run
rather than one distance at a time and walks the table once between them all,
which is where most of the cost of a large resample went. Order is exploited but
never assumed: a distance that goes backwards seeks again, so the answers are
identical to calling `point_at` in a loop, to the last bit.

!!! note "The one place the two measures visibly differ"

    Spacing is measured *along the curve*. When the gaps are small relative to
    the local radius — the usual case — the straight-line distance between
    neighbours is effectively identical. Only a gap that curls around a large
    fraction of a tight turn comes out noticeably shorter than its along-curve
    length, which is a fact about circles rather than about the implementation.

## Fixed step: let the count fall out

For plotter and dot-placement work you usually do not have a point budget; you
have a gap. Say the gap and let the geometry decide how many points that takes:

```python
design = spiral.generate(step=5.0)  # a point every 5 units of real distance
len(design)  # however many that came to
```

`count=` and `step=` are mutually exclusive, and `step` is applied
independently to every stroke in a design.

## Spacing curves

Equal spacing is the default, not the only option. A **spacing curve** maps
[0, 1] → [0, 1] and reshapes how the arc length is consumed — dense at one end,
dense at both ends, whatever the curve says:

```python
from geomotif import PowerSpacing, ExponentialSpacing, SmoothstepSpacing

spiral.generate(200, spacing=PowerSpacing(2.5))
spiral.generate(200, spacing=ExponentialSpacing(mode="out", strength=6))
spiral.generate(200, spacing=SmoothstepSpacing())
```

| Curve | Character |
|---|---|
| [`LinearSpacing()`][geomotif.core.spacing.LinearSpacing] | equal spacing — the default |
| [`PowerSpacing(exponent, mode)`][geomotif.core.spacing.PowerSpacing] | general "by how much" control; `1` is equal |
| [`QuadraticSpacing(mode)`][geomotif.core.spacing.QuadraticSpacing] | classic t² easing |
| [`CubicSpacing(mode)`][geomotif.core.spacing.CubicSpacing] | classic t³ easing |
| [`SineSpacing(mode)`][geomotif.core.spacing.SineSpacing] | a gentle bias |
| [`ExponentialSpacing(mode, strength)`][geomotif.core.spacing.ExponentialSpacing] | dramatic clustering, tunable |
| [`CircularSpacing(mode)`][geomotif.core.spacing.CircularSpacing] | quarter-arc profile |
| [`SmoothstepSpacing()`][geomotif.core.spacing.SmoothstepSpacing] | inherently in-out, dense at both ends |
| [`ReversedSpacing(curve)`][geomotif.core.spacing.ReversedSpacing] | mirror any curve, including a plain callable |
| [`CompositeSpacing(*curves)`][geomotif.core.spacing.CompositeSpacing] | chain eases left to right |
| [`TableSpacing(points)`][geomotif.core.spacing.TableSpacing] | draw the curve by hand from control points |

Most take `mode="in"` (spacing gradually increases), `"out"` (gradually
decreases) or `"in_out"`. The modal machinery lives once in the base class, so
a curve you write gets all three modes from implementing `ease(t)` alone:

```python
from geomotif import SpacingCurve


class Stepped(SpacingCurve):
    """Four discrete bands rather than a continuous ramp."""

    def ease(self, t: float) -> float:
        return round(t * 4) / 4
```

A plain callable works too — anything taking a float and returning a float is
accepted wherever a curve is, and
[`coerce_spacing`][geomotif.core.spacing.coerce_spacing] is what wraps it.

## Designs with more than one stroke

A tiling has hundreds of strokes; a Cassini oval has two. `count` is a total,
and `distribute=` decides how it is split:

| Mode | Split | Use it when |
|---|---|---|
| `"length"` *(default)* | proportional to each stroke's arc length | you want uniform visual **density** |
| `"even"` | `count // len(paths)` on each | you want uniform per-stroke **detail** |
| `"per_path"` | `count` on *every* stroke | the strokes are meant to match each other |

```python
tiling.generate(5000)  # even density over the whole figure
tiling.generate(5000, distribute="even")  # every cell gets the same budget
```

Loose points — the ones a design carries outside any stroke, like the seed head
of a phyllotaxis or the output of a chaos game — are passed through untouched.
They are already exactly the points the motif meant, and there is no curve to
redistribute them along.

## Native resolution

`build()` gives a motif at whatever resolution it thinks it needs;
`generate()` resamples that. The distinction matters more than it looks:

```python
design = motif.build()  # the shape, at its own idea of enough detail
design = motif.generate(200)  # 200 points, arc-length placed
```

For a curve, native resolution is a smooth-enough polyline — a few hundred
samples, or more if it winds a lot. For a polygon it is the corners and nothing
else, which is the whole reason
[`PolygonMotif`][geomotif.bases.PolygonMotif] exists separately from
[`ParametricMotif`][geomotif.bases.ParametricMotif]: sampling a pentagon at 512
evenly spaced parameters rounds all five corners off, and listing them costs
five points.

If you are exporting for a plotter, `build()` is usually what you want. If you
are placing objects, `generate()` is.
