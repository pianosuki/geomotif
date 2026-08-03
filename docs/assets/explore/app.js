"use strict";

// --- constants ---------------------------------------------------------------
// Pyodide ships from the official CDN; the version is a single pin so a later
// step can vendor it for offline use. The geomotif wheel is copied next to the
// SPA at deploy time (Step 10); its name carries the catalog's version, so the
// pinned build and the runtime stay in lockstep automatically.
const PYODIDE_VERSION = "0.26.4";
const CACHE_SIZE = 256;

// A URL fragment past ~2 KB risks truncation in some browsers and chat
// clients. When the animation recipe pushes the share fragment over this limit
// the share button copies the spec JSON instead (see the share handler).
const SHARE_URL_LIMIT = 2000;

// Parameter names the CLI reserves for its own flags and never accepts on a
// motif -- mirrors RESERVED in src/geomotif/cli.py so the command line is
// copy-paste accurate.
const RESERVED = new Set([
  "aa_level", "antialias", "background", "by", "compression", "distribute",
  "dither", "dot_radius", "ease", "fit", "fps", "frames", "hold", "ink",
  "keep_duplicates", "landscape", "loop", "margin", "motion", "optimize",
  "out", "padding", "paper", "precision", "quality", "samples", "snap",
  "snap_mode", "spec", "stride", "title", "transparent",
]);

// Annotations the CLI turns into a flag -- mirrors _flag_for in cli.py. Anything
// else (Projection, Callable, Sequence[Point], nested motifs, ...) is not a
// flag and is held at its declared default.
const SETTABLE = new Set([
  "bool", "int", "int | None", "float", "float | None",
  "str", "str | None", "Point", "Point | None", "Bounds", "Bounds | None",
]);

// --- Python render bridge ----------------------------------------------------
// Runs in Pyodide once and exposes render_motif(name, params_json) -> JSON.
// The same exception set explore._draw guards is caught and surfaced as a
// friendly inline error rather than a thrown promise rejection.
const PY_CODE = `
import json
from geomotif.io.spec import from_spec
from geomotif.io.svg import to_svg
from geomotif.io.png import to_png

_EXC = (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RecursionError)

# The same canvas size and precision the SPA's display render uses -- kept in
# one place so the live picture and the SVG export stay the same picture.
_W, _H, _PREC = 520, 520, 1

def render_motif(name, params_json):
    try:
        params = json.loads(params_json) if params_json else {}
        motif = from_spec({"motif": name, "params": params})
        design = motif.build()
        svg = to_svg(design, width=_W, height=_H, precision=_PREC, title=None)
        return json.dumps({"svg": svg, "error": None})
    except _EXC as e:
        return json.dumps({"svg": None, "error": type(e).__name__ + ": " + str(e)})

# PNG export -- matches the CLI's "geomotif render <motif> --out x.png" default
# styling (canvas 480, ink #0b0b0b, paper #ffffff, thickness 1, padding 8, no
# antialias, zlib 6, truecolour). Returns raw bytes, which Pyodide hands to JS
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

_STORE = {"frames": ()}

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

def build_keyframes(name, params_json, tracks_json, frames, fps, hold, easing, overlays_json):
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
        return json.dumps({"count": len(built), "error": None})
    except _EXC as e:
        _STORE["frames"] = ()
        return json.dumps({"count": 0, "error": type(e).__name__ + ": " + str(e)})

def render_stored_frame(i):
    frames = _STORE["frames"]
    try:
        if i < 0 or i >= len(frames):
            raise IndexError(f"frame {i} out of range (0..{len(frames)-1})")
        svg = to_svg(frames[i], width=_W, height=_H, precision=_PREC, title=None)
        return json.dumps({"svg": svg, "error": None})
    except _EXC as e:
        return json.dumps({"svg": None, "error": type(e).__name__ + ": " + str(e)})

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

// --- module state ------------------------------------------------------------
let catalog = null;
const byName = Object.create(null);
let current = null;
let state = {};
let familyFilter = null;
let searchQuery = "";

let pyPromise = null;
let pyodide = null;
let pyRender = null;
let pyExportPng = null;
let pyBuildKeyframes = null;
let pyRenderFrame = null;
let pyClearFrames = null;
let pyExportGif = null;
let WHEEL_URL = "";

// LRU cache, insertion-ordered: the oldest entry is evicted when full.
const cache = new Map();

// The last successfully rendered, full-prolog SVG (the bytes the CLI would
// write) and the motif/params that produced it. Kept so the SVG / PNG / spec
// exports reuse the same picture the user is looking at without a second
// Pyodide round-trip for the SVG case, and so PNG/spec can rebuild it with
// the right defaults. The LRU stays keyed on geometry alone (name + params),
// never on the viewBox, so zooming and panning never evict a render.
let lastSvg = null;
let lastMotif = null;
let lastParams = null;

// viewBox for zoom/pan: the live box applied to the stage's <svg>, in user
// units. `null` while no SVG is displayed (placeholder, unavailable motif, or
// error). `naturalVB` is the box the renderer emitted -- the one "fit"
// restores to.
let viewBox = null;
let naturalVB = null;
const ZOOM_STEP = Math.sqrt(2); // one button click ≈ one stop

// Render debounce. Each input event clears the pending timer and arms a fresh
// one; when it fires the actual render runs inside a requestAnimationFrame so
// the browser has finished painting the input's own state. ~30 ms is long
// enough to coalesce a rapid slider drag, short enough to feel instant.
const RENDER_DEBOUNCE_MS = 30;
let renderTimer = null;

// Spread used by the geometric heuristic for numeric params without a declared
// Range -- mirrors explore._SPREAD so the SPA's guessed sliders cover the same
// ground the CLI explore page would.
const SPREAD = 2.0;

// --- share URL fragment ------------------------------------------------------
// The hash carries one or two key=value pairs separated by `&`:
//
//   #m=<still>&a=<anim>
//
// `m=` is the still spec: base64url of a compact JSON blob `{"m": motif,
// "p": params}`. base64url keeps the value free of `+`/`/`/`=` so it never
// needs percent-encoding. The CLI never sees this compact form: the SPA
// expands it back to the full `{"motif":..., "params":...}` shape before
// calling from_spec, so a shared view round-trips with `geomotif render
// --spec` byte-for-byte by construction.
//
// `a=` is the animation recipe (Step 9): the `animRecipe(anim)` output
// compressed with lz-string's `compressToEncodedURIComponent` -- the one
// vendored client dependency (see lz-string.js). That compressor's alphabet
// is URL-safe (no `&`, no `=`, no `/`), so its output can sit directly in
// the hash without a second base64 pass. Landing on a URL with an `a=` pair
// boots straight into animation mode with the timeline populated.
//
// Both values use alphabets that omit `&` and `=`, so `&` is a safe pair
// separator and `=` cleanly splits each pair into key/value. Either pair
// may be absent; a still-only share URL is just `#m=...`.

// --- DOM handles -------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const progressEl = $("progress");
const progressFill = progressEl.querySelector("i");
const familiesEl = $("families");
const motifsEl = $("motifs");
const stageEl = $("stage");
const placeholderEl = $("placeholder");
const phMain = $("ph-main");
const metaEl = $("meta");
const controlsEl = $("controls");
const commandEl = $("command");
const copyEl = $("copy");
const shareEl = $("share");
const expSvgEl = $("exp-svg");
const expPngEl = $("exp-png");
const expSpecEl = $("exp-spec");
const zoomOutEl = $("zoom-out");
const zoomInEl = $("zoom-in");
const fitEl = $("fit");
const tgGridEl = $("tg-grid");
const tgBorderEl = $("tg-border");
const themeEl = $("theme");
const playEl = $("play");
const timelineEl = $("timeline");
const animProgressEl = $("anim-progress");
const animProgressFill = animProgressEl.querySelector("i");
const transportEl = $("transport");
const playPauseEl = $("tp-play");
const loopEl = $("tp-loop");
const animFramesEl = $("tp-frames");
const animFpsEl = $("tp-fps");
const animHoldEl = $("tp-hold");
const animEaseEl = $("tp-easing");
const tracksEl = $("tracks");
const scrubEl = $("scrubber");
const ovDrawEl = $("ov-draw");
const ovSpinEl = $("ov-spin");
const ovDrawOpts = $("ov-draw-opts");
const ovSpinOpts = $("ov-spin-opts");
const ovTrailEl = $("ov-trail");
const ovTurnsEl = $("ov-turns");
const expGifEl = $("exp-gif");

// --- catalog ----------------------------------------------------------------
async function boot() {
  try {
    const res = await fetch("catalog.json");
    catalog = await res.json();
  } catch (e) {
    setStatus("failed to load catalog.json");
    placeholderEl.textContent = "could not load catalog.json";
    placeholderEl.classList.add("error");
    return;
  }
  WHEEL_URL = `./geomotif-${catalog.geomotif}-py3-none-any.whl`;
  for (const m of catalog.motifs) byName[m.name] = m;
  paintFamilies();
  paintMotifs();
  setStatus("ready — pick a motif");
  // A shared view arrives in the URL fragment; if present it wins over the
  // default first motif so landing on a share URL boots straight into the
  // sender's state. Otherwise we fall back to the first available motif.
  const restored = readFragment();
  if (restored && byName[restored.motif]) {
    selectMotif(restored.motif, restored.params, { fromFragment: true, anim: restored.anim });
  } else {
    const first = catalog.motifs.find((m) => m.available) || catalog.motifs[0];
    if (first) selectMotif(first.name);
  }
}

function paintFamilies() {
  const all = document.createElement("button");
  all.textContent = "all";
  all.className = "on";
  all.addEventListener("click", () => {
    familyFilter = null;
    [...familiesEl.children].forEach((b) => (b.className = ""));
    all.className = "on";
    paintMotifs();
  });
  familiesEl.appendChild(all);
  for (const f of catalog.families) {
    const b = document.createElement("button");
    b.textContent = `${f.name} (${f.count})`;
    b.addEventListener("click", () => {
      familyFilter = f.name;
      [...familiesEl.children].forEach((x) => (x.className = ""));
      b.className = "on";
      paintMotifs();
    });
    familiesEl.appendChild(b);
  }
}

function paintMotifs() {
  motifsEl.innerHTML = "";
  const q = searchQuery.toLowerCase();
  const list = catalog.motifs.filter((m) => {
    if (familyFilter && m.family !== familyFilter) return false;
    if (q && !m.name.includes(q) && !(m.summary || "").toLowerCase().includes(q)) return false;
    return true;
  });
  for (const m of list) {
    const li = document.createElement("li");
    if (!m.available) li.className = "unavailable";
    if (m.name === current) li.classList.add("on");
    const code = document.createElement("code");
    code.textContent = m.name;
    li.appendChild(code);
    if (m.requires) {
      const b = document.createElement("span");
      b.className = "badge";
      b.textContent = m.requires;
      li.appendChild(b);
    }
    li.title = m.summary || "";
    li.addEventListener("click", () => selectMotif(m.name));
    motifsEl.appendChild(li);
  }
}

// --- motif selection & rendering --------------------------------------------
// `override` (optional) is a params mapping decoded from a shared URL fragment;
// it is folded into the freshly-seeded state so a share URL boots into the
// sender's slider positions. `opts.fromFragment` records that the selection
// came from the hash so selectMotif does not rewrite the same hash it just
// consumed (which would replace the entry we want to keep as the landing one).
function selectMotif(name, override, opts) {
  opts = opts || {};
  // Leaving animation mode tears down the timeline and the frame bundle; the
  // timeline is per-motif and a new selection renders a still.
  if (animOn) exitAnim();
  current = name;
  const info = byName[name];
  if (!info) return;
  // Working state begins from the motif's registered example -- the curated
  // picture the gallery shows -- overlaid on the declared default for every
  // settable parameter the example does not mention, so each control has a
  // starting value. Non-settable params that the example does not name are
  // left out entirely: their real default (a function, a Projection, ...) is
  // not a value the SPA can or should round-trip, and `from_spec` falls back
  // to the motif's own default when they are absent.
  state = initState(info);
  if (override) applyOverride(state, info, override);
  paintMotifs();
  paintMeta(info);
  paintControls(info, state, !info.available);
  paintCommand(info, state);
  // Export needs a built design; scipy-only motifs cannot build under Pyodide
  // so their export buttons stay disabled alongside their controls.
  const canExport = !!info.available;
  [expSvgEl, expPngEl, expSpecEl].forEach((b) => { b.disabled = !canExport; });
  expGifEl.disabled = true; // GIF export is animation-mode only
  // `animOn` was torn down above, so the still write carries no `a=` pair.
  if (!opts.fromFragment) writeFragment(name, state, null, false);
  if (!info.available) {
    showUnavailable(info);
    return;
  }
  // A share URL's `a=` pair (decoded into `opts.anim`) boots straight into
  // animation mode with the timeline populated; otherwise a still render.
  if (opts.anim) {
    enterAnim({ recipe: opts.anim, fromFragment: opts.fromFragment });
  } else {
    render(info, state);
  }
}

// Build the initial parameter state for a motif. Example values win; settable
// params not in the example take their declared default; everything else is
// omitted so the Python bridge uses the motif's real default for it.
function initState(info) {
  const st = {};
  for (const p of info.params) {
    if (RESERVED.has(p.name)) continue;
    if (p.name in info.example) st[p.name] = clone(info.example[p.name]);
    else if (isSettable(p)) st[p.name] = clone(p.default);
  }
  return st;
}

function clone(v) {
  if (v == null || typeof v !== "object") return v;
  return JSON.parse(JSON.stringify(v));
}

async function render(info, params) {
  // Only show the "rendering..." placeholder on the first render, when the
  // stage has no SVG yet. On subsequent debounced updates we keep the current
  // picture in place and swap it once the new one is ready, so slider drags
  // never flash a placeholder between frames.
  const hadSvg = !!stageEl.querySelector("svg");
  if (!hadSvg) {
    placeholderEl.classList.remove("error");
    placeholderEl.classList.add("busy");
    phMain.textContent = "rendering…";
    placeholderEl.style.display = "";
  }
  let result;
  try {
    result = await renderMotif(info.name, params);
  } catch (e) {
    placeholderEl.classList.remove("busy");
    placeholderEl.classList.add("error");
    phMain.textContent = "Pyodide failed to load: " + (e && e.message ? e.message : e);
    return;
  }
  if (result.error) {
    placeholderEl.classList.remove("busy");
    placeholderEl.classList.add("error");
    placeholderEl.style.display = "";
    stageEl.querySelectorAll("svg").forEach((s) => s.remove());
    phMain.textContent = result.error;
    lastSvg = null;
    lastMotif = null;
    lastParams = null;
    viewBox = null;
    naturalVB = null;
    return;
  }
  placeholderEl.classList.remove("busy", "error");
  placeholderEl.style.display = "none";
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
  stageEl.insertAdjacentHTML("beforeend", stripXmlDecl(result.svg));
  // Remember the full-prolog SVG (the bytes the CLI writes) and the inputs
  // that produced it, for the SVG / PNG / spec exporters. The display copy is
  // the prolog-stripped version; the export copy keeps the prolog so a
  // downloaded .svg opens standalone and round-trips with save_svg.
  const prevMotif = lastMotif;
  lastSvg = result.svg;
  lastMotif = info.name;
  lastParams = params;
  // The renderer always emits viewBox="0 0 520 520", so a slider drag (same
  // motif, new SVG element) can keep the user's zoom/pan: reapply the live
  // box to the new <svg>. Switching motifs starts fit-to-view instead, so a
  // new picture is never cropped by the previous one's zoom.
  captureNatural();
  if (prevMotif === info.name && viewBox) applyViewBox();
  else fitView();
}

// Read the rendered <svg>'s own viewBox into `naturalVB` -- the box the
// "fit" button restores to. The display render is a fixed 520x520 canvas, so
// in practice this is always {0,0,520,520}, but reading it from the element
// keeps the code honest if that ever changes.
function captureNatural() {
  const svg = stageEl.querySelector("svg");
  if (!svg) { naturalVB = null; return; }
  const vb = svg.viewBox && svg.viewBox.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    naturalVB = { x: vb.x, y: vb.y, w: vb.width, h: vb.height };
  } else {
    naturalVB = { x: 0, y: 0, w: 520, h: 520 };
  }
}

