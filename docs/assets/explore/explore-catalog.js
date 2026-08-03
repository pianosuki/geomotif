"use strict";

// Catalog browse + motif selection + still render. `boot()` fetches
// catalog.json, builds the family chips and motif list, and either restores a
// shared view from the URL fragment or selects the first available motif.
// `selectMotif` seeds the parameter state, paints the controls + command line,
// and dispatches a still render (or enters animation mode when a share URL's
// `a=` pair is present).

(function (E) {
  const {
    familiesEl, motifsEl, stageEl, placeholderEl, phMain, metaEl,
    expSvgEl, expPngEl, expSpecEl, expGifEl,
    RESERVED,
  } = E;

  async function boot() {
    try {
      const res = await fetch("catalog.json");
      E.catalog = await res.json();
    } catch (e) {
      E.setStatus("failed to load catalog.json");
      placeholderEl.textContent = "could not load catalog.json";
      placeholderEl.classList.add("error");
      return;
    }
    E.WHEEL_URL = `./geomotif-${E.catalog.geomotif}-py3-none-any.whl`;
    for (const m of E.catalog.motifs) E.byName[m.name] = m;
    paintFamilies();
    paintMotifs();
    E.setStatus("ready — pick a motif");
    // A shared view arrives in the URL fragment; if present it wins over the
    // default first motif so landing on a share URL boots straight into the
    // sender's state. Otherwise we fall back to the first available motif.
    const restored = E.readFragment();
    if (restored && E.byName[restored.motif]) {
      selectMotif(restored.motif, restored.params, { fromFragment: true, anim: restored.anim });
    } else {
      const first = E.catalog.motifs.find((m) => m.available) || E.catalog.motifs[0];
      if (first) selectMotif(first.name);
    }
  }
  E.boot = boot;

  function paintFamilies() {
    const all = document.createElement("button");
    all.textContent = "all";
    all.className = "on";
    all.addEventListener("click", () => {
      E.familyFilter = null;
      [...familiesEl.children].forEach((b) => (b.className = ""));
      all.className = "on";
      paintMotifs();
    });
    familiesEl.appendChild(all);
    for (const f of E.catalog.families) {
      const b = document.createElement("button");
      b.textContent = `${f.name} (${f.count})`;
      b.addEventListener("click", () => {
        E.familyFilter = f.name;
        [...familiesEl.children].forEach((x) => (x.className = ""));
        b.className = "on";
        paintMotifs();
      });
      familiesEl.appendChild(b);
    }
  }

  function paintMotifs() {
    motifsEl.innerHTML = "";
    const q = E.searchQuery.toLowerCase();
    const list = E.catalog.motifs.filter((m) => {
      if (E.familyFilter && m.family !== E.familyFilter) return false;
      if (q && !m.name.includes(q) && !(m.summary || "").toLowerCase().includes(q)) return false;
      return true;
    });
    for (const m of list) {
      const li = document.createElement("li");
      if (!m.available) li.className = "unavailable";
      if (m.name === E.current) li.classList.add("on");
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
  E.paintMotifs = paintMotifs;

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
    if (E.animOn) E.exitAnim();
    E.current = name;
    const info = E.byName[name];
    if (!info) return;
    // Working state begins from the motif's registered example -- the curated
    // picture the gallery shows -- overlaid on the declared default for every
    // settable parameter the example does not mention, so each control has a
    // starting value. Non-settable params that the example does not name are
    // left out entirely: their real default (a function, a Projection, ...) is
    // not a value the SPA can or should round-trip, and `from_spec` falls back
    // to the motif's own default when they are absent.
    E.state = initState(info);
    if (override) E.applyOverride(E.state, info, override);
    paintMotifs();
    paintMeta(info);
    E.paintControls(info, E.state, !info.available);
    E.paintCommand(info, E.state);
    // Export needs a built design; scipy-only motifs cannot build under Pyodide
    // so their export buttons stay disabled alongside their controls.
    const canExport = !!info.available;
    [expSvgEl, expPngEl, expSpecEl].forEach((b) => { b.disabled = !canExport; });
    expGifEl.disabled = true; // GIF export is animation-mode only
    // `animOn` was torn down above, so the still write carries no `a=` pair.
    if (!opts.fromFragment) E.writeFragment(name, E.state, null, false);
    if (!info.available) {
      showUnavailable(info);
      return;
    }
    // A share URL's `a=` pair (decoded into `opts.anim`) boots straight into
    // animation mode with the timeline populated; otherwise a still render.
    if (opts.anim) {
      E.enterAnim({ recipe: opts.anim, fromFragment: opts.fromFragment });
    } else {
      render(info, E.state);
    }
  }
  E.selectMotif = selectMotif;

  // Build the initial parameter state for a motif. Example values win; settable
  // params not in the example take their declared default; everything else is
  // omitted so the Python bridge uses the motif's real default for it.
  function initState(info) {
    const st = {};
    for (const p of info.params) {
      if (RESERVED.has(p.name)) continue;
      if (p.name in info.example) st[p.name] = clone(info.example[p.name]);
      else if (E.isSettable(p)) st[p.name] = clone(p.default);
    }
    return st;
  }
  E.initState = initState;

  function clone(v) {
    if (v == null || typeof v !== "object") return v;
    return JSON.parse(JSON.stringify(v));
  }
  E.clone = clone;

  async function render(info, params) {
    // Only show the "rendering..." placeholder on the first render, when the
    // stage has no SVG yet. On subsequent debounced updates we keep the current
    // picture in place and swap it once the new one is ready, so slider drags
    // never flash a placeholder between frames.
    const hadSvg = !!stageEl.querySelector("svg:not(.grid-overlay)");
    if (!hadSvg) {
      placeholderEl.classList.remove("error");
      placeholderEl.classList.add("busy");
      phMain.textContent = "rendering…";
      placeholderEl.style.display = "";
    }
    let result;
    try {
      result = await E.renderMotif(info.name, params);
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
      stageEl.querySelectorAll("svg:not(.grid-overlay)").forEach((s) => s.remove());
      phMain.textContent = result.error;
      E.lastSvg = null;
      E.lastMotif = null;
      E.lastParams = null;
      E.lastFrameIdx = -1;
      E.viewBox = null;
      E.naturalVB = null;
      return;
    }
    placeholderEl.classList.remove("busy", "error");
    placeholderEl.style.display = "none";
    stageEl.querySelectorAll("svg:not(.grid-overlay)").forEach((s) => s.remove());
    stageEl.insertAdjacentHTML("beforeend", E.stripXmlDecl(result.svg));
    // Remember the full-prolog SVG (the bytes the CLI writes) and the inputs
    // that produced it, for the SVG / PNG / spec exporters. The display copy is
    // the prolog-stripped version; the export copy keeps the prolog so a
    // downloaded .svg opens standalone and round-trips with save_svg.
    const prevMotif = E.lastMotif;
    E.lastSvg = result.svg;
    E.lastMotif = info.name;
    E.lastParams = params;
    E.lastFrameIdx = -1; // a still render clears the frame marker
    // The renderer always emits viewBox="0 0 520 520", so a slider drag (same
    // motif, new SVG element) can keep the user's zoom/pan: reapply the live
    // box to the new <svg>. Switching motifs starts fit-to-view instead, so a
    // new picture is never cropped by the previous one's zoom.
    E.captureNatural();
    if (prevMotif === info.name && E.viewBox) E.applyViewBox();
    else E.fitView();
  }
  E.render = render;

  function showUnavailable(info) {
    stageEl.querySelectorAll("svg:not(.grid-overlay)").forEach((s) => s.remove());
    placeholderEl.classList.remove("busy");
    placeholderEl.classList.add("error");
    placeholderEl.style.display = "";
    phMain.textContent =
      `This motif needs ${info.requires} to build, which Pyodide does not yet load. ` +
      "Try it locally: pip install scipy && geomotif render " + info.name;
    E.lastSvg = null;
    E.lastMotif = null;
    E.lastParams = null;
    E.lastFrameIdx = -1;
    E.viewBox = null;
    E.naturalVB = null;
  }
  E.showUnavailable = showUnavailable;

  function paintMeta(info) {
    const parts = [`<h2><code>${E.esc(info.name)}</code></h2>`];
    parts.push(`<p class="summary">${E.esc(info.summary || "")}</p>`);
    if (info.requires) {
      parts.push(`<p><span class="badge">needs ${E.esc(info.requires)}</span></p>`);
    }
    if (info.doc) {
      parts.push(`<div class="doc">${E.esc(info.doc)}</div>`);
    }
    metaEl.innerHTML = parts.join("");
    E.$("control-title").innerHTML = `<code>${E.esc(info.name)}</code>`;
  }
  E.paintMeta = paintMeta;

  // --- debounced render + fragment sync ---------------------------------------
  // The hash is updated on the same ~30 ms cadence as the render so a slider
  // drag never spams the history stack. replaceState keeps the back button
  // working as one entry per motif session; pushState is reserved for the
  // explicit "copy share URL" action so a shared view is its own bookmarkable
  // entry.
  function scheduleRender(info, st) {
    if (E.renderTimer) clearTimeout(E.renderTimer);
    E.renderTimer = setTimeout(() => {
      E.renderTimer = null;
      E.writeFragment(info.name, st, E.animOn ? E.anim : null, false);
      requestAnimationFrame(() => render(info, st));
    }, E.RENDER_DEBOUNCE_MS);
  }
  E.scheduleRender = scheduleRender;

  // --- search -----------------------------------------------------------------
  const searchEl = document.querySelector(".search");
  searchEl.addEventListener("input", () => {
    E.searchQuery = searchEl.value.trim();
    paintMotifs();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== searchEl) {
      e.preventDefault();
      searchEl.focus();
    }
  });
})(window.EXPLORE);
