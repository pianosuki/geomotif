"""An explorable gallery: one page, sliders, and every picture already drawn.

The catalog's parameters are the interesting part and a static gallery cannot
show them. What ``k`` does to a rose, what ``depth`` does to a dragon and what
``factor`` does to a times-table circle are all things you learn by dragging a
slider and watching, and never by reading a default value.

So: a page you can drag. It has no server, no build step and no JavaScript
library -- every frame is **rendered ahead of time** by geomotif's own SVG
writer and embedded in the document, and the sliders only choose which one is
showing. That means the page works from a file:// URL, inside a zip, and with
nothing installed and no network::

    geomotif explore rose fractal.dragon --out explore.html
    geomotif explore --family spiral --out spirals.html

**One parameter moves at a time.** Rendering every combination of five
parameters would be a combinatorial explosion and a hundred-megabyte file, so
each slider sweeps *its own* parameter with the others left at the motif's
example values. The page says so; it is the honest limit of pre-rendering, and
in exchange one motif is a few hundred kilobytes rather than the product of
every slider's length. ``--samples`` trims a dense one further.

Numbers and booleans get sliders. A parameter that is a point, a set of
coordinates or another motif does not -- there is no single axis to drag it
along -- and is listed on the page as fixed, exactly as the command line
reports the same parameters as not settable.
"""

from __future__ import annotations

import html
import pathlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .core import registry
from .io.svg import to_svg

if TYPE_CHECKING:
    from collections.abc import Sequence
    from os import PathLike

    from .core.registry import MotifInfo, ParamInfo

__all__ = ["DEFAULT_SIZE", "DEFAULT_STEPS", "Sweep", "save_html", "sweeps_for", "to_html"]

#: How many values a slider offers. Odd, so the motif's own example value sits
#: exactly in the middle and the page opens on the picture the gallery shows.
DEFAULT_STEPS = 9

#: Canvas for each frame, in SVG user units.
DEFAULT_SIZE = 340

#: How far a slider reaches either side of the example value, as a multiple of
#: it. Small enough that the interesting range is not squeezed into two steps,
#: wide enough to show the parameter actually doing something.
_SPREAD = 2.0

#: Coordinate precision for an embedded frame. These are display sizes, so a
#: second decimal is a hundredth of a pixel, and a page holds a frame per step
#: per parameter.
_PRECISION = 1

#: The largest frame worth embedding, in bytes. A depth parameter can double
#: its geometry every step, so the top of that slider is a frame large enough
#: to stop the page opening. Dropping those leaves the slider ending where the
#: drawing does.
_MAX_FRAME = 250_000


@dataclass(frozen=True, slots=True)
class Sweep:
    """One parameter, the values it was drawn at, and the drawings."""

    parameter: str
    values: tuple[object, ...]
    #: The frames, as ``<svg>`` elements ready to sit inside a page.
    images: tuple[str, ...]
    #: Index of the motif's own example value, where the slider starts.
    start: int


def to_html(
    names: Sequence[str],
    *,
    steps: int = DEFAULT_STEPS,
    size: int = DEFAULT_SIZE,
    samples: int | None = None,
    title: str = "geomotif",
) -> str:
    """Render an explorable page for one or more registered motifs.

    Parameters
    ----------
    names : sequence of str
        Registered motif names. Several become a picker beside the sliders.
    steps : int
        Values per slider. Must be >= 2; odd values put the motif's own
        example in the middle.
    size : int
        Canvas for each frame, in SVG user units.
    samples : int, optional
        Resample every frame to this many points. Worth setting for a dense
        motif: the page holds ``steps`` frames per parameter, and it is the
        vertices that make it large.
    title : str
        The document's title.

    Returns
    -------
    str
        A complete, self-contained HTML document.

    Raises
    ------
    ValueError
        If no names are given, or none of them could be drawn.
    KeyError
        If a name is not registered.
    """
    if not names:
        raise ValueError("cannot explore nothing: name at least one motif")
    if steps < 2:
        raise ValueError(f"steps must be >= 2, got {steps}")

    panels = [
        (info, sweeps_for(info, steps=steps, size=size, samples=samples))
        for info in (registry.describe(name) for name in names)
        if info.available
    ]
    drawable = [(info, sweeps) for info, sweeps in panels if sweeps]
    if not drawable:
        raise ValueError(
            f"none of {list(names)} has a parameter that can be swept; every one of "
            f"them is defined by values a slider cannot move along"
        )
    return _document(drawable, title=title, size=size)