function applyViewBox() {
  const svg = stageEl.querySelector("svg");
  if (!svg || !viewBox) return;
  svg.setAttribute("viewBox", `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`);
}

function zoomAround(factor, cx, cy) {
  if (!viewBox) return;
  // Zoom around a viewBox-space point (cx, cy); leave it fixed on screen.
  const newW = Math.max(1e-6, viewBox.w * factor);
  const newH = Math.max(1e-6, viewBox.h * factor);
  // Clamp so a single motif never zooms in past ~50x of its natural box
  // (keeps the float precision sane) or out beyond 0.1x (still visible).
  const lim = (n, n0) => {
    const lo = n0 * 0.02, hi = n0 * 50;
    return Math.min(hi, Math.max(lo, n));
  };
  const W = lim(newW, naturalVB.w), H = lim(newH, naturalVB.h);
  const real = W / viewBox.w;
  viewBox.x = cx - (cx - viewBox.x) * real;
  viewBox.y = cy - (cy - viewBox.y) * real;
  viewBox.w = W;
  viewBox.h = H;
  applyViewBox();
}

function zoomCenter(factor) {
  if (!viewBox) return;
  zoomAround(factor, viewBox.x + viewBox.w / 2, viewBox.y + viewBox.h / 2);
}

function fitView() {
  if (!naturalVB) return;
  viewBox = { ...naturalVB };
  applyViewBox();
}

function showUnavailable(info) {
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
  placeholderEl.classList.remove("busy");
  placeholderEl.classList.add("error");
  placeholderEl.style.display = "";
  phMain.textContent =
    `This motif needs ${info.requires} to build, which Pyodide does not yet load. ` +
    "Try it locally: pip install scipy && geomotif render " + info.name;
  lastSvg = null;
  lastMotif = null;
  lastParams = null;
  viewBox = null;
  naturalVB = null;
}

function paintMeta(info) {
  const parts = [`<h2><code>${esc(info.name)}</code></h2>`];
  parts.push(`<p class="summary">${esc(info.summary || "")}</p>`);
  if (info.requires) {
    parts.push(`<p><span class="badge">needs ${esc(info.requires)}</span></p>`);
  }
  if (info.doc) {
    parts.push(`<div class="doc">${esc(info.doc)}</div>`);
  }
  metaEl.innerHTML = parts.join("");
  $("control-title").innerHTML = `<code>${esc(info.name)}</code>`;
}

// --- parameter controls -----------------------------------------------------
// Each row in the controls panel is built from the motif's catalog params. The
// mapping mirrors explore.py's settable/fixed split: an annotation the CLI
// turns into a flag becomes a live control; anything else (Projection,
// Callable, Sequence, tuple, nested motifs, ...) is listed as "held" -- the
// command line reports the same params as not settable, and the SPA shows them
// the same way.
//
// Control types:
//   bool                       -> toggle
//   Literal / choices present  -> dropdown
//   Point / Point | None       -> x, y pair (with a none toggle for the | None)
//   Bounds / Bounds | None     -> min_x, min_y, max_x, max_y 4-tuple
//   numeric with min & max     -> range slider with a live value readout
//                                 (ints honour `step`, snapping to whole steps)
//   int / float (no range)     -> range slider across the geometric heuristic
//                                 around the default (mirrors _floats/_integers)
//   int | None / float | None  -> number input with a none toggle
//   str / str | None           -> text input
//
// Every input mutates `state` in place and arms a single debounced render, so
// the canvas always reflects the combined state of all controls (the 1.1.0
// "one slider at a time" limitation is gone).
function paintControls(info, st, disabled) {
  controlsEl.innerHTML = "";
  const settable = [];
  const held = [];
  for (const p of info.params) {
    if (RESERVED.has(p.name)) continue;
    if (isSettable(p)) settable.push(p);
    else held.push(p);
  }
  for (const p of settable) controlsEl.appendChild(buildControl(info, p, st, disabled));
  if (held.length) {
    const note = document.createElement("p");
    note.className = "held-note";
    note.innerHTML =
      `<span class="label">Held</span>` +
      `<span class="held-list"> ` +
      held.map((p) => `<code>${esc(p.name)}</code>`).join("") +
      `</span>`;
    note.title =
      "These parameters have no scalar axis the CLI can flag -- a Projection, a " +
      "Callable, a Sequence, a nested motif, ... -- so they stay at the motif's " +
      "declared or example value.";
    controlsEl.appendChild(note);
  }
}

