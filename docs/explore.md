# Explore

geomotif can be driven entirely from the command line, but the catalog is
large and the parameters interact, and the quickest way to find the shape
you want is to see it move. The **explore** stage is the whole library
running in a browser: the same wheel that installs locally loads into
Pyodide, so every render the page produces is byte-identical to
`geomotif render`. No download, no server, no account.

[Open the explore stage &rarr;](https://pianosuki.github.io/geomotif/explore/){ .md-button .md-button--primary }
[Browse the catalog &rarr;](catalog.md){ .md-button }

<div class="strip" markdown>
![](assets/spiral.golden.svg){ .motif }
![](assets/rose.maurer.svg){ .motif }
![](assets/fractal.hilbert.svg){ .motif }
![](assets/tiling.penrose-p3.svg){ .motif }
![](assets/knot.celtic-grid.svg){ .motif }
![](assets/mandala.svg){ .motif }
</div>

## What it does

The page reads `catalog.json` — the registry serialized at build time —
and builds its controls from it, so it knows every motif, every family and
every parameter the way the CLI does.

A pair of **Design / Animate** tabs at the top of the page picks the
working mode. Both share the same canvas, the same coordinate grid, and
the same parameter sliders; only the right-hand panel swaps.

### The stage

- A real **coordinate plane** sits behind the motif: major and minor
  gridlines in "nice" steps, the x and y axes through the origin with
  arrowheads, and tick labels in the live viewBox units. It recomputes on
  every zoom and pan, so the grid always matches the picture.
- A **cursor coordinate readout** pinned to the bottom-left of the stage
  shows `x: 123.4  y: -56.7` in viewBox units under the pointer; a
  **zoom indicator** on the bottom-right (`1.2x`) tracks the current
  magnification. Both are click-through, so they never catch a pan or a
  zoom drag.
- The **stage toolbar** is just the view: `[−] [fit] [+]` zoom cluster, a
  separator, and `[grid] [axes] [labels]` toggles that flip the three
  layers of the coordinate plane (all three persist in `localStorage`).
  Under 50rem the toggles collapse into a gear popover.
- **Zoom, pan, fit-to-view**, and the **light/dark theme** toggle in the
  header. The theme persists and follows the OS when no manual choice is
  stored.
- A **docs** link in the header returns to this page.

### Design mode

- **Browse** the 147 motifs by family or by keyword search (`/` focuses the
  search box).
- **Adjust** every swappable parameter: range sliders for numerics,
  dropdowns for `Literal` choices, toggles for booleans, x/y pairs for
  `Point`, four-field inputs for `Bounds`. Every control contributes to
  one combined state, so the canvas always reflects the union — the
  1.1.0 limitation, where moving a second slider snapped the first back
  to its default, is gone.
- **Render live** in the browser, debounced so drags stay smooth, and
  cached in an in-page LRU so revisiting a slider position is instant.
- **Copy a `geomotif render` command** that tracks the live state exactly,
  using the CLI's own flag names — it is always paste-ready.
- **Share a URL** with the motif and its parameters baked into the
  fragment, so a colleague lands on the same picture.
- **Export** to SVG, PNG, or the spec JSON that feeds
  `geomotif render --spec`.

### Animate mode

Click the **Animate** tab to flip the right panel from the Design sliders
to the animator. The parameter sliders stay (they are now the keyframe
value inputs), and a scrubber appears directly under the canvas. That row
is the master clock: **play** / **loop** sit beside the range scrub and the
`t = 0.000` readout, so the whole transport is next to the picture.

- The motif's current parameter values become **keyframe 0** at `t = 0`.
- A **track** appears per animatable parameter, plus a `frames` / `fps` /
  `hold` / easing transport row under a **Playback** heading, and the
  existing **draw-on** (pen reveal) and **spin** (rotate the whole design)
  motion primitives appear under a **Motion overlays** heading.
- **Drop keyframes** three ways: the prominent **Set keyframe at t=…**
  button at the top of the tracks drops one for every animatable parameter
  at the scrubber's current time; each track's own **+** button drops a
  single keyframe for that parameter; and double-clicking a lane is the
  power-user shortcut (a faint `dblclick to drop` hint appears on hover).
  The big button's `t=` reads the live scrubber time so it always tells
  you what you will get.
- Drag the scrubber under the canvas to a new time, adjust any slider, and
  drop. Numeric parameters interpolate component-wise with an easing curve
  from `geomotif.core.spacing` (`linear`, `quadratic`, `cubic`,
  `sinusoidal`, `exponential`, `circular`); `bool`, `Literal` and `str`
  parameters **step** at the next keyframe. Per-track easing overrides the
  global one.
- An **empty-state hint** (`Move the scrubber to a time -> adjust the
  sliders -> click "Set keyframe", then press play`) appears when no track
  has a keyframe yet, and disappears the moment one lands.
- Frames render ahead of time in chunked `requestAnimationFrame` batches
  so the UI never freezes; a thin progress bar covers the cold render. The
  stage stays on the scrubber's frame until you press **play** — entering
  Animate or adjusting a parameter never starts motion on its own.
- **Export** the animation as a **GIF** — byte-identical to
  `geomotif render <motif> --out x.gif --animation spec.json` — and the
  spec JSON of the current timeline, both from the animator's export row.
- **Share the animation** in a URL: the full recipe (motif + params +
  keyframes + easing + frames + fps + hold + overlays) is compressed with
  `lz-string` into the `a=` fragment alongside the still `m=` fragment.
  Landing on a shared animation URL boots straight into Animate mode
  with the timeline populated. When a recipe is too large for a URL, the
  share button falls back to copying the spec JSON, which feeds the CLI's
  `--animation` flag directly.
- Picking a new motif from the list while in Animate mode stays in
  Animate, re-entering it on the new motif with a fresh default timeline.

## Round-trip with the CLI

Because the browser runs the same wheel the CLI uses, anything the page
produces reproduces on the command line:

```bash
# A still the share URL points at:
geomotif render rose --n 5 --k 6 --out rose.svg

# An animation the share URL encodes:
geomotif render --out anim.gif --animation spec.json
```

The spec JSON the page exports is the same file the CLI's `--spec` and
`--animation` flags read; the GIF it writes is byte-identical to the one
the page downloads.

## Where it cannot (yet) go

- **scipy motifs** (the `voronoi` family) cannot run under Pyodide, so
  they show a "needs scipy — try locally" badge instead of rendering, in
  both still and animation modes.
- **Timeline editing on touch** is awkward; touch devices get a read-only
  timeline (scrub and play) with an "edit on desktop" hint, so the
  `Set keyframe` button, the per-track `+`, and the double-click hint are
  hidden on touch.

[Open the explore stage &rarr;](https://pianosuki.github.io/geomotif/explore/){ .md-button .md-button--primary }