def save_html(names: Sequence[str], path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Write an explorable page and return the path written.

    Keyword arguments are passed straight through to :func:`to_html`.
    """
    target = pathlib.Path(path)
    target.write_text(to_html(names, **kwargs), encoding="utf-8")
    return target


def sweeps_for(
    info: MotifInfo,
    *,
    steps: int = DEFAULT_STEPS,
    size: int = DEFAULT_SIZE,
    samples: int | None = None,
) -> tuple[Sweep, ...]:
    """Render one sweep per parameter of a motif that a slider can move.

    A value the motif refuses -- a modulus of one, a depth of zero -- is
    dropped rather than reported: the sweep is generated from a range rather
    than chosen from one, so hitting the edge of what a motif accepts is
    expected, and the parameter simply offers the values that worked.
    """
    sweeps: list[Sweep] = []
    for param in info.params:
        values = _values_for(param, info, steps)
        if not values:
            continue
        drawn = [(value, _draw(info, param.name, value, size, samples)) for value in values]
        kept = [(value, image) for value, image in drawn if image is not None]
        if len(kept) < 2:
            continue
        base = _default_for(param, info)
        sweeps.append(
            Sweep(
                parameter=param.name,
                values=tuple(value for value, _ in kept),
                images=tuple(image for _, image in kept),
                start=_nearest(base, [value for value, _ in kept]),
            )
        )
    return tuple(sweeps)


# --- working out what to draw -------------------------------------------------


def _default_for(param: ParamInfo, info: MotifInfo) -> object:
    """Return where a slider starts: the example's value, else the declared one."""
    return info.example.get(param.name, param.default)


def _values_for(param: ParamInfo, info: MotifInfo, steps: int) -> Sequence[object]:
    """Return the values to try for one parameter, or ``[]`` if it has no axis.

    A parameter that declared a :class:`~geomotif.Range` on its field metadata
    is swept across that range -- the motif's own bound, not a guess. Anything
    without one falls back to the ``_SPREAD`` heuristic around the default, so
    the page is usable even before every motif is curated.
    """
    base = _default_for(param, info)
    if param.annotation == "bool":
        return [False, True]
    if param.min is not None and param.max is not None:
        return _ranged(param, base, steps)
    # A slider needs somewhere to start. A number whose default is None -- the
    # adaptive `resolution` every parametric motif carries -- gives no clue what
    # scale it lives at, and guessing produces a slider from 1 to 2.
    match (param.annotation, base):
        case ("int" | "int | None", int()):
            return _integers(base, steps)
        case ("float" | "float | None", int() | float()):
            return _floats(float(base), steps)
        case _:
            return []


def _ranged(param: ParamInfo, base: object, steps: int) -> Sequence[object]:
    """Return values across a declared ``Range``, including the motif's default.

    An integer parameter with a ``step`` is walked in whole steps so the slider
    never offers a fractional petal count; a float is spaced linearly across
    the range, which is the honest shape of a bound the motif itself declared
    (the geometric ``_SPREAD`` spread is for guessed ranges, where doubling is
    the same size of change as halving).
    """
    # ``_values_for`` only routes here when both bounds are set, so neither is
    # None at this point; narrowing them locally keeps the call site readable.
    low = float(param.min)  # type: ignore[arg-type]
    high = float(param.max)  # type: ignore[arg-type]
    if param.annotation in ("int", "int | None") and param.step is not None:
        # Walk in whole steps so the slider never offers a fractional count, but
        # subsample to ``steps`` values when the range is wider than that -- a
        # 1-50 range with 7 steps gives 7 evenly-spaced integers, not 50.
        step = max(1, round(param.step))
        start = round(low)
        stop = round(high)
        every = list(range(start, stop + 1, step)) or [start]
        if len(every) > steps:
            span = len(every) - 1
            every = [every[round(span * i / (steps - 1))] for i in range(steps)]
        if isinstance(base, int):
            every = sorted(set(every) | {base})
        return every
    grid = [round(low + (high - low) * i / (steps - 1), 6) for i in range(steps)]
    if isinstance(base, int | float):
        grid = sorted(set(grid) | {float(base)})
    return grid


def _integers(base: int, steps: int) -> Sequence[object]:
    """Return whole numbers around ``base``, distinct and at least one."""
    low = max(1, int(base / _SPREAD))
    high = max(low + 1, int(base * _SPREAD))
    span = high - low
    seen = {low + round(span * i / (steps - 1)) for i in range(steps)}
    return sorted(seen | {base})


def _floats(base: float, steps: int) -> Sequence[object]:
    """Return values around ``base``, geometrically, so ``base`` is the middle one.

    Geometric rather than linear because these are scales -- a radius, a
    growth rate, a span -- and halving is the same size of change as doubling.
    It also puts the motif's own value exactly at the middle of the slider,
    which linear spacing between ``base/2`` and ``base*2`` does not.
    """
    if base == 0.0:
        # Nothing to scale. A span either side of zero is the only sensible
        # guess, and it at least shows the parameter doing something.
        step = 2.0 / (steps - 1)
        return [round(-1.0 + step * i, 6) for i in range(steps)]
    return sorted(round(base * _SPREAD ** (2.0 * i / (steps - 1) - 1.0), 6) for i in range(steps))


def _nearest(base: object, values: Sequence[object]) -> int:
    """Return the index of whichever value is closest to where the motif started."""
    if not isinstance(base, int | float):
        return 0
    numbers = [(index, v) for index, v in enumerate(values) if isinstance(v, int | float)]
    if not numbers:
        return 0
    return min(numbers, key=lambda item: abs(item[1] - base))[0]


def _draw(
    info: MotifInfo,
    parameter: str,
    value: object,
    size: int,
    samples: int | None,
) -> str | None:
    """Return one frame's SVG, or ``None`` if the motif refused the value."""
    try:
        motif = registry.create(info.name, **{**info.example, parameter: value})
        design = motif.generate(samples) if samples else motif.build()
        frame = to_svg(design, width=size, height=size, precision=_PRECISION, title=None)
        return _inline(frame) if len(frame) <= _MAX_FRAME else None
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError):
        # Motifs validate their parameters, and sweeping a range walks off the
        # end of what several of them accept. That is data about the motif, not
        # an error in the page.
        return None
    except RecursionError:  # pragma: no cover -- a deep enough L-system
        return None