function buildControl(info, p, st, disabled) {
  const row = document.createElement("div");
  row.className = "control" + (disabled ? " disabled" : "");
  const label = document.createElement("div");
  label.className = "control-label";
  const name = document.createElement("span");
  name.className = "control-name";
  name.textContent = p.name;
  const ann = document.createElement("span");
  ann.className = "control-ann";
  ann.textContent = p.annotation;
  label.appendChild(name);
  label.appendChild(ann);
  row.appendChild(label);

  const body = document.createElement("div");
  body.className = "control-body";
  row.appendChild(body);

  const onChange = () => {
    paintCommand(info, st);
    if (animOn && anim) {
      // In animation mode a slider move pins a keyframe at the scrubber's
      // time for this param, so what the slider shows is what plays. Dropping
      // the value into the timeline re-renders the frame bundle.
      const t = bundle && bundle.core ? (bundle.core.length > 1 ? playState.idx / (bundle.core.length - 1) : 0) : 0;
      const tp = Math.min(1, Math.max(0, t));
      if (animatableParams(info).some((q) => q.name === p.name)) {
        dropKeyframe(p, st, anim, tp);
        const lane = tracksEl.querySelector(`.lane[data-param="${p.name}"]`);
        if (lane) paintLaneDots(lane, p, anim);
        restartPlayback(info, st, anim);
        return;
      }
    }
    scheduleRender(info, st);
  };
  addControlBody(body, p, st, disabled, onChange);
  return row;
}

function addControlBody(body, p, st, disabled, onChange) {
  const ann = p.annotation;
  const hasChoices = !!(p.choices && p.choices.length);
  if (ann === "bool") {
    addToggle(body, p, st, disabled, onChange);
  } else if (hasChoices || ann.startsWith("Literal")) {
    addSelect(body, p, st, disabled, onChange);
  } else if (ann === "Point" || ann === "Point | None") {
    addPoint(body, p, st, disabled, onChange);
  } else if (ann === "Bounds" || ann === "Bounds | None") {
    addBounds(body, p, st, disabled, onChange);
  } else if (ann === "int" || ann === "float") {
    addNumericSlider(body, p, st, disabled, onChange);
  } else if (ann === "int | None" || ann === "float | None") {
    addOptionalNumeric(body, p, st, disabled, onChange);
  } else if (ann === "str" || ann === "str | None") {
    addText(body, p, st, disabled, onChange);
  } else {
    // Should not happen -- isSettable filters these out -- but degrade safely.
    const span = document.createElement("span");
    span.className = "control-ann";
    span.textContent = "held";
    body.appendChild(span);
  }
}

// bool -> toggle
function addToggle(body, p, st, disabled, onChange) {
  const label = document.createElement("label");
  label.className = "toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = !!st[p.name];
  if (disabled) input.disabled = true;
  input.addEventListener("change", () => {
    st[p.name] = input.checked;
    label.querySelector(".switch").textContent = input.checked ? "on" : "off";
    onChange();
  });
  const span = document.createElement("span");
  span.className = "switch";
  span.textContent = input.checked ? "on" : "off";
  label.appendChild(input);
  label.appendChild(span);
  body.appendChild(label);
}

// Literal / choices -> dropdown
function addSelect(body, p, st, disabled, onChange) {
  const choices = p.choices || [];
  const select = document.createElement("select");
  select.className = "control-select";
  if (disabled) select.disabled = true;
  for (const c of choices) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    if (st[p.name] === c) opt.selected = true;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => {
    st[p.name] = select.value;
    onChange();
  });
  body.appendChild(select);
}

// Point / Point | None -> x, y pair (with a none toggle for the | None variant)
function addPoint(body, p, st, disabled, onChange) {
  const optional = p.annotation === "Point | None";
  const cur = st[p.name];
  const arr = Array.isArray(cur) ? [Number(cur[0]) || 0, Number(cur[1]) || 0] : [0, 0];
  const inputDisabled = disabled || (optional && cur == null);

  if (optional) addNoneToggle(body, p, st, disabled, onChange, () => arr, (a) => { st[p.name] = a; });

  const pair = document.createElement("div");
  pair.className = "pair two";
  for (let i = 0; i < 2; i++) {
    const lab = document.createElement("label");
    const ax = document.createElement("span");
    ax.className = "ax";
    ax.textContent = i === 0 ? "x" : "y";
    const input = numberInput(arr[i], 0.1, inputDisabled);
    input.addEventListener("input", () => {
      arr[i] = numOr(input.value, arr[i]);
      st[p.name] = arr.slice();
      onChange();
    });
    lab.appendChild(ax);
    lab.appendChild(input);
    pair.appendChild(lab);
  }
  body.appendChild(pair);
  if (optional && cur == null) setNoneDisabled(pair, true);
}

// Bounds / Bounds | None -> min_x, min_y, max_x, max_y
function addBounds(body, p, st, disabled, onChange) {
  const optional = p.annotation === "Bounds | None";
  const TYPE = "geomotif.core.types.Bounds";
  let cur = st[p.name];
  if (cur && typeof cur === "object") {
    cur = {
      min_x: +cur.min_x || 0, min_y: +cur.min_y || 0,
      max_x: +cur.max_x || 0, max_y: +cur.max_y || 0,
    };
  } else {
    cur = { min_x: -150, min_y: -150, max_x: 150, max_y: 150 };
  }
  const keys = ["min_x", "min_y", "max_x", "max_y"];
  const inputDisabled = disabled || (optional && st[p.name] == null);

  if (optional) addNoneToggle(body, p, st, disabled, onChange, () => cur, (c) => {
    st[p.name] = c && { $type: TYPE, ...c };
  });

  const pair = document.createElement("div");
  pair.className = "pair four";
  for (const k of keys) {
    const lab = document.createElement("label");
    const ax = document.createElement("span");
    ax.className = "ax";
    ax.textContent = k.replace("_", "");
    const input = numberInput(cur[k], 1, inputDisabled);
    input.addEventListener("input", () => {
      cur[k] = numOr(input.value, cur[k]);
      st[p.name] = { $type: TYPE, ...cur };
      onChange();
    });
    lab.appendChild(ax);
    lab.appendChild(input);
    pair.appendChild(lab);
  }
  body.appendChild(pair);
  if (optional && st[p.name] == null) setNoneDisabled(pair, true);
}

// numeric with declared Range -> range slider with a live readout. Ints honour
// `step` (whole-step snapping); floats use a fine linear step.
// Route plain int/float to the heuristic slider when no Range is declared.
function addNumericSlider(body, p, st, disabled, onChange) {
  if (p.min != null && p.max != null) {
    addRangedSlider(body, p, st, disabled, onChange);
  } else {
    addHeuristicSlider(body, p, st, disabled, onChange);
  }
}

// int / float without a declared Range -> range slider across the geometric
// heuristic around the default, mirroring explore.py's _floats / _integers.
function addHeuristicSlider(body, p, st, disabled, onChange) {
  const isInt = p.annotation === "int";
  const base = st[p.name];
  let lo, hi, step;
  if (isInt) {
    const low = Math.max(1, Math.floor(Number(base) / SPREAD));
    const high = Math.max(low + 1, Math.ceil(Number(base) * SPREAD));
    lo = low; hi = high; step = 1;
  } else {
    const f = Number(base) || 0;
    if (f === 0) { lo = -1; hi = 1; }
    else { lo = f / SPREAD; hi = f * SPREAD; }
    step = (hi - lo) / 1000;
  }
  const row = document.createElement("div");
  row.className = "slider-row";
  const input = document.createElement("input");
  input.type = "range";
  input.min = lo;
  input.max = hi;
  input.step = step;
  input.value = base;
  if (disabled) input.disabled = true;
  const out = document.createElement("output");
  out.className = "slider-val";
  out.textContent = formatVal(base);
  input.addEventListener("input", () => {
    const v = isInt ? Math.round(Number(input.value)) : Number(input.value);
    st[p.name] = v;
    out.textContent = formatVal(v);
    onChange();
  });
  row.appendChild(input);
  row.appendChild(out);
  body.appendChild(row);
}

function addRangedSlider(body, p, st, disabled, onChange) {
  const isInt = p.annotation === "int";
  const min = p.min;
  const max = p.max;
  let step;
  if (isInt) {
    step = p.step != null ? Math.max(1, Math.round(p.step)) : 1;
  } else {
    step = p.step != null ? p.step : (max - min) / 1000;
  }
  const row = document.createElement("div");
  row.className = "slider-row";
  const input = document.createElement("input");
  input.type = "range";
  input.min = min;
  input.max = max;
  input.step = step;
  input.value = st[p.name];
  if (disabled) input.disabled = true;
  const out = document.createElement("output");
  out.className = "slider-val";
  out.textContent = formatVal(st[p.name]);
  input.addEventListener("input", () => {
    const v = isInt ? Math.round(Number(input.value)) : Number(input.value);
    st[p.name] = v;
    out.textContent = formatVal(v);
    onChange();
  });
  row.appendChild(input);
  row.appendChild(out);
  body.appendChild(row);
}

// int | None / float | None (no range) -> number input with a none toggle.
function addOptionalNumeric(body, p, st, disabled, onChange) {
  const isInt = p.annotation === "int | None";
  const isNone = st[p.name] == null;
  let start = isNone ? (isInt ? 128 : 1.0) : st[p.name];

  const noneRow = document.createElement("div");
  noneRow.className = "none-row";
  const noneCb = document.createElement("input");
  noneCb.type = "checkbox";
  noneCb.checked = !isNone;
  if (disabled) noneCb.disabled = true;
  const noneLab = document.createElement("span");
  noneLab.textContent = "set value (otherwise the motif's adaptive default)";
  noneRow.appendChild(noneCb);
  noneRow.appendChild(noneLab);
  body.appendChild(noneRow);

  const input = numberInput(start, isInt ? 1 : 0.1, disabled || isNone);
  input.addEventListener("input", () => {
    if (noneCb.checked) {
      st[p.name] = isInt ? Math.round(numOr(input.value, start)) : numOr(input.value, start);
      onChange();
    }
  });
  noneCb.addEventListener("change", () => {
    if (noneCb.checked) {
      st[p.name] = isInt ? Math.round(numOr(input.value, start)) : numOr(input.value, start);
      input.disabled = disabled;
    } else {
      st[p.name] = null;
      input.disabled = true;
    }
    onChange();
  });
  body.appendChild(input);
}

