# Animation

A still image says what a design *is*. An animation says how it is made, which
for most of this catalogue is the more interesting half — watching a Hilbert
curve fill its square tells you something the finished picture cannot.

```python
from geomotif.animate import draw_on
from geomotif.io.gif import save_gif
from geomotif.motifs import HilbertCurve

save_gif(draw_on(HilbertCurve(depth=5).build(), frames=60), "hilbert.gif")
```

or from the command line:

```bash
geomotif render fractal.hilbert --depth 5 --out hilbert.gif --frames 60
geomotif render rose --out rose.gif --motion spin --frames 48 --fps 24
```

No dependency is involved in any of it — not for the frames, not for the
rasterizing, and not for the GIF's LZW compression.

## Frames

Everything in [`geomotif.animate`][geomotif.animate] returns a plain tuple of
`Design`s, one per frame, so frames compose with the rest of the library:
transform them, restyle them, export one as SVG, or hand the lot to `save_gif`.

| Function | What moves |
|---|---|
| [`draw_on`][geomotif.animate.draw_on] | the pen: the design is revealed progressively |
| [`spin`][geomotif.animate.spin] | the design: it turns about a point |
| [`sweep`][geomotif.animate.sweep] | a parameter: the motif is rebuilt for each value |

```python
draw_on(design, frames=60, trail=200.0, hold=10)
spin(design, frames=48, turns=-1.0)
sweep(Rose(), "n", range(2, 12))
```

`draw_on` measures progress in **arc length**, not in vertices, so the pen
moves at a constant speed rather than racing through the sparse parts of the
geometry and crawling through the dense ones. A partly drawn closed path comes
back open — half a square is not a square, and drawing it as one would close a
gap the pen has not been round yet.

`trail` draws only the last *n* units rather than everything so far, which
turns the pen into a comet. `hold` repeats the finished drawing, so a looping
animation pauses on the result instead of restarting the instant it arrives.

## Writing the GIF

```python
from geomotif.io.gif import save_gif, to_gif

save_gif(frames, "out.gif", width=480, height=480, fps=20)
blob = to_gif(frames, ink="#0b0b0b", background="#ffffff", thickness=2, loop=3)
```

Two things are decided for you, because getting either wrong looks like a bug:

**One canvas for every frame.** Each frame is drawn against the union of all
their bounds, not its own — otherwise a drawing that grows would rescale on
every frame and crawl about the canvas instead of standing still.

**One colour table for every frame.** Styles pick up their own palette entries,
so a two-pen design animates in two colours; but the table is worked out across
the whole animation, or an index that meant crimson in one frame and black in
the next would make the result flicker.

GIF stores a delay in hundredths of a second and nothing finer, so `fps` is
rounded to what the format can actually say — 20fps is 5 hundredths, and
anything above 50fps hits the floor. `loop=0`, the default, repeats forever.

A GIF holds at most 256 colours; a design that needs more is refused rather
than quantized, with a message saying so.

## Rasterizing on its own

[`rasterize`][geomotif.io.raster.rasterize] is the piece underneath, and it is
usable by itself when you want pixels rather than an animation:

```python
from geomotif.io.raster import rasterize

raster = rasterize(design, width=800, height=600, thickness=2)
raster.pixels  # one palette index per pixel, top-left origin
raster.palette  # ("#ffffff", "#0b0b0b", ...)
```

Lines are drawn with Bresenham's algorithm and nothing is antialiased, which is
the right answer for an indexed image: there are only a handful of colours and
nothing for a blend to blend *with*.

!!! note "This is the one raster format here"

    Everything else geomotif writes is vector, and deliberately: a design is a
    set of curves, and the formats that keep them curves are the ones worth
    writing. Pixels exist here for animation, which has no vector form that
    plays everywhere. For a still image, use [SVG](export.md#svg).