# --- the page -----------------------------------------------------------------


def _document(
    panels: Sequence[tuple[MotifInfo, tuple[Sweep, ...]]], *, title: str, size: int
) -> str:
    """Assemble the whole single-file document."""
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        "<p class=note>Every frame here was drawn ahead of time by geomotif's own SVG "
        "writer and embedded in this file. Each slider sweeps its own parameter with "
        "the others left at the motif's example values.</p>",
    ]
    if len(panels) > 1:
        lines.append("<nav>")
        lines.extend(
            f'<button data-motif="{html.escape(info.name)}">{html.escape(info.name)}</button>'
            for info, _ in panels
        )
        lines.append("</nav>")

    for index, (info, sweeps) in enumerate(panels):
        lines.append(_panel(info, sweeps, size=size, shown=index == 0))

    lines += [f"<script>{_SCRIPT}</script>", "</body>", "</html>", ""]
    return "\n".join(lines)


def _panel(info: MotifInfo, sweeps: Sequence[Sweep], *, size: int, shown: bool) -> str:
    """Return one motif's section: its pictures, its sliders and its prose."""
    name = html.escape(info.name)
    parts = [f'<section class="motif{" on" if shown else ""}" id="{name}" data-motif="{name}">']
    parts.append(f"<h2><code>{name}</code></h2>")
    parts.append(f"<p class=summary>{html.escape(info.summary)}</p>")
    parts.append("<div class=layout>")

    parts.append(f'<div class=stage style="max-width:{size}px">')
    for sweep in sweeps:
        parameter = html.escape(sweep.parameter)
        for index, image in enumerate(sweep.images):
            state = " on" if sweep is sweeps[0] and index == sweep.start else ""
            parts.append(
                f'<div class="frame{state}" data-param="{parameter}" data-index="{index}">'
                f"{image}</div>"
            )
    parts.append("</div>")

    parts.append("<div class=controls>")
    for sweep in sweeps:
        parameter = html.escape(sweep.parameter)
        # The values ride on the slider itself rather than in a script block:
        # they are numbers and booleans, the page has no other data, and an
        # attribute is one less thing that has to parse before anything works.
        values = html.escape(",".join(str(value) for value in sweep.values), quote=True)
        # A boolean parameter's flag is --x or --no-x, never "--x False", which
        # is what argparse's BooleanOptionalAction accepts and what the command
        # line under the sliders therefore has to write.
        boolean = " data-boolean" if all(isinstance(v, bool) for v in sweep.values) else ""
        parts.append(
            f"<label><span class=name>{parameter}</span>"
            f'<input type=range min=0 max="{len(sweep.values) - 1}" value="{sweep.start}" '
            f'data-param="{parameter}" data-values="{values}"{boolean}>'
            f'<output data-for="{parameter}">{html.escape(str(sweep.values[sweep.start]))}</output>'
            "</label>"
        )
    parts.append(f'<pre class=command data-name="{name}">geomotif render {name}</pre>')

    fixed = [p.name for p in info.params if p.name not in {s.parameter for s in sweeps}]
    if fixed:
        parts.append(
            "<p class=fixed>Held at the example's values, because a slider has no axis "
            f"to move them along: <code>{html.escape(', '.join(fixed))}</code></p>"
        )
    parts.append("</div></div></section>")
    return "\n".join(parts)