// str / str | None -> text input
function addText(body, p, st, disabled, onChange) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "control-input";
  input.value = st[p.name] == null ? "" : String(st[p.name]);
  if (disabled) input.disabled = true;
  input.addEventListener("input", () => {
    st[p.name] = input.value;
    onChange();
  });
  body.appendChild(input);
}

// --- shared input helpers ---------------------------------------------------
function numberInput(value, step, disabled) {
  const input = document.createElement("input");
  input.type = "number";
  input.className = "control-input";
  input.step = step;
  input.value = value;
  if (disabled) input.disabled = true;
  return input;
}

function numOr(s, fallback) {
  const n = Number(s);
  return isFinite(n) ? n : fallback;
}

function formatVal(v) {
  if (typeof v !== "number" || !isFinite(v)) return String(v);
  if (Number.isInteger(v)) return String(v);
  // Three significant figures is enough to read a slider without drowning the
  // readout in floating-point noise (e.g. 1.5707963 -> 1.57).
  return String(Number(v.toPrecision(3)));
}

// A "none" toggle for Optional Point / Bounds. When unchecked the parameter is
// set to null and the coordinate inputs below are disabled; when checked the
// current coordinate object is written back into state.
function addNoneToggle(body, p, st, disabled, onChange, getCur, writeCur) {
  const noneRow = document.createElement("div");
  noneRow.className = "none-row";
  const noneCb = document.createElement("input");
  noneCb.type = "checkbox";
  noneCb.checked = st[p.name] != null;
  if (disabled) noneCb.disabled = true;
  const noneLab = document.createElement("span");
  noneLab.textContent = "set value (otherwise the motif's default)";
  noneRow.appendChild(noneCb);
  noneRow.appendChild(noneLab);
  noneCb.addEventListener("change", () => {
    if (noneCb.checked) {
      writeCur(getCur());
    } else {
      st[p.name] = null;
    }
    onChange();
    // Toggle the disabled state of the sibling coordinate inputs that follow.
    const pair = body.querySelector(".pair");
    if (pair) setNoneDisabled(pair, !noneCb.checked);
  });
  body.appendChild(noneRow);
}

function setNoneDisabled(container, disabled) {
  container.querySelectorAll("input").forEach((i) => { i.disabled = disabled; });
}

// --- debounced render + fragment sync ---------------------------------------
// The hash is updated on the same ~30 ms cadence as the render so a slider
// drag never spams the history stack. replaceState keeps the back button
// working as one entry per motif session; pushState is reserved for the
// explicit "copy share URL" action so a shared view is its own bookmarkable
// entry.
function scheduleRender(info, st) {
  if (renderTimer) clearTimeout(renderTimer);
  renderTimer = setTimeout(() => {
    renderTimer = null;
    writeFragment(info.name, st, animOn ? anim : null, false);
    requestAnimationFrame(() => render(info, st));
  }, RENDER_DEBOUNCE_MS);
}

// Debounced replaceState of the full fragment (still + animation). Every
// animation-mode change point (keyframe drop/drag/delete, easing, overlays,
// frames, fps, hold) routes through here so a timeline edit never spams the
// history stack -- it replaces the current entry on the same ~30 ms cadence
// the still mode uses.
let fragTimer = null;
function scheduleFragmentWrite() {
  if (fragTimer) clearTimeout(fragTimer);
  fragTimer = setTimeout(() => {
    fragTimer = null;
    if (current) writeFragment(current, state, animOn ? anim : null, false);
  }, RENDER_DEBOUNCE_MS);
}

// Fold a params dict decoded from a share URL into the freshly-seeded state.
// Only settable params that the catalog actually knows about are written, so a
// stale share URL (renamed param, dropped field) degrades gracefully instead
// of feeding from_spec a key the motif rejects.
function applyOverride(st, info, override) {
  if (!override || typeof override !== "object") return;
  const known = Object.create(null);
  for (const p of info.params) known[p.name] = p;
  for (const key of Object.keys(override)) {
    const p = known[key];
    if (!p || RESERVED.has(p.name)) continue;
    if (!isSettable(p)) continue;
    st[key] = clone(override[key]);
  }
}

// --- share URL fragment ------------------------------------------------------
function encodeFragment(motif, params, anim) {
  // Still pair: base64url of `{"m": motif, "p": params}`. btoa handles
  // Latin-1; motif params are ASCII (numbers, strings, arrays, plain objects),
  // so no UTF-8 re-encoding is needed.
  const json = JSON.stringify({ m: motif, p: params });
  const b64 = btoa(json);
  const still = "m=" + b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  // Animation pair (only when the timeline is live): the recipe compressed with
  // lz-string's URI-safe codec. Its alphabet omits `&`/`=`/`/`, so the output
  // drops straight into the hash without a second base64 pass.
  const parts = [still];
  if (anim) {
    const recipe = animRecipe(anim);
    const compressed = LZString.compressToEncodedURIComponent(JSON.stringify(recipe));
    if (compressed) parts.push("a=" + compressed);
  }
  return "#" + parts.join("&");
}

function decodeFragment(hash) {
  if (!hash) return null;
  let frag = String(hash);
  if (frag.startsWith("#")) frag = frag.slice(1);
  if (!frag) return null;
  // The hash is `&`-separated `key=value` pairs. Each value's alphabet omits
  // `&` and `=`, so a split on `&` then first-`=` split cleanly partitions it.
  // An unknown key is ignored, so a later `x=` pair degrades instead of
  // throwing the whole restore away.
  let mRaw = null, aRaw = null;
  for (const part of frag.split("&")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const key = part.slice(0, eq);
    const val = part.slice(eq + 1);
    if (key === "m") mRaw = val;
    else if (key === "a") aRaw = val;
  }
  if (mRaw == null) return null;
  // Still pair: base64url -> JSON `{"m":..., "p":...}`. A malformed or
  // hand-edited value degrades to null (the caller falls back to the default
  // first motif).
  let motif, params;
  {
    let b64 = mRaw.replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    try {
      const obj = JSON.parse(atob(b64));
      if (!obj || typeof obj.m !== "string") return null;
      if (obj.p != null && typeof obj.p !== "object") return null;
      motif = obj.m;
      params = obj.p || {};
    } catch (e) {
      return null;
    }
  }
  // Animation pair: lz-string URI-safe decompress -> JSON recipe. An empty or
  // garbage value yields null, so a still-only share URL or a stale `a=` part
  // boots into still mode rather than throwing.
  let anim = null;
  if (aRaw != null && aRaw !== "") {
    try {
      const json = LZString.decompressFromEncodedURIComponent(aRaw);
      const recipe = json == null ? null : JSON.parse(json);
      if (recipe && typeof recipe === "object" && recipe.type === "keyframes") {
        anim = recipe;
      }
    } catch (e) {
      anim = null;
    }
  }
  return { motif, params, anim };
}

function readFragment() {
  return decodeFragment(location.hash);
}

// Write the current view into the URL fragment. `push` false uses replaceState
// (in-session sync); `push` true uses pushState (explicit share, a real
// history entry the back button can return to). `anim` is the live animation
// recipe when the timeline is open, so a shared animation URL carries the
// keyframes alongside the still spec.
function writeFragment(motif, params, anim, push) {
  const frag = encodeFragment(motif, params, anim);
  if (frag === location.hash) return;
  const url = location.pathname + location.search + frag;
  if (push) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

// --- live command line ------------------------------------------------------
// Mirrors _flag_for in cli.py: reserved params are skipped, non-flag annotations
// are held at their default, defaults are omitted, and a bool becomes --x or
// --no-x (argparse BooleanOptionalAction). Point is x,y and Bounds is
// min_x,min_y,max_x,max_y -- the metavar the CLI's parsers accept.
function isSettable(p) {
  if (p.choices || p.annotation.startsWith("Literal")) return true;
  return SETTABLE.has(p.annotation);
}

function flagValue(p, v) {
  if (Array.isArray(v)) return v.map(formatNum).join(",");
  if (v && typeof v === "object" && "$type" in v) {
    if (p.annotation.startsWith("Bounds")) {
      return [v.min_x, v.min_y, v.max_x, v.max_y].map(formatNum).join(",");
    }
    return JSON.stringify(v);
  }
  return String(v);
}

function formatNum(n) {
  return typeof n === "number" ? String(n) : String(n);
}

function paintCommand(info, st) {
  const parts = ["geomotif", "render", info.name];
  for (const p of info.params) {
    if (RESERVED.has(p.name) || !isSettable(p)) continue;
    if (!(p.name in st)) continue;
    const cur = st[p.name];
    if (equalEncoded(cur, p.default)) continue;
    const flag = p.name.replace(/_/g, "-");
    if (p.annotation === "bool") {
      parts.push(cur ? `--${flag}` : `--no-${flag}`);
    } else {
      parts.push(`--${flag}`, flagValue(p, cur));
    }
  }
  commandEl.textContent = parts.join(" ");
}

function equalEncoded(a, b) {
  if (a === b) return true;
  if (a == null || b == null) return a == b;
  if (typeof a !== typeof b) return false;
  if (Array.isArray(a)) {
    return Array.isArray(b) && a.length === b.length && a.every((x, i) => equalEncoded(x, b[i]));
  }
  if (typeof a === "object") {
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => equalEncoded(a[k], b[k]));
  }
  return false;
}

