# Plotting

Everything else in geomotif is dependency-free. This module is not: it needs
matplotlib, which is why it is behind an extra.

```bash
pip install 'geomotif[plot]'
```

Importing [`geomotif.plotting`][geomotif.plotting] without matplotlib raises at
import time with a message that says which extra to install. Nothing else in
the library imports it, so the rest works untouched on a machine that has not
got it.

## One design

```python
import matplotlib.pyplot as plt

from geomotif.plotting import plot_design

plot_design(design, show_points=True, center=(0, 0), title="my spiral")
plt.show()
```

`plot_design` draws onto an axes and returns it, creating a styled figure when
you do not pass one. Its strokes become lines and its loose points become
markers — always, since a loose point is the only thing a scatter motif has to
show.

The options worth knowing:

| Option | Effect |
|---|---|
| `show_points=True` | draw a marker at every point, not just the line |
| `guide=` | a second, smoother design drawn faintly underneath — the curve the points sit on |
| `center=` | mark a focal point, for spirals and rosettes |
| `label_endpoints=True` | annotate the first and last point of each stroke |
| `ax=` | draw into an axes you already have |
| `palette=` | `LIGHT` or `DARK` |

## Several designs

```python
from geomotif.plotting import plot_grid

fig = plot_grid(
    [
        ("linear", linear_design, {}),
        ("power 2.5", eased_design, {"show_points": True}),
    ],
    ncols=2,
    suptitle="two spacings",
)
```

Each panel is `(title, design, extra)`, where `extra` is passed through to
`plot_design` for that panel alone. Keyword arguments to `plot_grid` itself
apply to every panel, and a panel's own `extra` wins where the two disagree.

## The premise, in one figure

```python
from geomotif import ExponentialSpacing, PowerSpacing, SmoothstepSpacing
from geomotif.plotting import plot_comparison

fig = plot_comparison(
    spiral,
    [None, PowerSpacing(2.5), ExponentialSpacing(mode="out", strength=6), SmoothstepSpacing()],
)
```

Same curve, same number of points in every panel; only where they land changes.
That is the whole library in one picture, and it is what `geomotif demo` runs.

The motif is built **once** and resampled per panel, rather than generated per
panel — the geometry is identical in every one, and demonstrating that is the
point.

## Palettes

colors live in a [`Palette`][geomotif.plotting.Palette], a frozen dataclass
with two instances shipped: `LIGHT` and `DARK`.

```python
from geomotif.plotting import DARK, Palette, plot_design

plot_design(design, palette=DARK)

mine = Palette(
    page="#101014",
    surface="#191920",
    primary_ink="#eaeaf0",
    secondary_ink="#9a9aa8",
    muted="#4a4a58",
    gridline="#26262f",
    baseline="#33333f",
    series="#7aa2f7",
)
plot_design(design, palette=mine)
```

Gathering them into one value rather than leaving them as module constants is
what makes a dark-mode figure a different *argument* instead of a different
code path.

## Saving without matplotlib

You do not need this module to get a picture. [`save_svg`](export.md#svg) is
pure standard library and produces a file every browser, editor and plotter
toolchain reads. For a still image in particular, `save_png` is the
recommended alternative — also pure standard library, no matplotlib required
— when you want pixels rather than vectors. Reach for matplotlib when you
want axes, a grid, labeled endpoints and a comparison figure — that is, when
you are inspecting the points rather than drawing the design.
