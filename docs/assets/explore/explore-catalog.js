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
      E.showToast("failed to load catalog.json");
      placeholderEl.textContent = "could not load catalog.json";
      placeholderEl.classList.add("error");
      return;
    }
    E.WHEEL_URL = `./geomotif-${E.catalog.geomotif}-py3-none-any.whl`;
    for (const m of E.catalog.motifs) E.byName[m.name] = m;
    paintFamilies();
    paintMotifs();
    E.showToast("ready — pick a motif");
    E.setStatus("");
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
    // A motif switch while Animate is active stays in Animate mode. The
    // timeline is per-motif, so we still tear down the outgoing animation
    // (bundle + pre-render), but `skipStillRender` keeps exitAnim from firing a
    // wasted still render of the motif we are leaving -- the new motif renders
    // (or re-enters Animate) below. A share URL's `a=` pair (`opts.anim`) still
    // wins over the inherited mode: it boots straight into Animate with that
    // recipe regardless of which mode the user was in.
    const wasAnim = E.animOn;
    if (E.animOn) E.exitAnim({ skipStillRender: true });
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
    // `wasAnim` was torn down above; in Design mode the still write carries no
    // `a=` pair. In Animate mode enterAnim writes the `a=` pair for the fresh
    // default recipe below.
    if (!opts.fromFragment) E.writeFragment(name, E.state, null, false);
    if (!info.available) {
      showUnavailable(info);
      return;
    }
    // A share URL's `a=` pair (decoded into `opts.anim`) boots straight into
    // animation mode with the timeline populated; otherwise a still render --
    // unless the user was already in Animate mode, in which case we re-enter
    // Animate on the new motif with a fresh default recipe.
    if (opts.anim) {
      E.enterAnim({ recipe: opts.anim, fromFragment: opts.fromFragment });
    } else if (wasAnim) {
      E.enterAnim({});
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
    const hadSvg = !!E.motifSvg();
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
      E.motifSvgs().forEach((s) => s.remove());
      phMain.textContent = result.error;
      E.lastSvg = null;
      E.lastMotif = null;
      E.lastParams = null;
      E.lastFrameIdx = -1;
      E.viewBox = null;
      E.naturalVB = null;
      E.scale = null;
      E.dispBounds = null;
      return;
    }
    placeholderEl.classList.remove("busy", "error");
    placeholderEl.style.display = "none";
    E.motifSvgs().forEach((s) => s.remove());
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
    // The renderer carries the world->display scale alongside the picture;
    // refresh it so the grid overlay, the cursor readout and the zoom
    // indicator stay correct after a still render (slider drag, motif switch).
    E.scale = (result.scale != null) ? result.scale : E.scale;
    // The renderer also reports the drawn picture's display bounds; refresh
    // them so "fit to view" frames the motif at its current size (see
    // captureNatural in explore-view.js).
    E.dispBounds = (result.bounds && Number.isFinite(result.bounds.w) && result.bounds.w > 0)
      ? result.bounds : null;
    // A slider drag (same motif, new SVG element) re-applies the user's
    // zoom/pan; switching motifs starts fit-to-view instead, so a new
    // picture is never cropped by the previous one's zoom. "Fit" frames the
    // drawn picture's current bounds (E.dispBounds -> captureNatural), so a
    // resize shows the whole motif again, centered.
    E.captureNatural();
    if (prevMotif === info.name && E.viewBox) E.applyViewBox();
    else E.fitView();
  }
  E.render = render;

  function showUnavailable(info) {
    E.motifSvgs().forEach((s) => s.remove());
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
    E.scale = null;
    E.dispBounds = null;
  }
  E.showUnavailable = showUnavailable;

  function paintMeta(info) {
    const parts = [`<h2 class="motif-title"><code>${E.esc(info.name)}</code></h2>`];
    // The summary is a docstring paragraph, so it carries the same ``code`` /
    // **bold** / *italic* markup the long description does. Escaping alone left
    // the literal backticks on screen; run it through the inline formatter.
    parts.push(`<p class="motif-summary">${E.inlineDoc(info.summary || "")}</p>`);
    const tags = [];
    if (info.family) tags.push(`<span class="badge">${E.esc(info.family)}</span>`);
    if (info.requires) tags.push(`<span class="badge">needs ${E.esc(info.requires)}</span>`);
    if (tags.length) parts.push(`<div class="motif-tags">${tags.join("")}</div>`);
    if (info.doc) parts.push(`<div class="motif-doc">${renderDoc(info.doc, info.summary)}</div>`);
    metaEl.innerHTML = parts.join("");
    E.$("control-title").innerHTML = `<code>${E.esc(info.name)}</code>`;
  }
  E.paintMeta = paintMeta;

  // Render the long-form description as readable paragraphs, not a mono blob.
  // The catalog's `summary` is the docstring's first paragraph, which paintMeta
  // already shows as its own .motif-summary line -- so the leading duplicate is
  // dropped here. A numpydoc section (a title immediately followed by a solid
  // underline) is detected by the underline, wherever the content sits: the
  // "Parameters" section becomes a tidy definition list of per-parameter rows
  // instead of collapsing into one run-on paragraph, and any other section
  // (Returns, Notes, ...) gets a small heading. The surrounding text is escaped
  // first and a tiny inline formatter applies to `code` / ``code``, **bold**
  // and *italic*.
  function renderDoc(doc, summary) {
    let text = String(doc || "").trim();
    if (!text) return "";
    // Drop the first paragraph when it duplicates the summary line.
    const first = text.split(/\n\s*\n/)[0].trim();
    if (summary && first && first === String(summary).trim()) {
      text = text.slice(text.indexOf(first) + first.length).trim();
    }
    const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
    // A block that opens a section: a short title line, then an underline of
    // the same dashed/underscored character, with the section body (which may
    // be indented after the underline, or in the following blocks) after it.
    const isSectionBlock = (block) => /^[A-Za-z][A-Za-z ]*\n[-=~^]{3,}/.test(block);
    const out = [];
    const isParams = (t) => /^Parameters?$/i.test(t);
    let i = 0;
    const n = blocks.length;
    while (i < n) {
      const block = blocks[i];
      const m = block.match(/^([A-Za-z][A-Za-z ]*)\n[-=~^]{3,}(?:\n([\s\S]*))?$/);
      if (m && isSectionBlock(block)) {
        const title = m[1].trim();
        const paramsSec = isParams(title);
        out.push(paramsSec
          ? `<div class="motif-params"><span class="params-title">${E.esc(title)}</span>`
          : `<h3>${E.esc(title)}</h3>`);
        if (m[2] && m[2].trim()) {
          out.push(paramsSec ? renderParam(m[2]) : `<p>${inlineDoc(m[2])}</p>`);
        }
        let j = i + 1;
        while (j < n && !isSectionBlock(blocks[j])) {
          out.push(paramsSec ? renderParam(blocks[j]) : `<p>${inlineDoc(blocks[j])}</p>`);
          j++;
        }
        if (paramsSec) out.push("</div>");
        i = j;
        continue;
      }
      out.push(`<p>${inlineDoc(block)}</p>`);
      i++;
    }
    return out.join("");
  }
  E.renderDoc = renderDoc;

  // One numpydoc parameter list, possibly many entries in a single block: each
  // parameter opens at column 0 with `name : type` and its description
  // continues on the following indented lines; the next parameter starts at
  // column 0 again. Each entry is rendered as a tidy row -- name, then the
  // type tag and the description -- so a card of many parameters stays
  // scannable instead of collapsing into one run-on paragraph.
  function renderParam(block) {
    const items = [];
    let cur = null;
    for (const raw of block.split("\n")) {
      if (!raw.trim()) continue;
      if (/^\s+/.test(raw)) {
        // An indented line continues the current parameter's description.
        if (cur) cur.desc.push(raw.trim());
        continue;
      }
      const m = raw.trim().match(/^([^:]+):\s*(.*)$/);
      if (m) {
        if (cur) items.push(cur);
        cur = { name: m[1].trim(), type: m[2].trim(), desc: [] };
      } else if (cur) {
        cur.desc.push(raw.trim()); // a stray non-indented continuation line
      } else {
        cur = { name: raw.trim(), type: "", desc: [] };
      }
    }
    if (cur) items.push(cur);
    return items.map((it) =>
      `<div class="param-row"><code class="param-name">${E.esc(it.name)}</code>` +
      (it.type ? `<span class="param-type">${inlineDoc(it.type)}</span>` : "") +
      (it.desc.length ? `<span class="param-desc">${inlineDoc(it.desc.join(" "))}</span>` : "") +
      `</div>`
    ).join("");
  }
  E.renderParam = renderParam;
  function inlineDoc(text) {
    let s = E.esc(text);
    s = s.replace(/(``[^`]+``|`[^`]+`)/g, (m) => `<code>${m.replace(/`/g, "")}</code>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|\W)\*([^*\n]+)\*/g, "$1<em>$2</em>");
    return s;
  }

  // Exported so the summary line (paintMeta) formats like the description body.
  E.inlineDoc = inlineDoc;

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