// --- Pyodide loader ----------------------------------------------------------
async function ensurePyodide() {
  if (pyPromise) return pyPromise;
  pyPromise = (async () => {
    setStatus("loading Pyodide…");
    showProgress(0.1);
    await loadScript(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.js`);
    showProgress(0.3);
    // eslint-disable-next-line no-undef
    pyodide = await loadPyodide();
    showProgress(0.55);
    setStatus("loading geomotif…");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install(WHEEL_URL);
    showProgress(0.85);
    await pyodide.runPythonAsync(PY_CODE);
    pyRender = pyodide.globals.get("render_motif");
    pyExportPng = pyodide.globals.get("export_png");
    pyBuildKeyframes = pyodide.globals.get("build_keyframes");
    pyRenderFrame = pyodide.globals.get("render_stored_frame");
    pyClearFrames = pyodide.globals.get("clear_stored_frames");
    pyExportGif = pyodide.globals.get("export_gif");
    showProgress(1);
    hideProgress();
    setStatus("ready");
    return pyodide;
  })().catch((e) => {
    pyPromise = null;
    hideProgress();
    setStatus("Pyodide load failed");
    throw e;
  });
  return pyPromise;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("failed to load " + src));
    document.head.appendChild(s);
  });
}

// --- render + LRU ------------------------------------------------------------
async function renderMotif(name, params) {
  const key = name + "|" + canonical(params);
  const hit = cache.get(key);
  if (hit !== undefined) {
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }
  await ensurePyodide();
  const out = JSON.parse(pyRender(name, JSON.stringify(params || {})));
  if (cache.size >= CACHE_SIZE) cache.delete(cache.keys().next().value);
  cache.set(key, out);
  return out;
}

function canonical(params) {
  const keys = Object.keys(params).sort();
  return JSON.stringify(keys.map((k) => [k, params[k]]));
}

// --- small helpers ----------------------------------------------------------
function stripXmlDecl(svg) {
  const s = svg.trim();
  return s.startsWith("<?xml") ? s.split("?>", 2)[1].lstrip() : s;
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
  ));
}

function setStatus(t) { statusEl.textContent = t; }
function showProgress(frac) { progressEl.classList.add("on"); progressFill.style.width = (frac * 100) + "%"; }
function hideProgress() { progressEl.classList.remove("on"); }

// --- events -----------------------------------------------------------------
copyEl.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(commandEl.textContent);
    copyEl.textContent = "copied";
    copyEl.classList.add("ok");
    setTimeout(() => { copyEl.textContent = "copy command"; copyEl.classList.remove("ok"); }, 1200);
  } catch (e) {
    copyEl.textContent = "copy failed";
  }
});

// Copy the share URL for the current view. A real history entry is pushed so
// the back button returns to the pre-share state, and the URL the user copies
// is the one the address bar shows afterwards. When the animation recipe
// pushes the fragment past a safe URL limit (~2 KB), the URL would be
// truncated by some browsers / chat clients; the share then falls back to
// copying the spec JSON (which already carries the `animation` key from the
// spec export) and flashes a hint to feed it to `geomotif render --animation`.
// The CLI reproduces the GIF byte-for-byte from that spec either way.
shareEl.addEventListener("click", async () => {
  if (!current) return;
  const animArg = animOn ? anim : null;
  const frag = encodeFragment(current, state, animArg);
  if (frag.length > SHARE_URL_LIMIT) {
    try {
      const spec = { geomotif: catalog ? catalog.geomotif : null, motif: current, params: state };
      if (animArg) spec.animation = animRecipe(animArg);
      await navigator.clipboard.writeText(JSON.stringify(spec, null, 2) + "\n");
      shareEl.textContent = "spec copied — too long for URL";
      shareEl.classList.add("ok");
      setTimeout(() => { shareEl.textContent = "copy share URL"; shareEl.classList.remove("ok"); }, 2000);
    } catch (e) {
      shareEl.textContent = "copy failed";
    }
    return;
  }
  try {
    writeFragment(current, state, animArg, true);
    await navigator.clipboard.writeText(location.href);
    shareEl.textContent = "copied";
    shareEl.classList.add("ok");
    setTimeout(() => { shareEl.textContent = "copy share URL"; shareEl.classList.remove("ok"); }, 1200);
  } catch (e) {
    shareEl.textContent = "copy failed";
  }
});

// Restoring from a back/forward navigation: the browser fires popstate when
// the user lands on a fragment we wrote. Re-seed both still state and
// timeline from it so the back button walks through shared views (still and
// animated) rather than jumping past them.
window.addEventListener("popstate", () => {
  const restored = readFragment();
  if (restored && byName[restored.motif]) {
    selectMotif(restored.motif, restored.params, { fromFragment: true, anim: restored.anim });
  }
});

const searchEl = document.querySelector(".search");
searchEl.addEventListener("input", () => {
  searchQuery = searchEl.value.trim();
  paintMotifs();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== searchEl) {
    e.preventDefault();
    searchEl.focus();
  }
});

// --- view toggles (theme / grid / border) ------------------------------------
// The theme is set on first paint by the inline head script from the stored
// preference (or the OS preference). Here we wire the manual switch: clicking
// flips data-theme, persists the choice, and updates the button label. We also
// track OS changes so a user who never touched the switch still follows their
// OS as it moves -- the stored choice is the only thing that overrides that.
const THEME_KEY = "geomotif.theme";
const GRID_KEY = "geomotif.grid";
const BORDER_KEY = "geomotif.border";

function effectiveTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function applyThemeButton() {
  // The label names the theme you would switch *to*, so a dark page shows
  // "light" and vice versa -- the same convention the explore command line
  // uses for its flags.
  themeEl.textContent = effectiveTheme() === "dark" ? "light" : "dark";
  themeEl.setAttribute("aria-pressed", String(effectiveTheme() === "dark"));
}

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem(THEME_KEY, t); } catch (e) { /* private mode */ }
  applyThemeButton();
}

themeEl.addEventListener("click", () => {
  setTheme(effectiveTheme() === "dark" ? "light" : "dark");
});

// Follow the OS when the user has not chosen a manual override.
const mq = window.matchMedia("(prefers-color-scheme: dark)");
if (mq.addEventListener) mq.addEventListener("change", (e) => {
  let stored;
  try { stored = localStorage.getItem(THEME_KEY); } catch (e) { stored = null; }
  if (stored) return;
  document.documentElement.dataset.theme = e.matches ? "dark" : "light";
  applyThemeButton();
});
else if (mq.addListener) mq.addListener((e) => { /* Safari < 14 fallback */ });

// Grid + border toggles carry over between sessions the same way; their state
// is read at boot by initViewToggles and applied as classes on .stage.
function readToggle(key, def) {
  try { const v = localStorage.getItem(key); return v == null ? def : v === "on"; }
  catch (e) { return def; }
}
function writeToggle(key, on) {
  try { localStorage.setItem(key, on ? "on" : "off"); } catch (e) { /* private */ }
}

function syncGridToggle() {
  const on = !stageEl.classList.contains("no-grid");
  tgGridEl.setAttribute("aria-pressed", String(on));
}
function syncBorderToggle() {
  const on = !stageEl.classList.contains("no-border");
  tgBorderEl.setAttribute("aria-pressed", String(on));
}

tgGridEl.addEventListener("click", () => {
  stageEl.classList.toggle("no-grid");
  syncGridToggle();
  writeToggle(GRID_KEY, !stageEl.classList.contains("no-grid"));
});
tgBorderEl.addEventListener("click", () => {
  stageEl.classList.toggle("no-border");
  syncBorderToggle();
  writeToggle(BORDER_KEY, !stageEl.classList.contains("no-border"));
});

function initViewToggles() {
  if (!readToggle(GRID_KEY, true)) stageEl.classList.add("no-grid");
  if (!readToggle(BORDER_KEY, true)) stageEl.classList.add("no-border");
  syncGridToggle();
  syncBorderToggle();
  applyThemeButton();
}
initViewToggles();

// --- zoom / pan --------------------------------------------------------------
// Wheel zooms around the cursor; a left-button drag pans; the toolbar buttons
// zoom around the centre and "fit" restores the natural viewBox. Everything is
// pure client-side viewBox math on the already-rendered SVG, so it never calls
// Pyodide and never busts the LRU (the cache key stays name + params).
function svgRect() {
  const svg = stageEl.querySelector("svg");
  return svg ? svg.getBoundingClientRect() : null;
}

stageEl.addEventListener("wheel", (e) => {
  if (!viewBox) return;
  // Do not hijack the page scroll when the pointer is over the toolbar's own
  // scrollable bits; let those scroll naturally.
  if (e.target.closest(".stage-toolbar")) return;
  e.preventDefault();
  const r = svgRect();
  if (!r || !r.width || !r.height) return;
  // Cursor as a fraction of the displayed SVG, mapped into viewBox units so
  // the point under the pointer stays under the pointer after zooming.
  const px = (e.clientX - r.left) / r.width;
  const py = (e.clientY - r.top) / r.height;
  const cx = viewBox.x + px * viewBox.w;
  const cy = viewBox.y + py * viewBox.h;
  const factor = e.deltaY < 0 ? 1 / ZOOM_STEP : ZOOM_STEP;
  zoomAround(factor, cx, cy);
}, { passive: false });

let pan = null;
stageEl.addEventListener("pointerdown", (e) => {
  if (!viewBox || e.button !== 0) return;
  // Ignore presses on the floating toolbar so its buttons still work.
  if (e.target.closest(".stage-toolbar")) return;
  pan = {
    x: e.clientX, y: e.clientY,
    vx: viewBox.x, vy: viewBox.y, w: viewBox.w, h: viewBox.h,
  };
  try { stageEl.setPointerCapture(e.pointerId); } catch (err) { /* old browser */ }
});
stageEl.addEventListener("pointermove", (e) => {
  if (!pan) return;
  const r = svgRect();
  if (!r || !r.width || !r.height) return;
  // A cursor move of dx screen px maps to dx / r.width * viewBox.w user units.
  // Dragging right moves the picture right, so viewBox.x moves left.
  const dx = (e.clientX - pan.x) / r.width * pan.w;
  const dy = (e.clientY - pan.y) / r.height * pan.h;
  viewBox.x = pan.vx - dx;
  viewBox.y = pan.vy - dy;
  applyViewBox();
});
function endPan() { pan = null; }
stageEl.addEventListener("pointerup", endPan);
stageEl.addEventListener("pointercancel", endPan);
stageEl.addEventListener("pointerleave", endPan);

zoomInEl.addEventListener("click", () => zoomCenter(1 / ZOOM_STEP));
zoomOutEl.addEventListener("click", () => zoomCenter(ZOOM_STEP));
fitEl.addEventListener("click", fitView);

// --- export (SVG / PNG / spec JSON) ------------------------------------------
// All three downloads are built from `lastSvg` / `lastMotif` / `lastParams`,
// which `render()` refreshes on every successful render. SVG reuses the cached
// prolog-bearing SVG directly (no Pyodide call); PNG rebuilds the design under
// Pyodide with the CLI's default styling so the bytes match
// `geomotif render <motif> --out x.png`; spec is the full `to_spec` shape the
// CLI's `--spec` flag reads, written in JS from `state` plus the catalog's
// geomotif version.
function flash(btn, ok, okText, failText) {
  const orig = btn.dataset.label || btn.textContent;
  btn.textContent = ok ? okText : failText;
  if (ok) btn.classList.add("ok");
  setTimeout(() => { btn.textContent = orig; btn.classList.remove("ok"); }, 1400);
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke on a timeout so the download has time to start in every browser.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

expSvgEl.addEventListener("click", () => {
  if (!lastSvg) return;
  // Keep the XML prolog so the file opens standalone and matches save_svg.
  download(new Blob([lastSvg], { type: "image/svg+xml" }), `${lastMotif}.svg`);
  flash(expSvgEl, true, "saved", "failed");
});

expPngEl.addEventListener("click", async () => {
  if (!lastMotif) return;
  expPngEl.disabled = true;
  try {
    await ensurePyodide();
    const bytes = pyExportPng(lastMotif, JSON.stringify(lastParams || {}));
    // Pyodide converts Python bytes -> Uint8Array; build a Blob from a copy so
    // the underlying buffer is not shared with the Python heap.
    const data = bytes instanceof Uint8Array ? bytes.slice() : new Uint8Array(bytes);
    download(new Blob([data], { type: "image/png" }), `${lastMotif}.png`);
    flash(expPngEl, true, "saved", "failed");
  } catch (e) {
    flash(expPngEl, false, "saved", "failed");
  } finally {
    expPngEl.disabled = false;
  }
});

expSpecEl.addEventListener("click", () => {
  if (!lastMotif) return;
  // The full `to_spec` shape: version key + motif name + params. `state` is
  // exactly the JSON-encodable params dict io/spec.py round-trips, so this
  // loads straight into `geomotif render --spec <file>`. In animation mode the
  // `animation` key sits alongside, so the same file feeds
  // `geomotif render --animation`.
  const spec = {
    geomotif: catalog ? catalog.geomotif : null,
    motif: lastMotif,
    params: state,
  };
  if (animOn && anim) spec.animation = animRecipe(anim);
  const blob = new Blob([JSON.stringify(spec, null, 2) + "\n"], { type: "application/json" });
  download(blob, `${lastMotif}.json`);
  flash(expSpecEl, true, "saved", "failed");
});

// --- animation mode ---------------------------------------------------------
// A mode toggle on the stage toolbar flips the bottom of the stage-area from a
// still picture into a timeline editor. The Step-7 `keyframes` primitive is
// the wire format: `anim.tracks` is exactly the `tracks` mapping the Python
// function takes, and `build_keyframes` runs it under Pyodide, stashing the
// per-frame Designs for chunked SVG fetch. Playback is a rAF loop reading the
// cached SVGs; pre-render happens in chunked rAF batches (4 frames per tick)
// so the timeline stays draggable while a cold animation fills in. The LRU is
// keyed on geometry (motif + params + tracks + frames + easing + overlays) and
// never on fps or hold, so a playback-only tweak re-uses the cached bundle.
//
// The share-URL `a=` fragment is Step 9; here the still fragment continues to
// carry the motif + slider state and the timeline lives in-memory only.
const EASINGS = ["linear", "quadratic", "cubic", "sinusoidal", "exponential", "circular"];
const ANIM_FRAMES_MIN = 32, ANIM_FRAMES_MAX = 240;
const ANIM_FPS_MIN = 1, ANIM_FPS_MAX = 60;
const ANIM_HOLD_MIN = 0;
const PRE_FRAMES_PER_TICK = 4;

let animOn = false;
// anim = {tracks: {name: {keyframes: [[t, value], ...], easing: null|"..."}}, ...}
let anim = null;
// bundle = {key, core: frames-length array of SVG strings (null while pending),
//            count, ready, total, busy}
let bundle = null;
// In-browser LRU for animation frame bundles, separate from the still cache so
// the two eviction policies do not fight.
const animCache = new Map();
const ANIM_CACHE_SIZE = 16;

// Playback state. `idx` is the live frame index; `holdLeft` counts down the
// hold tail; `looping` mirrors the loop toggle; `on` is whether the rAF loop
// is running.
const playState = { raf: null, last: 0, idx: 0, holdLeft: 0, looping: true, on: false };
let preRaf = null;
let scrubbing = false;

// The animatable parameters of a motif: anything a slider/dropdown/toggle can
// move, i.e. the settable numeric/bool/Literal params the catalog reports.
function animatableParams(info) {
  const out = [];
  for (const p of info.params) {
    if (RESERVED.has(p.name)) continue;
    if (!isSettable(p)) continue;
    const ann = p.annotation;
    if (ann === "int" || ann === "float" || ann === "bool" ||
        (p.choices && p.choices.length) || ann.startsWith("Literal")) {
      out.push(p);
    }
  }
  return out;
}

// The default timeline, per "Default state when entering animation mode": a
// single track on the motif's primary numeric parameter (the first int/float
// in ParamInfo order) sweeping across its declared Range (or a 2x spread of
// the default when there is none), with cubic easing at 48 frames / 20 fps /
// hold 12. The user sees motion immediately and edits from there.
function defaultAnim(info, st) {
  const nums = info.params.filter((p) =>
    !RESERVED.has(p.name) && (p.annotation === "int" || p.annotation === "float"));
  const tracks = {};
  if (nums.length) {
    const p = nums[0];
    const cur = st[p.name];
    let v0, v1;
    if (p.min != null && p.max != null) {
      v0 = p.min; v1 = p.max;
    } else if (p.annotation === "int") {
      const base = Number(cur) || 5;
      v0 = Math.max(1, Math.floor(base / SPREAD));
      v1 = Math.max(v0 + 1, Math.ceil(base * SPREAD));
    } else {
      const f = Number(cur) || 1;
      v0 = f === 0 ? -1 : f / SPREAD;
      v1 = f === 0 ? 1 : f * SPREAD;
    }
    tracks[p.name] = { keyframes: [[0.0, v0], [1.0, v1]], easing: null };
  }
  return {
    tracks,
    frames: 48,
    fps: 20,
    hold: 12,
    easing: "cubic",
    overlays: [],
  };
}

// The animation recipe as the Python `keyframes` primitive and the CLI's
// `--animation` flag read it: tracks map each animated param to a
// `[[t, value], ...]` list (the per-track easing, when set, is sent as the
// `{"keyframes": [...], "easing": "..."}` mapping form). The `type` key is
// what the spec reserves room for; `overlay` lists the post-passes.
function animRecipe(an) {
  const tracks = {};
  for (const [name, tr] of Object.entries(an.tracks)) {
    if (tr.easing) {
      tracks[name] = { keyframes: tr.keyframes, easing: tr.easing };
    } else {
      tracks[name] = tr.keyframes;
    }
  }
  return {
    type: "keyframes",
    tracks,
    frames: an.frames,
    fps: an.fps,
    hold: an.hold,
    easing: an.easing,
    overlay: an.overlays,
  };
}

function animBundleKey(info, st, an) {
  return [
    info.name,
    canonical(st),
    JSON.stringify(an.tracks),
    an.frames,
    an.easing,
    JSON.stringify(an.overlays),
  ].join("|");
}

// The inverse of `animRecipe`: turn a decoded share-URL recipe back into the
// internal `anim` shape `paintTimeline` / `startAnim` read. A stale or
// hand-edited recipe degrades gracefully -- unknown track names are kept (the
// timeline paints them, and if the motif does not know them they simply never
// fire), but malformed keyframes / overlays are dropped, and numeric fields
// are clamped into the same bounds the transport enforces. This is the restore
// half of the share-URL round-trip; `animRecipe` is the encode half.
function recipeToAnim(recipe) {
  const tracks = {};
  if (recipe && recipe.tracks && typeof recipe.tracks === "object") {
    for (const [name, tr] of Object.entries(recipe.tracks)) {
      let kfs, easing = null;
      if (Array.isArray(tr)) {
        kfs = tr;
      } else if (tr && Array.isArray(tr.keyframes)) {
        kfs = tr.keyframes;
        easing = typeof tr.easing === "string" && tr.easing ? tr.easing : null;
      } else {
        continue;
      }
      const norm = [];
      for (const kf of kfs) {
        if (!Array.isArray(kf) || kf.length < 2) continue;
        const t = Number(kf[0]);
        if (!Number.isFinite(t)) continue;
        norm.push([Math.min(1, Math.max(0, t)), clone(kf[1])]);
      }
      norm.sort((a, b) => a[0] - b[0]);
      if (norm.length) tracks[name] = { keyframes: norm, easing };
    }
  }
  const frames = clampInt(recipe && recipe.frames, ANIM_FRAMES_MIN, ANIM_FRAMES_MAX, 48);
  const fps = clampInt(recipe && recipe.fps, ANIM_FPS_MIN, ANIM_FPS_MAX, 20);
  const holdMax = Math.max(ANIM_HOLD_MIN, Math.floor(frames / 4));
  const hold = clampInt(recipe && recipe.hold, ANIM_HOLD_MIN, holdMax, 0);
  const easing = recipe && EASINGS.includes(recipe.easing) ? recipe.easing : "cubic";
  const overlays = [];
  if (recipe && Array.isArray(recipe.overlay)) {
    for (const o of recipe.overlay) {
      const e = recipeOverlay(o);
      if (e) overlays.push(e);
    }
  }
  return { tracks, frames, fps, hold, easing, overlays };
}

function clampInt(v, lo, hi, fallback) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return fallback;
  return Math.min(hi, Math.max(lo, n));
}

function recipeOverlay(o) {
  if (!o || typeof o !== "object") return null;
  if (o.type === "draw_on") {
    const trail = o.trail == null ? null : Number(o.trail);
    return { type: "draw_on", trail: Number.isFinite(trail) ? trail : null };
  }
  if (o.type === "spin") {
    const turns = Number(o.turns);
    return { type: "spin", turns: Number.isFinite(turns) ? turns : 1.0 };
  }
  return null;
}

// `opts.recipe` (from a share URL's `a=` pair) restores the timeline instead
// of seeding the default sweep; `opts.fromFragment` keeps the just-consumed
// hash in place rather than rewriting it.
function enterAnim(opts) {
  opts = opts || {};
  if (!current) return;
  const info = byName[current];
  if (!info || !info.available) return;
  animOn = true;
  playEl.setAttribute("aria-pressed", "true");
  playEl.textContent = "stop";
  anim = opts.recipe ? recipeToAnim(opts.recipe) : defaultAnim(info, state);
  timelineEl.classList.add("on");
  stageEl.classList.add("anim");
  // The slider panel stays live: moving a slider now pins a keyframe at the
  // scrubber's time instead of re-rendering a still.
  paintTimeline(info, state);
  paintTransport(anim);
  syncScrubber();
  expGifEl.disabled = false;
  // Write the animation fragment unless we just consumed one from the URL
  // (restoring a share URL keeps the landing hash rather than rewriting it
  // over itself). replaceState keeps the back button on one entry per motif.
  if (!opts.fromFragment) writeFragment(current, state, anim, false);
  startAnim(info, state, anim);
}

function exitAnim() {
  animOn = false;
  playEl.setAttribute("aria-pressed", "false");
  playEl.textContent = "play";
  timelineEl.classList.remove("on");
  stageEl.classList.remove("anim");
  expGifEl.disabled = true;
  stopPlayback();
  if (preRaf) { cancelAnimationFrame(preRaf); preRaf = null; }
  bundle = null;
  anim = null;
  hideAnimProgress();
  // Return to a still render of the current slider state.
  const info = byName[current];
  if (info && info.available) render(info, state);
}

function toggleAnim() {
  if (animOn) exitAnim();
  else enterAnim();
}

// --- timeline paint ---------------------------------------------------------
function paintTimeline(info, st) {
  tracksEl.innerHTML = "";
  const params = animatableParams(info);
  if (!params.length) {
    const note = document.createElement("p");
    note.className = "anim-empty";
    note.textContent = "this motif has no animatable parameters";
    tracksEl.appendChild(note);
    return;
  }
  for (const p of params) {
    tracksEl.appendChild(buildTrackRow(info, p, st, anim));
  }
}

function buildTrackRow(info, p, st, an) {
  const row = document.createElement("div");
  row.className = "track";
  const head = document.createElement("div");
  head.className = "track-head";
  const name = document.createElement("span");
  name.className = "track-name";
  name.textContent = p.name;
  const ann = document.createElement("span");
  ann.className = "track-ann";
  ann.textContent = p.annotation.startsWith("Literal") ? "choices" : p.annotation;
  head.appendChild(name);
  head.appendChild(ann);
  // Per-track easing dropdown (defaults to the global easing; "auto" means
  // inherit). The "auto" option keeps the recipe compact.
  const ease = document.createElement("select");
  ease.className = "track-easing";
  const autoOpt = document.createElement("option");
  autoOpt.value = ""; autoOpt.textContent = "auto";
  ease.appendChild(autoOpt);
  for (const e of EASINGS) {
    const o = document.createElement("option");
    o.value = e; o.textContent = e;
    ease.appendChild(o);
  }
  const tr = an.tracks[p.name];
  if (tr && tr.easing) ease.value = tr.easing;
  ease.addEventListener("change", () => {
    if (!an.tracks[p.name]) an.tracks[p.name] = { keyframes: [[0, st[p.name]]], easing: null };
    an.tracks[p.name].easing = ease.value || null;
    restartPlayback(info, st, an);
  });
  head.appendChild(ease);
  row.appendChild(head);

  const lane = document.createElement("div");
  lane.className = "lane";
  lane.dataset.param = p.name;
  paintLaneDots(lane, p, an);
  // Double-click drops a keyframe at the clicked time holding the slider's
  // current value. Click-to-place would fight with dot dragging; a deliberate
  // double-click is unambiguous.
  lane.addEventListener("dblclick", (e) => {
    const rect = lane.getBoundingClientRect();
    const t = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    dropKeyframe(p, st, an, t);
    paintLaneDots(lane, p, an);
    restartPlayback(info, st, an);
  });
  row.appendChild(lane);
  return row;
}

function paintLaneDots(lane, p, an) {
  // Keep the lane element; clear and re-add dots so a redraw after a drop /
  // drag / delete is one DOM write.
  lane.querySelectorAll(".kf").forEach((d) => d.remove());
  const tr = an.tracks[p.name];
  if (!tr) return;
  for (let i = 0; i < tr.keyframes.length; i++) {
    const [t, v] = tr.keyframes[i];
    const dot = document.createElement("span");
    dot.className = "kf";
    dot.style.left = (t * 100) + "%";
    dot.title = `${p.name} @ t=${t.toFixed(2)} = ${formatVal(v)}`;
    dot.dataset.idx = String(i);
    dot.tabIndex = 0;
    dot.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        deleteKeyframe(p, an, i);
        paintLaneDots(lane, p, an);
        restartPlayback(byName[current], state, an);
      }
    });
    dot.addEventListener("pointerdown", (e) => startDotDrag(e, dot, p, an, lane));
    lane.appendChild(dot);
  }
}

// Drag a keyframe dot horizontally to change its time. Vertically is a no-op
// (the value comes from the slider, not the dot's height).
function startDotDrag(e, dot, p, an, lane) {
  e.preventDefault();
  dot.focus();
  const idx = Number(dot.dataset.idx);
  const rect = lane.getBoundingClientRect();
  const move = (ev) => {
    const t = Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width));
    an.tracks[p.name].keyframes[idx][0] = t;
    // Keep keyframes time-sorted so the interpolator and the dot order agree.
    an.tracks[p.name].keyframes.sort((a, b) => a[0] - b[0]);
    paintLaneDots(lane, p, an);
  };
  const up = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", up);
    restartPlayback(byName[current], state, an);
  };
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", up);
}

// Drop a keyframe for `p` at time `t` holding the slider's current value. If a
// keyframe already sits within a small threshold of `t` it is updated in
// place, so a repeated drop at the same time moves the value rather than
// stacking dots.
function dropKeyframe(p, st, an, t) {
  if (!an.tracks[p.name]) an.tracks[p.name] = { keyframes: [], easing: null };
  const kfs = an.tracks[p.name].keyframes;
  const THRESH = 0.01;
  const near = kfs.findIndex((kv) => Math.abs(kv[0] - t) < THRESH);
  const val = clone(st[p.name]);
  if (near >= 0) kfs[near][1] = val;
  else {
    kfs.push([t, val]);
    kfs.sort((a, b) => a[0] - b[0]);
  }
}

function deleteKeyframe(p, an, idx) {
  const kfs = an.tracks[p.name].keyframes;
  if (kfs.length <= 1) return; // keep at least one
  kfs.splice(idx, 1);
}

// --- transport paint --------------------------------------------------------
function paintTransport(an) {
  animFramesEl.value = an.frames;
  animFpsEl.value = an.fps;
  animHoldEl.value = an.hold;
  animHoldEl.max = Math.max(0, Math.floor(an.frames / 4));
  animEaseEl.value = an.easing;
  loopEl.setAttribute("aria-pressed", String(playState.looping));
  // Overlay checkboxes reflect the recipe's overlay list.
  const hasDraw = an.overlays.some((o) => o.type === "draw_on");
  const hasSpin = an.overlays.some((o) => o.type === "spin");
  ovDrawEl.checked = hasDraw;
  ovSpinEl.checked = hasSpin;
  ovDrawOpts.classList.toggle("on", hasDraw);
  ovSpinOpts.classList.toggle("on", hasSpin);
  if (hasDraw) {
    const dr = an.overlays.find((o) => o.type === "draw_on");
    ovTrailEl.value = dr.trail == null ? "" : String(dr.trail);
  }
  if (hasSpin) {
    const sp = an.overlays.find((o) => o.type === "spin");
    ovTurnsEl.value = String(sp.turns == null ? 1 : sp.turns);
  }
}

// --- pre-render + playback --------------------------------------------------
// Build the frame bundle for the current animation. The Python bridge runs
// `keyframes` once and stashes the per-frame Designs; we then fetch each
// frame's SVG in chunked rAF batches so the timeline stays responsive. The
// bundle holds the `frames`-length core (before `hold`); the hold tail is
// synthesised on playback by repeating the last frame, so changing `hold` is
// a free re-playback with no re-render.
function startAnim(info, st, an) {
  stopPlayback();
  if (preRaf) { cancelAnimationFrame(preRaf); preRaf = null; }
  const key = animBundleKey(info, st, an);
  const cached = animCache.get(key);
  if (cached) {
    animCache.delete(key);
    animCache.set(key, cached);
    bundle = { key, core: cached, count: cached.length + an.hold, ready: cached.length, total: cached.length, busy: false };
    showAnimProgress(1);
    startPlayback(info, an);
    return;
  }
  bundle = { key, core: null, count: 0, ready: 0, total: 0, busy: true };
  showAnimProgress(0);
  (async () => {
    await ensurePyodide();
    const out = JSON.parse(pyBuildKeyframes(
      info.name, JSON.stringify(st || {}), JSON.stringify(animRecipe(an).tracks),
      an.frames, an.fps, 0, an.easing, JSON.stringify(an.overlays)
    ));
    if (out.error) {
      bundle = null;
      hideAnimProgress();
      showAnimError(out.error);
      return;
    }
    const total = out.count - 0; // bridge built with hold=0; core length == frames
    const core = new Array(total).fill(null);
    bundle.core = core;
    bundle.total = total;
    bundle.count = total + an.hold;
    preRenderChunks(info, an, 0);
  })();
}

// Fetch PRE_FRAMES_PER_TICK SVGs per rAF tick until the core bundle is full,
// then start playback if it has not already. Playback kicks off as soon as
// the first frame is ready so the user sees motion without waiting on the
// whole run.
function preRenderChunks(info, an, from) {
  let i = from;
  const tick = () => {
    if (!bundle || !bundle.busy) return;
    let made = 0;
    while (i < bundle.total && made < PRE_FRAMES_PER_TICK) {
      const out = JSON.parse(pyRenderFrame(i));
      bundle.core[i] = out.error ? null : out.svg;
      i++; made++;
    }
    bundle.ready = i;
    showAnimProgress(bundle.total ? bundle.ready / bundle.total : 1);
    if (i < bundle.total) {
      preRaf = requestAnimationFrame(tick);
    } else {
      bundle.busy = false;
      hideAnimProgress();
      // Cache the core bundle for replay.
      if (animCache.size >= ANIM_CACHE_SIZE) animCache.delete(animCache.keys().next().value);
      animCache.set(bundle.key, bundle.core.slice());
      if (!playState.on) startPlayback(info, an);
    }
  };
  preRaf = requestAnimationFrame(tick);
}

// rAF playback loop. Each tick advances `idx` by the elapsed-time budget at
// the recipe's fps; the hold tail holds the last core frame for `hold`
// extra frames. Looping wraps to 0; non-looping stops at the end.
function startPlayback(info, an) {
  if (!bundle || !bundle.core) return;
  playState.on = true;
  playState.last = performance.now();
  playState.idx = 0;
  playState.holdLeft = an.hold;
  playPauseEl.textContent = "pause";
  const step = () => {
    if (!playState.on || !bundle) return;
    const now = performance.now();
    const frameMs = 1000 / an.fps;
    const dt = now - playState.last;
    if (dt >= frameMs) {
      const steps = Math.max(1, Math.floor(dt / frameMs));
      playState.last += steps * frameMs;
      for (let s = 0; s < steps; s++) advanceFrame(an);
      drawFrame(playState.idx);
      syncScrubber();
    }
    playState.raf = requestAnimationFrame(step);
  };
  drawFrame(0);
  syncScrubber();
  playState.raf = requestAnimationFrame(step);
}

function advanceFrame(an) {
  const coreLen = bundle.core.length;
  if (playState.idx < coreLen - 1) {
    playState.idx++;
    return;
  }
  // At or past the last core frame: spend the hold tail, then loop or stop.
  if (playState.holdLeft > 0) {
    playState.holdLeft--;
    return;
  }
  if (playState.looping) {
    playState.idx = 0;
    playState.holdLeft = an.hold;
  } else {
    stopPlayback();
  }
}

function stopPlayback() {
  if (playState.raf) cancelAnimationFrame(playState.raf);
  playState.raf = null;
  playState.on = false;
  playPauseEl.textContent = "play";
}

function drawFrame(idx) {
  if (!bundle || !bundle.core) return;
  const svg = bundle.core[Math.min(idx, bundle.core.length - 1)];
  if (!svg) return;
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
  stageEl.insertAdjacentHTML("beforeend", stripXmlDecl(svg));
  placeholderEl.classList.remove("busy", "error");
  placeholderEl.style.display = "none";
  // The display render is a fixed 520x520 canvas, so the stage's zoom/pan
  // viewBox applies the same way it does to a still. We do not preserve zoom
  // across frames (a parameter sweep changes the bounds), so each frame fits.
  captureNatural();
  fitView();
}

// Scrubber -> frame index. The scrubber spans the full core run (the hold
// tail is playback-only and not scrubbed).
function syncScrubber() {
  if (!bundle || !bundle.core) { scrubEl.value = 0; return; }
  const t = bundle.core.length > 1 ? playState.idx / (bundle.core.length - 1) : 0;
  scrubEl.value = Math.min(1, Math.max(0, t));
}

// Restart pre-render + playback after a timeline edit. Reuses the cache when
// the bundle key is unchanged (e.g. a pure playback param changed); otherwise
// starts a fresh build.
function restartPlayback(info, st, an) {
  if (!animOn) return;
  startAnim(info, st, an);
  // The timeline changed, so the share URL's `a=` pair must follow. Debounced
  // so a rapid drag rewrites the hash once, not once per pointermove tick.
  scheduleFragmentWrite();
}

function showAnimError(msg) {
  placeholderEl.classList.add("error");
  placeholderEl.style.display = "";
  phMain.textContent = msg;
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
}

function showAnimProgress(frac) {
  animProgressEl.classList.add("on");
  animProgressFill.style.width = (frac * 100) + "%";
}
function hideAnimProgress() { animProgressEl.classList.remove("on"); }

// --- GIF export -------------------------------------------------------------
// Rebuilds the same run the SPA just played, with the recipe's hold, and
// writes it through the pure-stdlib `save_gif` to Pyodide's in-memory FS. The
// bytes match `geomotif render --animation spec.json` by construction (same
// primitive, same writer, same default export styling).
expGifEl.addEventListener("click", async () => {
  if (!animOn || !current) return;
  expGifEl.disabled = true;
  try {
    await ensurePyodide();
    const info = byName[current];
    const an = anim;
    const result = pyExportGif(
      info.name, JSON.stringify(state || {}), JSON.stringify(animRecipe(an).tracks),
      an.frames, an.fps, an.hold, an.easing, JSON.stringify(an.overlays)
    );
    let data;
    if (result instanceof Uint8Array) {
      data = result.slice();
    } else if (typeof result === "string") {
      // Pyodide surfaces a Python str return as a JS string; the bridge uses
      // that only for the error envelope, so decode it.
      let parsed;
      try { parsed = JSON.parse(result); } catch (e) { throw new Error(result); }
      throw new Error(parsed && parsed.error ? parsed.error : result);
    } else {
      data = new Uint8Array(result);
    }
    download(new Blob([data], { type: "image/gif" }), `${info.name}.gif`);
    flash(expGifEl, true, "saved", "failed");
  } catch (e) {
    flash(expGifEl, false, "saved", "failed");
  } finally {
    expGifEl.disabled = false;
  }
});

// --- transport events -------------------------------------------------------
playPauseEl.addEventListener("click", () => {
  if (!animOn || !bundle) return;
  if (playState.on) stopPlayback();
  else startPlayback(byName[current], anim);
});

loopEl.addEventListener("click", () => {
  playState.looping = !playState.looping;
  loopEl.setAttribute("aria-pressed", String(playState.looping));
});

animFramesEl.addEventListener("input", () => {
  if (!anim) return;
  const v = Math.min(ANIM_FRAMES_MAX, Math.max(ANIM_FRAMES_MIN, Math.round(Number(animFramesEl.value) || anim.frames)));
  anim.frames = v;
  animHoldEl.max = Math.max(0, Math.floor(v / 4));
  if (anim.hold > Math.floor(v / 4)) {
    anim.hold = Math.floor(v / 4);
    animHoldEl.value = anim.hold;
  }
  restartPlayback(byName[current], state, anim);
});

animFpsEl.addEventListener("input", () => {
  if (!anim) return;
  const v = Math.min(ANIM_FPS_MAX, Math.max(ANIM_FPS_MIN, Math.round(Number(animFpsEl.value) || anim.fps)));
  anim.fps = v;
  animFpsEl.value = v;
  // fps is a playback-only param: no re-render, just keep the live loop on the
  // new cadence. It still changes the share URL's recipe, so the fragment
  // follows on the same debounced cadence.
  if (playState.on) {
    stopPlayback();
    startPlayback(byName[current], anim);
  }
  scheduleFragmentWrite();
});

animHoldEl.addEventListener("input", () => {
  if (!anim) return;
  const max = Math.max(0, Math.floor(anim.frames / 4));
  const v = Math.min(max, Math.max(ANIM_HOLD_MIN, Math.round(Number(animHoldEl.value) || 0)));
  anim.hold = v;
  animHoldEl.value = v;
  // hold is a playback-only param: the bundle's core is unchanged, only the
  // tail length moves. No re-render. The recipe's hold rides the share URL,
  // so the fragment follows.
  if (bundle) bundle.count = bundle.core.length + v;
  if (playState.on) {
    stopPlayback();
    startPlayback(byName[current], anim);
  }
  scheduleFragmentWrite();
});

animEaseEl.addEventListener("change", () => {
  if (!anim) return;
  anim.easing = animEaseEl.value;
  restartPlayback(byName[current], state, anim);
});

// Scrubber: drag to scrub (canvas shows the frame at that time), click to
// jump. While scrubbing, playback is paused so the hand on the scrubber is
// the only clock.
scrubEl.addEventListener("pointerdown", () => {
  scrubbing = true;
  if (playState.on) stopPlayback();
});
scrubEl.addEventListener("input", () => {
  if (!bundle || !bundle.core) return;
  const t = Number(scrubEl.value);
  const idx = Math.round(t * (bundle.core.length - 1));
  playState.idx = Math.min(idx, bundle.core.length - 1);
  drawFrame(playState.idx);
});
scrubEl.addEventListener("pointerup", () => { scrubbing = false; });

// Overlay checkboxes. Toggling one adds/removes the matching entry on
// `anim.overlays` and re-renders (overlays are post-passes on the geometry).
function overlayEntry(type) {
  return anim.overlays.find((o) => o.type === type);
}
ovDrawEl.addEventListener("change", () => {
  if (!anim) return;
  if (ovDrawEl.checked) {
    if (!overlayEntry("draw_on")) anim.overlays.push({ type: "draw_on", trail: null });
    const e = overlayEntry("draw_on");
    e.trail = ovTrailEl.value === "" ? null : Number(ovTrailEl.value);
  } else {
    anim.overlays = anim.overlays.filter((o) => o.type !== "draw_on");
  }
  paintTransport(anim);
  restartPlayback(byName[current], state, anim);
});
ovTrailEl.addEventListener("input", () => {
  if (!anim) return;
  const e = overlayEntry("draw_on");
  if (!e) return;
  e.trail = ovTrailEl.value === "" ? null : Number(ovTrailEl.value);
  restartPlayback(byName[current], state, anim);
});
ovSpinEl.addEventListener("change", () => {
  if (!anim) return;
  if (ovSpinEl.checked) {
    if (!overlayEntry("spin")) anim.overlays.push({ type: "spin", turns: 1.0 });
    const e = overlayEntry("spin");
    e.turns = Number(ovTurnsEl.value) || 1.0;
  } else {
    anim.overlays = anim.overlays.filter((o) => o.type !== "spin");
  }
  paintTransport(anim);
  restartPlayback(byName[current], state, anim);
});
ovTurnsEl.addEventListener("input", () => {
  if (!anim) return;
  const e = overlayEntry("spin");
  if (!e) return;
  e.turns = Number(ovTurnsEl.value) || 1.0;
  restartPlayback(byName[current], state, anim);
});

// The Play toggle on the stage toolbar enters / exits animation mode.
playEl.addEventListener("click", () => {
  toggleAnim();
});

// --- go ---------------------------------------------------------------------
boot();
