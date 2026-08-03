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
from geomotif.io.spec import from_spec
from geomotif.io.svg import to_svg
from geomotif.io.png import to_png
from geomotif.core.transform import Affine

_EXC = (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RecursionError)

# The display canvas and its margin. The display renderer maps the world
# coordinate plane (y up, origin at 0,0) onto this canvas with a fixed
# per-motif scale (see _scale_for below), the world origin anchored at the
# canvas centre (260, 260). Because the mapping is fixed, a slider change
# *visibly rescales* the picture instead of being re-fit to the box on every
# render, and the grid / readout can translate between world and screen.
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

# Render an SVG for display. to_svg is called with width=/height=/padding=0
# (no explicit canvas), which makes its internal fit the identity -- exactly
# the placed design's own bounds, so the fixed scale and the origin-anchored
# placement survive the write. flip_y=False because _placed already produced
# y-down coordinates; a second flip would invert the picture.
def _display_svg(placed, s):
    svg = to_svg(placed, width=None, height=None, padding=0,
                 precision=_PREC, title=None, flip_y=False)
    return json.dumps({"svg": svg, "scale": s, "error": None})

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
