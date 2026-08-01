# Plotting it for real

A pen plotter cares about three things the rest of this library does not: how
big the paper is, how far the pen travels while it is *up*, and which pen is
drawing. [`geomotif.io.plotter`][geomotif.io.plotter] answers all three.

```python
from geomotif.io.plotter import optimize, pen_up_distance, save_plotter_svg

design = optimize(mandala.build())
save_plotter_svg(design, "mandala.svg", paper="a4", margin=15.0)
```

```bash
geomotif render tiling.truchet --out plot.svg --paper a4 --optimize
```

## A real size

`save_plotter_svg` writes `width="210mm"`, not `width="210"`, with a `viewBox`
of the same numbers. One user unit is one millimeter, so `stroke_width=0.35` is
a 0.35 mm pen and the drawing arrives the size you asked for rather than
whatever the receiving software guessed.

```python
from geomotif.io.plotter import PAPER, on_page, page_size, to_plotter_svg

page_size("a3", landscape=True)  # (420.0, 297.0)
sorted(PAPER)  # a2 a3 a4 a5 a6 legal letter tabloid
on_page(design, paper="a4", margin=10.0)  # the design, fitted, in mm, y-down
```

The margin is worth more than it looks: most plotters cannot reach the last few
millimeters of a sheet. `to_plotter_svg` and `save_plotter_svg` take it
directly, and `--margin` does the same on the command line:

```bash
geomotif render mandala --out plot.svg --paper a4 --margin 20
```

## Fewer wasted moves

A design built cell by cell is thousands of separate strokes in whatever order
the algorithm produced them, and the plotter dutifully lifts the pen between
every one. [`optimize`][geomotif.io.plotter.optimize] makes two passes:

1. **Merge** — two open strokes whose ends meet within `tolerance` become one,
   reversing either if that is what makes them meet. A stroke whose own ends
   then meet is closed.
2. **Sort** — the strokes are ordered greedily from where the pen starts,
   always taking whichever begins nearest to where it just finished, and
   reversing an open stroke when its far end is the nearer one.

[`pen_up_distance`][geomotif.io.plotter.pen_up_distance] measures the
difference rather than asserting it:

| Design | Strokes | Pen up |
|---|---|---|
| `tiling.truchet` | 72 → **13** | 2742 → **533** |
| `tiling.square` | 96 → **50** | 5491 → **2165** |
| `mandala` | 37 → 37 | 1530 → **1238** |

Neither pass ever changes the ink: the same curves are drawn in the same
colors, in a better order. There is a test that the total drawn length comes
out identical.

**Neither pass crosses a layer.** Strokes on different layers are drawn by
different pens, and joining them would mean drawing one of them in the wrong
color. Nor are strokes of different colors joined within a layer.

## Layers are pens

Everything here works in terms of [color and layers](style.md). One layer per
pen, and the SVG comes out with the groups Inkscape and `vpype` both read:

```python
from geomotif import layer, styled

drawing = layer(
    styled(outline, layer="black", stroke="#000"),
    styled(shading, layer="red", stroke="#c00"),
)
save_plotter_svg(optimize(drawing), "two-pens.svg", paper="a3")
```

## Handing it to vpype

[`vpype`](https://vpype.readthedocs.io/) is the pen-plotter toolchain —
occlusion, hatching, HPGL output, a whole pipeline this library is deliberately
not trying to be. Two ways in.

**The file.** What `save_plotter_svg` writes is what `vpype` reads, layers and
page size included:

```bash
vpype read plot.svg linemerge linesort reloop write --page-size a4 out.svg
```

**The object**, skipping the file entirely:

```python
import vpype_cli
from geomotif.io.plotter import to_vpype

document = to_vpype(design, paper="a3", margin=20.0)
vpype_cli.execute("linemerge linesort write out.svg", document)
```

`vpype` is not a dependency — `to_vpype` imports it behind a guard and says how
to install it if it is not there. Its `linemerge`/`linesort` and `optimize` do
the same job; the test suite runs both over the same design and holds this one
to within a quarter of `vpype`'s result, which is what a greedy pass should
manage.
