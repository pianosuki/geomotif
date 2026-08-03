"use strict";

// Python render bridge: runs in Pyodide once and exposes render_motif /
// export_png / build_keyframes / render_stored_frame / export_gif to JS. The
// same exception set explore._draw guards is caught and surfaced as a friendly
// inline error rather than a thrown promise rejection. export_stored_png
// renders the *current animation frame* (the design already stashed by
// build_keyframes) so the PNG export in animation mode matches what the
// scrubber is showing, not the last still render.

(function (E) {
  const { PYODIDE_VERSION, CACHE_SIZE } = E;

  const PY_CODE = `
import json
from xml.sax.saxutils import escape as _esc_html, quoteattr
from geomotif.core.registry import NAME_KEY
from geomotif.core.style import (
    by_layer as _by_layer,
    layer_names as _layer_names,
    point_styles_of as _point_styles_of,
    styles_of as _styles_of,
)
from geomotif.io.spec import from_spec
from geomotif.io.png import to_png
from geomotif.core.transform import Affine

_EXC = (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RecursionError)

# The display canvas. The display renderer maps the world coordinate plane
# (y up, origin at 0,0) onto this canvas with a fixed per-motif scale (see
# _scale_for below), the world origin anchored at the canvas centre (260, 260).
# Because the mapping is fixed, a slider change *visibly rescales* the picture
# instead of being re-fit to the box on every render, and the grid / readout
# can translate between world and screen. _PAD is the margin an example fills
# to, so a default motif sits comfortably inside the square.
_W, _H, _PREC = 520, 520, 1
_PAD = 40

# Per-motif display scale, computed once from the registered example design
# and cached. The example is what the gallery shows and what the SPA seeds its
# sliders with, so by construction the motif fills the canvas nicely at its
# default state -- and stays at the same scale when sliders move it.
_EXAMPLE_SCALES = {}

def _example_scale(name, example_json):
    s = 1.0
    try:
        params = json.loads(example_json) if example_json else {}
        motif = from_spec({"motif": name, "params": params})
        bounds = motif.build().bounds
        # Scale so the example's own radius around the world origin fills the
        # canvas: the world origin stays at (260, 260) and nothing is clipped
        # even for a motif drawn off-centre (e.g. a cardioid). For an
        # origin-centred motif this equals extent -> _W - 2*_PAD; for an
        # off-centre one it zooms out just far enough that the whole example
        # is visible.
        radius = max(abs(bounds.min_x), abs(bounds.max_x),
                     abs(bounds.min_y), abs(bounds.max_y))
        if not radius > 0:
            radius = max(bounds.width, bounds.height) / 2.0
        if radius > 0:
            s = (_W - 2 * _PAD) / (2.0 * radius)
    except _EXC:
        pass
    return s if s > 0 else 1.0

def _scale_for(name, example_json):
    if name not in _EXAMPLE_SCALES:
        _EXAMPLE_SCALES[name] = _example_scale(name, example_json)
    return _EXAMPLE_SCALES[name]

# Map a world-space design into display space: flip to y-down, then scale by
# the fixed per-motif factor and translate the world origin to the canvas
# centre. Returns (placed design, scale) so the JS side can drive the grid,
# the readout and the zoom indicator from the live scale.
def _placed(design, name, example_json):
    s = _scale_for(name, example_json)
    affine = Affine.translate(_W / 2.0, _H / 2.0) @ Affine.scale(s)
    return design.flipped_y().transformed(affine), s

# Paint the display SVG. to_svg fits and *re-bases* the design (its fit() moves
# the min corner to 0,0), which would shift the world origin away from the
# canvas centre and put the grid / readout out of step with the picture. So the
# placed coordinates are written verbatim onto a fixed 520x520 canvas instead:
# the world origin stays exactly at (260, 260) for every motif, and the natural
# viewBox is always the full 520x520 square, so the grid covers the whole stage
# at fit-to-view rather than only the motif's own bounds rectangle. The motif's
# own display-space bounds are returned alongside so the SPA's "fit to view"
# can frame the *drawn picture* whenever its size changes with a parameter.
def _display_svg(placed, s):
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" '
             'width="520" height="520" viewBox="0 0 520 520">']
    title = str(placed.meta.get(NAME_KEY, "") or "") if hasattr(placed, "meta") else ""
    if title:
        lines.append(f"  <title>{_esc_html(title)}</title>")
    layers = _by_layer(placed) if _layer_names(placed) else {None: placed}
    for name, part in layers.items():
        if name is None:
            lines.extend(_elements(part, "  ", _PREC))
            continue
        lines.append(f'  <g inkscape:groupmode="layer" '
                     f'inkscape:label={quoteattr(str(name))} id={quoteattr(str(name))}>')
        lines.extend(_elements(part, "    ", _PREC))
        lines.append("  </g>")
    lines.append("</svg>")
    b = placed.bounds
    return json.dumps({
        "svg": chr(10).join(lines) + chr(10),
        "scale": s,
        "bounds": {
            "x": float(b.min_x), "y": float(b.min_y),
            "w": float(b.width), "h": float(b.height),
        },
        "error": None,
    })

def _num(value, precision):
    text = f"{value:.{precision}f}"
    if precision > 0:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", "", "-"} else text

def _overrides(style):
    if style is None:
        return ""
    parts = []
    if style.stroke is not None and style.stroke != "#0b0b0b":
        parts.append(f"stroke={quoteattr(style.stroke)}")
    if style.width is not None and style.width != 1:
        parts.append(f'stroke-width="{_num(style.width, 3)}"')
    if style.fill is not None and style.fill != "none":
        parts.append(f"fill={quoteattr(style.fill)}")
    return (" " + " ".join(parts)) if parts else ""

def _strokes(design, precision):
    drawn = []
    for path, style in zip(design.paths, _styles_of(design), strict=True):
        pts = path.points
        coords = [f"{_num(x, precision)} {_num(y, precision)}" for x, y in pts]
        d = f"M {coords[0]}" if len(coords) == 1 else f"M {coords[0]} L {' '.join(coords[1:])}"
        if path.closed and len(coords) > 2:
            d += " Z"
        drawn.append((d, _overrides(style)))
    return drawn

def _elements(part, pad, precision):
    lines = []
    if part.paths:
        lines.append(pad + '<g fill="none" stroke="#0b0b0b" stroke-width="1" '
                        'stroke-linecap="round" stroke-linejoin="round">')
        for d, attrs in _strokes(part, precision):
            lines.append(pad + "  " + f'<path d="{d}"{attrs}/>')
        lines.append(pad + "</g>")
    if part.points:
        lines.append(pad + '<g fill="#0b0b0b" stroke="none">')
        for (x, y), style in zip(part.points, _point_styles_of(part), strict=True):
            radius = style.width if style is not None and style.width is not None else 1.0
            color = ""
            if style is not None and style.stroke is not None and style.stroke != "#0b0b0b":
                color = f" fill={quoteattr(style.stroke)}"
            lines.append(pad + "  " +
                         f'<circle cx="{_num(x, precision)}" cy="{_num(y, precision)}" '
                         f'r="{_num(radius, 3)}"{color}/>')
        lines.append(pad + "</g>")
    return lines

def render_motif(name, params_json, example_json=None):
    try:
        params = json.loads(params_json) if params_json else {}
        motif = from_spec({"motif": name, "params": params})
        design = motif.build()
        placed, s = _placed(design, name, example_json)
        return _display_svg(placed, s)
    except _EXC as e:
        return json.dumps({"svg": None, "scale": None, "error": type(e).__name__ + ": " + str(e)})

# PNG export -- matches the CLI's "geomotif render <motif> --out x.png" default
# styling (canvas 480, ink #0b0b0b, paper #ffffff, thickness 1, padding 8, no
# antialias, zlib 6, truecolor). Returns raw bytes, which Pyodide hands to JS
# as a Uint8Array; the bridge raises and the JS side surfaces the error.
def export_png(name, params_json):
    params = json.loads(params_json) if params_json else {}
    motif = from_spec({"motif": name, "params": params})
    design = motif.build()
    return to_png(
        design,
        width=480, height=480, padding=8.0,
        ink="#0b0b0b", background="#ffffff", thickness=1,
        antialias=False, aa_level=8, color="rgb", compression=6,
    )

# Current-frame PNG in animation mode: the design for frame i was already built
# and stashed by build_keyframes, so there is no from_spec round-trip -- the
# bytes match the frame the scrubber is showing, not the last still state.
def export_stored_png(i):
    try:
        frames = _STORE["frames"]
        if i < 0 or i >= len(frames):
            raise IndexError(f"frame {i} out of range (0..{len(frames)-1})")
        return to_png(
            frames[i],
            width=480, height=480, padding=8.0,
            ink="#0b0b0b", background="#ffffff", thickness=1,
            antialias=False, aa_level=8, color="rgb", compression=6,
        )
    except _EXC as e:
        return json.dumps({"error": type(e).__name__ + ": " + str(e)})

# --- animation bridges -------------------------------------------------------
# build_keyframes runs the Step-7 keyframes primitive (plus any overlay
# post-passes) and stashes the per-frame Designs in a module-global list. The
# SPA then fetches each frame's SVG in chunked rAF batches via
# render_stored_frame, so a 60-frame pre-render never blocks the main thread
# on one giant Pyodide call. export_gif rebuilds the same run and writes it
# through the pure-stdlib geomotif.io.gif.save_gif to the in-memory FS, so
# the downloaded bytes match 'geomotif render --animation spec.json' by
# construction (same primitive, same writer).
from geomotif.animate import (
    compose as _compose,
    draw_on_overlay as _draw_on_overlay,
    keyframes as _keyframes,
    spin_overlay as _spin_overlay,
)
from geomotif.io.gif import save_gif as _save_gif

_STORE = {"frames": (), "name": None, "example": None}

def _overlay_motions(overlays):
    motions = []
    for entry in overlays or []:
        kind = entry.get("type")
        if kind == "draw_on":
            motions.append(_draw_on_overlay(trail=entry.get("trail")))
        elif kind == "spin":
            about = entry.get("about")
            motions.append(_spin_overlay(
                turns=float(entry.get("turns", 1.0)),
                about=tuple(about) if isinstance(about, list) else about,
            ))
    return motions

def build_keyframes(name, params_json, tracks_json, frames, fps, hold, easing, overlays_json, example_json=None):
    try:
        params = json.loads(params_json) if params_json else {}
        tracks = json.loads(tracks_json) if tracks_json else {}
        overlays = json.loads(overlays_json) if overlays_json else []
        motif = from_spec({"motif": name, "params": params})
        built = _keyframes(motif, tracks, frames=int(frames), fps=float(fps),
                           hold=int(hold), easing=str(easing))
        motions = _overlay_motions(overlays)
        if motions:
            built = _compose(motions, built)
        _STORE["frames"] = built
        # Animation frames are built in world coordinates and get the same
        # fixed display mapping as a still, so thread the motif (and its
        # example for the scale cache) through _STORE for render_stored_frame.
        _STORE["name"] = name
        _STORE["example"] = example_json
        return json.dumps({"count": len(built), "error": None})
    except _EXC as e:
        _STORE["frames"] = ()
        return json.dumps({"count": 0, "error": type(e).__name__ + ": " + str(e)})

def render_stored_frame(i):
    frames = _STORE["frames"]
    try:
        if i < 0 or i >= len(frames):
            raise IndexError(f"frame {i} out of range (0..{len(frames)-1})")
        placed, s = _placed(frames[i], _STORE["name"], _STORE["example"])
        return _display_svg(placed, s)
    except _EXC as e:
        return json.dumps({"svg": None, "scale": None, "error": type(e).__name__ + ": " + str(e)})

def clear_stored_frames():
    _STORE["frames"] = ()

# GIF export -- the same run the SPA just played, written with the CLI's
# default export styling so the bytes match 'geomotif render --animation'. The
# writer needs a path; Pyodide mounts an in-memory FS at /tmp, so we write
# there and read the bytes back.
def export_gif(name, params_json, tracks_json, frames, fps, hold, easing, overlays_json):
    try:
        params = json.loads(params_json) if params_json else {}
        tracks = json.loads(tracks_json) if tracks_json else {}
        overlays = json.loads(overlays_json) if overlays_json else []
        motif = from_spec({"motif": name, "params": params})
        built = _keyframes(motif, tracks, frames=int(frames), fps=float(fps),
                           hold=int(hold), easing=str(easing))
        motions = _overlay_motions(overlays)
        if motions:
            built = _compose(motions, built)
        _save_gif(built, "/tmp/geomotif_explore.gif",
                  width=480, height=480, fps=float(fps), loop=0,
                  ink="#0b0b0b", background="#ffffff", thickness=1,
                  padding=8.0, antialias=False, aa_level=8, dither=True,
                  transparent=False)
        with open("/tmp/geomotif_explore.gif", "rb") as fh:
            return fh.read()
    except _EXC as e:
        return json.dumps({"error": type(e).__name__ + ": " + str(e)})
`;

  E.PY_CODE = PY_CODE;

  // --- Pyodide loader ----------------------------------------------------------
  async function ensurePyodide() {
    if (E.pyPromise) return E.pyPromise;
    E.pyPromise = (async () => {
      E.showToast("loading Pyodide…");
      E.showProgress(0.1);
      await loadScript(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.js`);
      E.showProgress(0.3);
      // eslint-disable-next-line no-undef
      E.pyodide = await loadPyodide();
      E.showProgress(0.55);
      E.showToast("loading geomotif…");
      await E.pyodide.loadPackage("micropip");
      const micropip = E.pyodide.pyimport("micropip");
      await micropip.install(E.WHEEL_URL);
      E.showProgress(0.85);
      await E.pyodide.runPythonAsync(E.PY_CODE);
      E.pyRender = E.pyodide.globals.get("render_motif");
      E.pyExportPng = E.pyodide.globals.get("export_png");
      E.pyExportFramePng = E.pyodide.globals.get("export_stored_png");
      E.pyBuildKeyframes = E.pyodide.globals.get("build_keyframes");
      E.pyRenderFrame = E.pyodide.globals.get("render_stored_frame");
      E.pyClearFrames = E.pyodide.globals.get("clear_stored_frames");
      E.pyExportGif = E.pyodide.globals.get("export_gif");
      E.showProgress(1);
      E.hideProgress();
      E.showToast("ready");
      return E.pyodide;
    })().catch((e) => {
      E.pyPromise = null;
      E.hideProgress();
      E.showToast("Pyodide load failed");
      throw e;
    });
    return E.pyPromise;
  }
  E.ensurePyodide = ensurePyodide;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("failed to load " + src));
      document.head.appendChild(s);
    });
  }
  E.loadScript = loadScript;

  // --- render + LRU ------------------------------------------------------------
  async function renderMotif(name, params) {
    const key = name + "|" + canonical(params);
    const hit = E.cache.get(key);
    if (hit !== undefined) {
      E.cache.delete(key);
      E.cache.set(key, hit);
      return hit;
    }
    await ensurePyodide();
    // The bridge computes the display scale from the motif's registered
    // example (see the PY_CODE _scale_for cache); hand it over so the first
    // render of a motif caches the right per-motif scale.
    const ex = E.byName && E.byName[name] ? E.byName[name].example : null;
    const out = JSON.parse(E.pyRender(name, JSON.stringify(params || {}), JSON.stringify(ex || {})));
    if (E.cache.size >= CACHE_SIZE) E.cache.delete(E.cache.keys().next().value);
    E.cache.set(key, out);
    return out;
  }
  E.renderMotif = renderMotif;

  function canonical(params) {
    const keys = Object.keys(params).sort();
    return JSON.stringify(keys.map((k) => [k, params[k]]));
  }
  E.canonical = canonical;
})(window.EXPLORE);