def _inline(document: str) -> str:
    """Return an SVG document as an element that can sit inside a page.

    The XML declaration is dropped -- it is only legal at the very start of a
    file -- and everything else is already valid HTML5.
    """
    body = document.strip()
    if body.startswith("<?xml"):
        body = body.split("?>", 1)[1].lstrip()
    return body


_STYLE = """
:root { color-scheme: light dark; --ink: #0b0b0b; --page: #f9f9f7; --muted: #6d6c68;
        --line: #d9d8d2; --panel: #fcfcfb; }
@media (prefers-color-scheme: dark) {
  :root { --ink: #f2f2ef; --page: #14141a; --muted: #9a99a3; --line: #2c2c36;
          --panel: #1b1b22; }
}
* { box-sizing: border-box; }
body { margin: 0 auto; padding: 2rem 1.25rem 4rem; max-width: 60rem; background: var(--page);
       color: var(--ink); font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; letter-spacing: -.01em; }
h2 { font-size: 1.1rem; margin: 0 0 .25rem; font-weight: 600; }
code, pre { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: .85em; }
.note, .summary, .fixed { color: var(--muted); margin: .25rem 0 1rem; font-size: .9rem; }
nav { display: flex; flex-wrap: wrap; gap: .4rem; margin: 1rem 0 1.5rem; }
nav button { padding: .35rem .7rem; border: 1px solid var(--line); border-radius: 999px;
             background: var(--panel); color: inherit; font: inherit; font-size: .85rem;
             cursor: pointer; }
nav button.on { background: var(--ink); color: var(--page); border-color: var(--ink); }
section.motif { display: none; }
section.motif.on { display: block; }
.layout { display: flex; flex-wrap: wrap; gap: 2rem; align-items: flex-start; }
.stage { flex: 1 1 320px; position: relative; border: 1px solid var(--line);
         border-radius: 6px; background: var(--panel); padding: .5rem; }
.stage::after { content: ""; display: block; padding-bottom: 100%; }
.frame { display: none; position: absolute; inset: .5rem; }
.frame.on { display: block; }
.frame svg { width: 100%; height: 100%; }
@media (prefers-color-scheme: dark) { .frame svg { filter: invert(1); } }
.controls { flex: 1 1 260px; }
label { display: grid; grid-template-columns: 7rem 1fr 4rem; align-items: center;
        gap: .5rem; margin-bottom: .6rem; }
label .name { font-family: ui-monospace, Menlo, monospace; font-size: .8rem; }
input[type=range] { width: 100%; accent-color: var(--ink); }
output { font-family: ui-monospace, Menlo, monospace; font-size: .8rem; text-align: right;
         color: var(--muted); }
pre.command { margin: 1.25rem 0 0; padding: .6rem .75rem; border: 1px solid var(--line);
              border-radius: 6px; background: var(--panel); overflow-x: auto; }
""".strip()

_SCRIPT = """
document.querySelectorAll('nav button').forEach(function (button) {
  button.addEventListener('click', function () {
    var wanted = button.dataset.motif;
    document.querySelectorAll('nav button').forEach(function (other) {
      other.classList.toggle('on', other === button);
    });
    document.querySelectorAll('section.motif').forEach(function (section) {
      section.classList.toggle('on', section.dataset.motif === wanted);
    });
  });
});
document.querySelector('nav button')?.classList.add('on');

document.querySelectorAll('section.motif').forEach(function (section) {
  var values = {};
  var booleans = {};
  section.querySelectorAll('input[type=range]').forEach(function (slider) {
    values[slider.dataset.param] = slider.dataset.values.split(',');
    booleans[slider.dataset.param] = slider.dataset.boolean !== undefined;
  });
  var command = section.querySelector('pre.command');

  function show(param, index) {
    section.querySelectorAll('.frame').forEach(function (frame) {
      frame.classList.toggle(
        'on', frame.dataset.param === param && Number(frame.dataset.index) === index
      );
    });
    var name = param.replace(/_/g, '-');
    var value = values[param][index];
    // A boolean is --x or --no-x; everything else is --x value.
    var flag = booleans[param]
      ? (value === 'True' ? '--' + name : '--no-' + name)
      : '--' + name + ' ' + value;
    command.textContent = 'geomotif render ' + command.dataset.name + ' ' + flag;
  }

  section.querySelectorAll('input[type=range]').forEach(function (slider) {
    slider.addEventListener('input', function () {
      var param = slider.dataset.param;
      var index = Number(slider.value);
      section.querySelector('output[data-for="' + param + '"]').textContent =
        values[param][index];
      show(param, index);
    });
  });
});
""".strip()
