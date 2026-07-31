# The command line

Installing geomotif installs a `geomotif` command. It is pure `argparse`, so
the zero-dependency promise survives the CLI as well as the library.

```bash
geomotif list                                   # every motif, grouped by family
geomotif list --family fractal
geomotif show rose                              # docs, parameters, defaults
geomotif render rose --n 5 --samples 400 --out rose.svg
geomotif render spiral.golden --samples 300 --ease power:2.5 --out s.csv
geomotif render fractal.hilbert --depth 6 --out h.dxf --fit 800x800
geomotif render --spec my-design.json --out out.svg
geomotif render tiling.truchet --out plot.svg --paper a4 --optimize
geomotif render fractal.hilbert --out h.gif --frames 60   # an animation
geomotif explore rose --out rose.html           # sliders for its parameters
geomotif gallery --out gallery                  # all 147, plus a manifest
geomotif demo                                   # the spacing showcase (needs matplotlib)
```

`python -m geomotif` is the same command, for when the script is not on the
path.

## Where the flags come from

A motif's flags are **generated from its dataclass fields** — the same
declaration that drives `describe()`, the spec format and the documentation.
Nothing is written twice.

```console
$ geomotif show rose
rose  (polar)

  The rhodonea `r = cos(n/d * theta)`, with the petal count right.
  ...

parameters:
  --n           int               default: 5
  --d           int               default: 1
  --size        float             default: 100.0
  --center      Point             default: (0.0, 0.0)
  --resolution  int | None        default: None

example:
  geomotif render rose --out rose.svg
```

`geomotif render NAME --help` prints the same list as argparse help. Two things
follow from generating the flags rather than writing them, and both are worth
knowing before they surprise you.

### Not every parameter can be said on a command line

A motif parameterized by a Python function, by another motif, or by a whole
point set has no sensible flag. Those take their value from the motif's
**registered example** instead, so every motif in the catalogue still renders:

```bash
geomotif render voronoi.cells --inset 0.2
```

gives you the example's point set and *your* inset. `geomotif show NAME` lists
what it could not offer, under "not settable from the command line".

The same rule is why `--n 7` on a rose changes one thing about the rose in the
gallery rather than silently rendering a different one: flags start from the
example, not from the class defaults.

### The sampling options have unobvious names

A generic option and a motif parameter share one argparse namespace, and
`points`, `count`, `step`, `spacing`, `seed`, `size`, `width`, `height`, `gap`,
`curve`, `spread` and `resolution` are all parameter names somewhere in the
catalogue. So the sampling options are:

| Option | Means |
|---|---|
| `--samples N` | resample to N points |
| `--stride D` | a point every D units of real distance |
| `--ease CURVE` | the spacing curve |

The full reserved list is `geomotif.cli.RESERVED`, and a test asserts that no
builtin motif collides with it.

`--ease` takes a `name[:arg[:arg]]` mini-syntax whose arguments go to the
constructor positionally, because each spacing class already declares them in
the order you would say them:

```bash
--ease linear
--ease power:2.5
--ease exp:out:6
--ease smoothstep
```

## Output

The suffix of `--out` picks the writer:

| Suffix | Writer |
|---|---|
| `.svg` | SVG |
| `.dxf` | DXF R12 |
| `.csv`, `.txt`, `.tsv`, `.json` | the structured design writer |
| `.gif` | an animation — see `--motion`, `--frames` and `--fps` |
| `.png`, `.pdf`, `.jpg` | matplotlib — the one part of the CLI that needs the `plot` extra |

Without `--out`, the points go to stdout as CSV, so the command pipes:

```bash
geomotif render spiral.golden --samples 50 | tail -n +2 | while IFS=, read x y; do
  echo "place $x $y"
done
```

`--fit 800x600` scales onto a canvas, `--precision N` sets the decimals written,
and `--title` sets the SVG document title or the figure title.

`--snap STEP` puts every coordinate on a grid of that size — `--snap 0.5` for
half units, `--snap 5` for a five-unit lattice, neither of which `--precision`
can express. It runs last, after `--fit`, so the grid is the one the file is
actually written on. `--snap-mode` chooses which way a point between two grid
lines goes (`half-even`, the default, then `half-up`, `floor`, `ceil`,
`trunc`), and `--keep-duplicates` keeps the points a coarse grid stacked up
rather than dropping them:

```bash
geomotif render spiral.golden --samples 300 --snap 1 --precision 0 > whole.csv
```

`--snap` pairs with `--precision 0`, which writes `3` rather than `3.0`. It is
exact for the coordinate formats and `.dxf`; `.svg` output, `--paper` included,
fits the design into its canvas as it writes and rescales the grid away — see
[Snapping to a grid](export.md#snapping-to-a-grid).

For a plotter, `--paper a4` writes the SVG in real millimetres (with
`--landscape` for the other way up) and `--optimize` joins strokes that meet and
orders them so the pen travels less — see [Plotting it for
real](plotter.md):

```bash
geomotif render tiling.truchet --out plot.svg --paper a4 --optimize
```

For an animation, `--out something.gif` with `--motion draw-on` (the default) or
`--motion spin`, plus `--frames` and `--fps` — see [Animation](animation.md).

!!! tip "Negative coordinates"

    `--region -60,-60,60,60` works. argparse would normally read that value as
    another option, since it starts with a dash and is not a plain negative
    number; options known to take coordinates get their value glued on with `=`
    before parsing, so both the spaced and the `--region=-60,...` forms work.

## Rendering from a spec

`--spec` reads the motif from a [spec file](export.md#specs-the-recipe-not-the-points)
instead of the command line, which is how you keep a design around and change
your mind about the resolution later:

```bash
geomotif render --spec my-design.json --samples 4000 --out big.svg
```

## The explore command

```bash
geomotif explore rose --out rose.html
geomotif explore --family spiral --out spirals.html --steps 7
```

writes a single self-contained HTML page with a **slider for every parameter a
slider can move**. Every frame is rendered ahead of time by geomotif's own SVG
writer and embedded in the document, so the page needs no server, no build step
and no JavaScript library, and works from a `file://` URL forever.

One parameter moves at a time: each slider sweeps its own with the others left
at the motif's example values. Rendering every *combination* would be a
combinatorial explosion and a hundred-megabyte file; this way a motif costs a
few hundred kilobytes and opens instantly. `--samples N` resamples each frame if
that is still too much, and `--steps` sets how many values a slider offers.

Numbers and booleans get sliders. A parameter that is a point, a set of
coordinates or another motif does not — there is no single axis to drag it along
— and the page lists it as held still.

## The gallery command

```bash
geomotif gallery --out gallery --size 320
```

renders every available motif to SVG at its registered example, and writes a
`manifest.json` beside them holding each one's name, family, summary and spec.
All 147 take about two seconds. On an install without the optional extras it
writes what it can and reports the rest as skipped rather than failing.

The [documentation gallery](../gallery/index.md) is the same idea with pages
around it: `tools/gendocs.py` walks the registry the same way and writes the
Markdown as well as the SVGs.
