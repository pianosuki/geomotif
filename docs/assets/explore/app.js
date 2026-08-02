"use strict";

// --- constants ---------------------------------------------------------------
// Pyodide ships from the official CDN; the version is a single pin so a later
// step can vendor it for offline use. The geomotif wheel is copied next to the
// SPA at deploy time (Step 10); its name carries the catalog's version, so the
// pinned build and the runtime stay in lockstep automatically.
const PYODIDE_VERSION = "0.26.4";
const CACHE_SIZE = 256;

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
// The still spec is encoded into the URL fragment as base64url of a compact
// JSON blob `{"m": motif, "p": params}`. The SPA decodes it on boot to restore
// the selected motif and its slider state. base64url keeps the hash free of
// `+`/`/`/`=` so it never needs percent-encoding. The CLI never sees this
// compact form: the SPA expands it back to the full `{"motif":..., "params":...}`
// shape before calling from_spec, so a shared view round-trips with
// `geomotif render --spec` byte-for-byte by construction.
//
// `m=` is a one-char discriminator so a later step can add an `a=` animation
// fragment alongside the still one without colliding.
const FRAGMENT_PREFIX = "m=";

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
    selectMotif(restored.motif, restored.params, { fromFragment: true });
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
  if (!opts.fromFragment) writeFragment(name, state, false);
  if (!info.available) {
    showUnavailable(info);
    return;
  }
  render(info, state);
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
    writeFragment(info.name, st, false);
    requestAnimationFrame(() => render(info, st));
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
function encodeFragment(motif, params) {
  const json = JSON.stringify({ m: motif, p: params });
  // btoa handles Latin-1; motif params are ASCII (numbers, strings, arrays,
  // plain objects), so no UTF-8 re-encoding is needed.
  const b64 = btoa(json);
  return "#" + FRAGMENT_PREFIX + b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeFragment(hash) {
  if (!hash) return null;
  let frag = String(hash);
  if (frag.startsWith("#")) frag = frag.slice(1);
  if (!frag.startsWith(FRAGMENT_PREFIX)) return null;
  let b64 = frag.slice(FRAGMENT_PREFIX.length).replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4) b64 += "=";
  try {
    const obj = JSON.parse(atob(b64));
    if (!obj || typeof obj.m !== "string") return null;
    const params = obj.p;
    if (params != null && typeof params !== "object") return null;
    return { motif: obj.m, params: params || {} };
  } catch (e) {
    return null;
  }
}

function readFragment() {
  return decodeFragment(location.hash);
}

// Write the current view into the URL fragment. `push` false uses replaceState
// (in-session sync); `push` true uses pushState (explicit share, a real
// history entry the back button can return to).
function writeFragment(motif, params, push) {
  const frag = encodeFragment(motif, params);
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
// is the one the address bar shows afterwards.
shareEl.addEventListener("click", async () => {
  if (!current) return;
  try {
    writeFragment(current, state, true);
    await navigator.clipboard.writeText(location.href);
    shareEl.textContent = "copied";
    shareEl.classList.add("ok");
    setTimeout(() => { shareEl.textContent = "copy share URL"; shareEl.classList.remove("ok"); }, 1200);
  } catch (e) {
    shareEl.textContent = "copy failed";
  }
});

// Restoring from a back/forward navigation: the browser fires popstate when the
// user lands on a fragment we wrote. Re-seed state from it so the back button
// walks through shared views rather than jumping past them.
window.addEventListener("popstate", () => {
  const restored = readFragment();
  if (restored && byName[restored.motif]) {
    selectMotif(restored.motif, restored.params, { fromFragment: true });
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
  // loads straight into `geomotif render --spec <file>`.
  const spec = {
    geomotif: catalog ? catalog.geomotif : null,
    motif: lastMotif,
    params: state,
  };
  const blob = new Blob([JSON.stringify(spec, null, 2) + "\n"], { type: "application/json" });
  download(blob, `${lastMotif}.json`);
  flash(expSpecEl, true, "saved", "failed");
});

// --- go ---------------------------------------------------------------------
boot();
