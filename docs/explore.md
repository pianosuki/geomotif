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
</div]

## What it does

The page reads `catalog.json` — the registry serialized at build time —
and builds its controls from it, so it knows every motif, every family and
every parameter the way the CLI does.

### Still mode

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
- **Zoom, pan, fit-to-view**, and toggle the dot grid, the stage border,
  and the light/dark theme — the last persists and follows the OS when no
  manual choice is stored.

### Animation mode

The stage has a **Play** toggle that flips the bottom panel from sliders
to a timeline. When you enter it:

- The motif's current parameter values become **keyframe 0** at `t = 0`.
- A **track** appears per animatable parameter, plus a global scrubber and
  a `frames` / `fps` / `hold` / easing transport row.
- Drag the scrubber to a new time, adjust any slider, and **drop a
  keyframe** (a dot on that track at that time). Numeric parameters
  interpolate component-wise with an easing curve from
  `geomotif.core.spacing` (`linear`, `quadratic`, `cubic`, `sinusoidal`,
  `exponential`, `circular`); `bool`, `Literal` and `str` parameters
  **step** at the next keyframe. Per-track easing overrides the global
  one.
- The existing motion primitives — **draw-on** (pen reveal) and **spin**
  (rotate the whole design) — are exposed as overlay checkboxes that
  compose with the parameter keyframes, so a Hilbert curve can draw itself
  on while its `depth` sweeps from 3 to 6.
- Frames render ahead of time in chunked `requestAnimationFrame` batches
  so the UI never freezes; a thin progress bar covers the cold render and
  playback starts as soon as the first frame is ready.
- **Export** the animation as a **GIF** — byte-identical to
  `geomotif render <motif> --out x.gif --animation spec.json`.
- **Share the animation** in a URL: the full recipe (motif + params +
  keyframes + easing + frames + fps + hold + overlays) is compressed with
  `lz-string` into the `a=` fragment alongside the still `m=` fragment.
  Landing on a shared animation URL boots straight into animation mode
  with the timeline populated. When a recipe is too large for a URL, the
  share button falls back to copying the spec JSON, which feeds the CLI's
  `--animation` flag directly.

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
  timeline (scrub and play) with an "edit on desktop" hint.

[Open the explore stage &rarr;](https://pianosuki.github.io/geomotif/explore/){ .md-button .md-button--primary }
