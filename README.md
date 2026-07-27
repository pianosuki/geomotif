# geomotif

[![PyPI](https://img.shields.io/pypi/v/geomotif)](https://pypi.org/project/geomotif/)
[![Python](https://img.shields.io/pypi/pyversions/geomotif)](https://pypi.org/project/geomotif/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A library for generating and plotting geometric designs. The spiral is the
first motif it ships; the point-placement engine underneath is the part that
generalizes.

Generate precisely spaced points along arbitrary spirals — between any start
and end point, around any center, in either direction, with any number of
turns — and control how the points are distributed along the path with
pluggable spacing curves.

Positioning is **true arc-length** by default: equal spacing means the same
real x,y distance between every consecutive pair of points, no matter how
tightly the spiral winds. Built for designs where the physical distance
between points is what matters — generative art, plotter art, game object
placement, particle layouts, UI motion paths.

Zero dependencies for the core; matplotlib is an optional extra for
visualization. Requires Python 3.12+.

## Install

```bash
pip install geomotif           # core (no dependencies)
pip install 'geomotif[plot]'   # with matplotlib plotting helpers
```

## Quickstart

```python
from geomotif import generate_spiral, PowerSpacing

points = generate_spiral(
    start=(200, 0),  # required — first point (always included)
    end=(20, 0),  # required — last point (always included)
    num_points=100,  # required — total points, inclusive of both ends
    center=(0, 0),  # point the spiral winds around (default shown)
    clockwise=True,  # rotation direction (default clockwise)
    y_down=False,  # True for y-down (screen-style) coordinates
    turns=3,  # extra full revolutions (default 0)
    spacing=PowerSpacing(2.5),  # point distribution (default equal spacing)
    arc_length=True,  # position by real distance along the curve (default)
)

for x, y in points:
    ...
```

Everything after `num_points` is keyword-only.

## Exporting points

Send the coordinates to any other tool — editors, plotters, spreadsheets,
game map formats — with `save_points`:

```python
from geomotif import save_points

save_points(points, "points.csv")  # x,y header + one row per point
save_points(points, "points.txt", precision=0)  # tab-separated whole integers
save_points(points, "points.json", precision=2)  # JSON array of [x, y] pairs
```

The format is inferred from the file suffix (`.csv`, `.txt`/`.tsv`,
`.json`) or forced with `fmt=`. `precision` rounds coordinates;
`precision=0` writes whole integers.

## Plotting

To see the points on a graph (requires the `plot` extra):

```python
import matplotlib.pyplot as plt
from geomotif.plotting import plot_spiral

plot_spiral(points, center=(0, 0), title="my spiral")
plt.show()
```

Or run the built-in showcase:

```bash
geomotif-demo             # interactive window (or python -m geomotif)
geomotif-demo demo.png    # save to a file instead
```

## Spacing curves

All curves subclass `SpacingCurve` — implement `ease(t)` mapping
[0, 1] → [0, 1] to make your own; any plain callable works too. Most take
`mode="in"` (spacing gradually increases), `"out"` (gradually decreases), or
`"in_out"`.

| Curve | Character |
|---|---|
| `LinearSpacing()` | equal spacing (default) |
| `PowerSpacing(exponent, mode)` | general "by how much" control; 1 = equal |
| `QuadraticSpacing(mode)` | classic t² easing |
| `CubicSpacing(mode)` | classic t³ easing |
| `SineSpacing(mode)` | gentle bias |
| `ExponentialSpacing(mode, strength)` | dramatic clustering, tunable |
| `CircularSpacing(mode)` | quarter-arc profile |
| `SmoothstepSpacing()` | inherently in-out, dense at both ends |

## Notes on geometry

- Angles use the standard math convention (y-up). If your target coordinate
  system has the y-axis pointing down (screen/raster style), pass
  `y_down=True` so `clockwise` matches the direction you actually see.
- With `arc_length=True` (default), spacing is measured in distance *along
  the curve*. When gaps are small relative to the local radius (the usual
  case), the straight-line distance between neighbors is effectively
  identical; only a gap that curls around a large fraction of a tight turn
  dips noticeably below its along-curve length.
- `arc_length=False` restores parametric spacing (equal steps of
  angle/radius progress), which visually compresses toward tight sections —
  occasionally useful as a design effect.
- Degenerate inputs are handled gracefully: an endpoint on the center yields
  a radial line; identical start and end with `turns=0` yields coincident
  points.

## Development

```bash
git clone <repo-url> && cd geomotif
pip install -e . --group dev    # editable install + pytest + matplotlib
pytest                          # run the test suite
```

Build and publish:

```bash
python -m build                 # or: uv build / hatch build
twine upload dist/*             # or PyPI trusted publishing via CI
```

## License

[MIT](LICENSE)
