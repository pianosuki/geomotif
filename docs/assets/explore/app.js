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

_EXC = (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RecursionError)

def render_motif(name, params_json):
    try:
        params = json.loads(params_json) if params_json else {}
        motif = from_spec({"motif": name, "params": params})
        design = motif.build()
        svg = to_svg(design, width=520, height=520, precision=1, title=None)
        return json.dumps({"svg": svg, "error": None})
    except _EXC as e:
        return json.dumps({"svg": None, "error": type(e).__name__ + ": " + str(e)})
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
let WHEEL_URL = "";

// LRU cache, insertion-ordered: the oldest entry is evicted when full.
const cache = new Map();

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
const commandEl = $("command");
const copyEl = $("copy");

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
  // First paint is the shell; Pyodide loads lazily on first render.
  const first = catalog.motifs.find((m) => m.available) || catalog.motifs[0];
  if (first) selectMotif(first.name);
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
function selectMotif(name) {
  current = name;
  const info = byName[name];
  if (!info) return;
  // Each motif's working state begins at its registered example -- the curated
  // picture the gallery shows. Step 4's controls mutate this object; until then
  // it holds still and the command line reflects the example.
  state = { ...info.example };
  paintMotifs();
  paintMeta(info);
  paintCommand(info, state);
  if (!info.available) {
    showUnavailable(info);
    return;
  }
  render(info, state);
}

async function render(info, params) {
  placeholderEl.classList.remove("error");
  placeholderEl.classList.add("busy");
  phMain.textContent = "rendering…";
  placeholderEl.style.display = "";
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
    phMain.textContent = result.error;
    return;
  }
  placeholderEl.classList.remove("busy", "error");
  placeholderEl.style.display = "none";
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
  stageEl.insertAdjacentHTML("beforeend", stripXmlDecl(result.svg));
}

function showUnavailable(info) {
  stageEl.querySelectorAll("svg").forEach((s) => s.remove());
  placeholderEl.classList.remove("busy");
  placeholderEl.classList.add("error");
  placeholderEl.style.display = "";
  phMain.textContent =
    `This motif needs ${info.requires} to build, which Pyodide does not yet load. ` +
    "Try it locally: pip install scipy && geomotif render " + info.name;
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

// --- go ---------------------------------------------------------------------
boot();
