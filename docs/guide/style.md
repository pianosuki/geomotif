# color and layers

Geometry says where the ink goes. A [`Style`][geomotif.core.style.Style] says
which pen puts it there — a layer name, a color, a stroke width — and it rides
along in `Design.meta` rather than in `Path`, because none of it changes the
maths.

```python
from geomotif import layer, save_svg, styled
from geomotif.motifs import Circle, Phyllotaxis

outline = styled(Circle(radius=120).build(), layer="pen1", stroke="black")
seeds = styled(Phyllotaxis(count=400).build(), layer="pen2", stroke="crimson")

save_svg(layer(outline, seeds), "two-pens.svg")
```

That file opens in Inkscape as two named layers, loads into `vpype` as two
layers, and plots as two pen changes.

## Applying a style

[`styled`][geomotif.core.style.styled] lays a style over every stroke and every
loose point of a design:

```python
styled(design, layer="pen1")
styled(design, stroke="#c0392b", width=0.35)
styled(design, Style(layer="cuts", stroke="red"))  # or a whole style at once
```

Styling **merges** rather than replaces, so the two calls compose:

```python
design = styled(styled(design, layer="pen1"), stroke="red")
# every stroke is now Style(layer="pen1", stroke="red")
```

Every field is optional, and `None` means *not stated* rather than *default*: a
style that names only a layer still draws in whatever ink the writer was told to
use. Nothing is required to carry a style, and a design that carries none writes
exactly the file it wrote before this existed.

## What survives what

Styles are attached per stroke and per loose point, and every operation that
reshapes a design keeps them lined up with the geometry:

| Operation | What happens to the styles |
|---|---|
| `transformed`, `fit`, `flipped_y`, `jitter` | carried, one for one |
| `a + b`, `layer(...)`, `radial_repeat`, `tile` | laid end to end, so both designs keep theirs |
| `resampled` | carried; a stroke dropped for want of points takes its style with it |
| `clip_to` | carried onto every fragment a stroke is cut into; dropped with what falls outside |
| `save_points`, iteration | gone — those are coordinates, and a coordinate has no color |

The end-to-end rule for `+` is the one that matters. A right-biased merge would
hand the whole result the second design's styles, and `layer(red, blue)` would
come out entirely blue — which is the one thing a layer exists to prevent.

## Reading them back

```python
from geomotif import by_layer, layer_names, point_styles_of, styles_of

styles_of(design)  # one entry per stroke, None where a stroke has none
point_styles_of(design)  # the same, per loose point
layer_names(design)  # ("pen1", "pen2") -- in the order they are drawn
by_layer(design)  # {"pen1": Design(...), "pen2": Design(...)}
```

`styles_of` is always exactly as long as `design.paths`, whatever the metadata
says, so you can zip the two without checking.

`by_layer` keys anything unlayered under `None` rather than under a stand-in
name, because each writer has its own idea of what the unnamed layer is called —
`"0"` in DXF, `1` in `vpype` — and picking one here would be wrong somewhere
else.

## What each writer does with them

**SVG** writes each layer as the group Inkscape and `vpype` read
(`inkscape:groupmode="layer"`), and per-element `stroke`, `stroke-width` and
`fill` attributes wherever a style differs from the document's own. A styled dot
takes its color as a fill and its `width` as a radius.

**DXF** writes real DXF layers: every one is declared in the file's layer table
and every entity carries its own. color is the part DXF barely models — R12
knows 255 indexed colors and no arbitrary ones — so the seven it can name
(`red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `white`/`black`) are
written as entity colors and anything else is left to the layer. Layer names
have to be ones R12 permits: at most 31 characters from letters, digits and
`_$-.`, which the writer checks rather than leaving to the reader.

**matplotlib** draws a styled stroke in its own color and width, so a two-pen
design looks on screen the way it will come off the plotter.

**Specs and design files** carry styles too. They are written beside the
parameters rather than among them, because they belong to the design rather than
to the motif:

```json
{
  "geomotif": "1.2.0",
  "motif": "circle",
  "params": {"radius": 120.0},
  "path-style": [{"$type": "geomotif.core.style.Style", "layer": "pen1", ...}]
}
```

The two metadata keys are hyphenated deliberately — no Python parameter can be
called `path-style`, so a motif's own parameters can never collide with them.

## Preparing the file for a plotter

Layers are what the plotter helpers work in terms of: `optimize` sorts and
merges strokes within each layer and never across them, and `to_plotter_svg`
writes the whole thing at a physical paper size in millimeters. See
[Plotting it for real](plotter.md).
