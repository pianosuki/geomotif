"use strict";

// View layer: small shared helpers (XML prolog strip, HTML escape, status,
// progress, flash, download) and the stage's zoom/pan + theme/grid/axes/labels
// toggles. Everything is pure client-side viewBox math on the already-rendered
// SVG (never calls Pyodide, never busts the LRU), and the toggle state
// persists in localStorage across sessions. The coordinate grid overlay is
// painted by explore-grid.js; this module owns the toggle buttons, the cursor
// coordinate readout, and the zoom indicator.

(function (E) {
  const {
    stageEl, themeEl, tgGridEl, tgAxesEl, tgLabelsEl,
    tgPopoverEl, tgGearEl,
    coordReadoutEl, zoomIndEl,
    zoomInEl, zoomOutEl, fitEl, toastEl,
    statusEl, progressEl, progressFill,
    ZOOM_STEP, THEME_KEY, GRID_KEY, AXES_KEY, LABELS_KEY,
  } = E;

  // --- small helpers ----------------------------------------------------------
  function stripXmlDecl(svg) {
    const s = svg.trim();
    return s.startsWith("<?xml") ? s.split("?>", 2)[1].trimStart() : s;
  }
  E.stripXmlDecl = stripXmlDecl;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
    ));
  }
  E.esc = esc;

  function setStatus(t) { statusEl.textContent = t; }
  E.setStatus = setStatus;
  // A transient load-status toast: a small fixed pill at the bottom of the
  // viewport that auto-dismisses after ~2.5s. Boot-and-render progress ("ready",
  // "loading Pyodide…", …) surfaces here instead of as a string stranded forever
  // in the header's #status slot.
  let toastTimer = null;
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2500);
  }
  E.showToast = showToast;
  function showProgress(frac) { progressEl.classList.add("on"); progressFill.style.width = (frac * 100) + "%"; }
  E.showProgress = showProgress;
  function hideProgress() { progressEl.classList.remove("on"); }
  E.hideProgress = hideProgress;

  // --- zoom / pan --------------------------------------------------------------
  // Wheel zooms around the cursor; a left-button drag pans; the toolbar buttons
  // zoom around the centre and "fit" restores the natural viewBox. Everything is
  // pure client-side viewBox math on the already-rendered SVG, so it never calls
  // Pyodide and never busts the LRU (the cache key stays name + params).
  function svgRect() {
    const svg = stageEl.querySelector("svg:not(.grid-overlay)");
    return svg ? svg.getBoundingClientRect() : null;
  }

  // Read the rendered <svg>'s own viewBox into `naturalVB` -- the box the
  // "fit" button restores to. The display render is a fixed 520x520 canvas, so
  // in practice this is always {0,0,520,520}, but reading it from the element
  // keeps the code honest if that ever changes.
  function captureNatural() {
    const svg = stageEl.querySelector("svg:not(.grid-overlay)");
    if (!svg) { E.naturalVB = null; return; }
    const vb = svg.viewBox && svg.viewBox.baseVal;
    if (vb && vb.width > 0 && vb.height > 0) {
      E.naturalVB = { x: vb.x, y: vb.y, w: vb.width, h: vb.height };
    } else {
      E.naturalVB = { x: 0, y: 0, w: 520, h: 520 };
    }
  }
  E.captureNatural = captureNatural;

  function applyViewBox() {
    const svg = stageEl.querySelector("svg:not(.grid-overlay)");
    if (!svg || !E.viewBox) return;
    svg.setAttribute("viewBox", `${E.viewBox.x} ${E.viewBox.y} ${E.viewBox.w} ${E.viewBox.h}`);
    // The grid overlay mirrors the motif's box on every zoom/pan tick, and the
    // zoom indicator (the factor relative to the motif's natural box) follows
    // along so it stays correct through wheel-zoom, pan, fit, and the buttons.
    if (E.paintGrid) E.paintGrid();
    updateZoomInd();
  }
  E.applyViewBox = applyViewBox;

  function zoomAround(factor, cx, cy) {
    if (!E.viewBox) return;
    // Zoom around a viewBox-space point (cx, cy); leave it fixed on screen.
    const newW = Math.max(1e-6, E.viewBox.w * factor);
    const newH = Math.max(1e-6, E.viewBox.h * factor);
    // Clamp so a single motif never zooms in past ~50x of its natural box
    // (keeps the float precision sane) or out beyond 0.1x (still visible).
    const lim = (n, n0) => {
      const lo = n0 * 0.02, hi = n0 * 50;
      return Math.min(hi, Math.max(lo, n));
    };
    const W = lim(newW, E.naturalVB.w), H = lim(newH, E.naturalVB.h);
    const real = W / E.viewBox.w;
    E.viewBox.x = cx - (cx - E.viewBox.x) * real;
    E.viewBox.y = cy - (cy - E.viewBox.y) * real;
    E.viewBox.w = W;
    E.viewBox.h = H;
    applyViewBox();
  }
  E.zoomAround = zoomAround;

  function zoomCenter(factor) {
    if (!E.viewBox) return;
    zoomAround(factor, E.viewBox.x + E.viewBox.w / 2, E.viewBox.y + E.viewBox.h / 2);
  }
  E.zoomCenter = zoomCenter;

  function fitView() {
    if (!E.naturalVB) return;
    E.viewBox = { ...E.naturalVB };
    applyViewBox();
  }
  E.fitView = fitView;

  stageEl.addEventListener("wheel", (e) => {
    if (!E.viewBox) return;
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
    const cx = E.viewBox.x + px * E.viewBox.w;
    const cy = E.viewBox.y + py * E.viewBox.h;
    const factor = e.deltaY < 0 ? 1 / ZOOM_STEP : ZOOM_STEP;
    zoomAround(factor, cx, cy);
  }, { passive: false });

  stageEl.addEventListener("pointerdown", (e) => {
    if (!E.viewBox || e.button !== 0) return;
    // Ignore presses on the floating toolbar so its buttons still work.
    if (e.target.closest(".stage-toolbar")) return;
    E.pan = {
      x: e.clientX, y: e.clientY,
      vx: E.viewBox.x, vy: E.viewBox.y, w: E.viewBox.w, h: E.viewBox.h,
    };
    try { stageEl.setPointerCapture(e.pointerId); } catch (err) { /* old browser */ }
  });
  stageEl.addEventListener("pointermove", (e) => {
    if (!E.pan) return;
    const r = svgRect();
    if (!r || !r.width || !r.height) return;
    // A cursor move of dx screen px maps to dx / r.width * viewBox.w user units.
    // Dragging right moves the picture right, so viewBox.x moves left.
    const dx = (e.clientX - E.pan.x) / r.width * E.pan.w;
    const dy = (e.clientY - E.pan.y) / r.height * E.pan.h;
    E.viewBox.x = E.pan.vx - dx;
    E.viewBox.y = E.pan.vy - dy;
    applyViewBox();
  });
  function endPan() { E.pan = null; }
  stageEl.addEventListener("pointerup", endPan);
  stageEl.addEventListener("pointercancel", endPan);
  stageEl.addEventListener("pointerleave", endPan);

  zoomInEl.addEventListener("click", () => zoomCenter(1 / ZOOM_STEP));
  zoomOutEl.addEventListener("click", () => zoomCenter(ZOOM_STEP));
  fitEl.addEventListener("click", fitView);

  // --- view toggles (theme / grid / border) ------------------------------------
  // The theme is set on first paint by the inline head script from the stored
  // preference (or the OS preference). Here we wire the manual switch: clicking
  // flips data-theme, persists the choice, and updates the button label. We also
  // track OS changes so a user who never touched the switch still follows their
  // OS as it moves -- the stored choice is the only thing that overrides that.
  function effectiveTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function applyThemeButton() {
    // The button shows a sun glyph in light mode and a moon in dark mode, so
    // the icon always reads as "the mode that is on now"; aria-pressed tracks
    // "dark mode active", and the accent fill (see app.css) means "dark is on".
    themeEl.setAttribute("aria-pressed", String(effectiveTheme() === "dark"));
  }
  E.applyThemeButton = applyThemeButton;

  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem(THEME_KEY, t); } catch (e) { /* private mode */ }
    applyThemeButton();
    // The grid overlay reads --line / --ink / --muted from CSS, so a theme
    // switch has to invalidate its color cache and repaint.
    if (E.invalidateGridColors) E.invalidateGridColors();
    if (E.paintGrid) E.paintGrid();
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
    if (E.invalidateGridColors) E.invalidateGridColors();
    if (E.paintGrid) E.paintGrid();
  });
  else if (mq.addListener) mq.addListener((e) => { /* Safari < 14 fallback */ });

  // The grid / axes / labels trio carries over between sessions the same way
  // the old single grid toggle did; their state is read at boot by
  // initViewToggles and applied as classes on .stage. The classes drive the
  // overlay: .no-grid hides the whole overlay SVG; .no-axes and .no-labels
  // toggle the axis and label groups inside it (see app.css).
  function readToggle(key, def) {
    try { const v = localStorage.getItem(key); return v == null ? def : v === "on"; }
    catch (e) { return def; }
  }
  function writeToggle(key, on) {
    try { localStorage.setItem(key, on ? "on" : "off"); } catch (e) { /* private */ }
  }

  function syncToggle(el, on) { el.setAttribute("aria-pressed", String(on)); }

  tgGridEl.addEventListener("click", () => {
    const on = !stageEl.classList.contains("no-grid");
    stageEl.classList.toggle("no-grid");
    syncToggle(tgGridEl, !on);
    writeToggle(GRID_KEY, !on);
  });
  tgAxesEl.addEventListener("click", () => {
    const on = !stageEl.classList.contains("no-axes");
    stageEl.classList.toggle("no-axes");
    syncToggle(tgAxesEl, !on);
    writeToggle(AXES_KEY, !on);
  });
  tgLabelsEl.addEventListener("click", () => {
    const on = !stageEl.classList.contains("no-labels");
    stageEl.classList.toggle("no-labels");
    syncToggle(tgLabelsEl, !on);
    writeToggle(LABELS_KEY, !on);
  });

  // The gear popover: under 50rem the three view toggles collapse into a
  // gear-triggered popover (CSS hides the body and floats it under the gear on
  // narrow viewports; on wide viewports the body unwraps inline and the gear is
  // hidden). The gear click toggles the wrapper's `.open` class and mirrors
  // aria-expanded; a click outside the popover or an Escape closes it. The
  // popover closes when the viewport crosses back to wide so an open popover
  // never collides with the inline toggles re-appearing.
  if (tgPopoverEl && tgGearEl) {
    function closePopover() {
      tgPopoverEl.classList.remove("open");
      tgGearEl.setAttribute("aria-expanded", "false");
    }
    function openPopover() {
      tgPopoverEl.classList.add("open");
      tgGearEl.setAttribute("aria-expanded", "true");
    }
    tgGearEl.addEventListener("click", (e) => {
      e.stopPropagation();
      tgPopoverEl.classList.contains("open") ? closePopover() : openPopover();
    });
    document.addEventListener("click", (e) => {
      if (!tgPopoverEl.classList.contains("open")) return;
      if (!tgPopoverEl.contains(e.target)) closePopover();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && tgPopoverEl.classList.contains("open")) closePopover();
    });
    const gearMq = window.matchMedia("(max-width: 50rem)");
    if (gearMq.addEventListener) gearMq.addEventListener("change", () => closePopover());
    else if (gearMq.addListener) gearMq.addListener(() => closePopover());
  }

  function initViewToggles() {
    // All three default to on, so the stage opens with a full coordinate
    // plane; a user who has turned one off restores that choice.
    if (!readToggle(GRID_KEY, true)) stageEl.classList.add("no-grid");
    if (!readToggle(AXES_KEY, true)) stageEl.classList.add("no-axes");
    if (!readToggle(LABELS_KEY, true)) stageEl.classList.add("no-labels");
    syncToggle(tgGridEl, !stageEl.classList.contains("no-grid"));
    syncToggle(tgAxesEl, !stageEl.classList.contains("no-axes"));
    syncToggle(tgLabelsEl, !stageEl.classList.contains("no-labels"));
    applyThemeButton();
    if (E.paintGrid) E.paintGrid();
    updateZoomInd();
  }
  E.initViewToggles = initViewToggles;

  // --- cursor coordinate readout + zoom indicator -------------------------
  // The readout maps the pointer's screen position into the live viewBox units
  // and shows `x: 12.3  y: -4.5` pinned to the bottom-left of the stage. It is
  // filled on pointermove and cleared when the pointer leaves (or when no
  // viewBox is live). Pure client-side math via svgRect() + E.viewBox.
  function fmtCoord(v) {
    if (Math.abs(v) < 1e-9) return "0";
    const s = Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1);
    return s.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
  }
  function updateReadout(e) {
    if (!E.viewBox) { coordReadoutEl.textContent = ""; return; }
    const r = svgRect();
    if (!r || !r.width || !r.height) return;
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    const cx = E.viewBox.x + px * E.viewBox.w;
    const cy = E.viewBox.y + py * E.viewBox.h;
    coordReadoutEl.textContent = `x: ${fmtCoord(cx)}  y: ${fmtCoord(cy)}`;
  }
  stageEl.addEventListener("pointermove", updateReadout);
  stageEl.addEventListener("pointerleave", () => { coordReadoutEl.textContent = ""; });

  // The zoom indicator is the factor of the motif's natural box currently in
  // view (natural.w / view.w): 1.0x at fit, >1 when zoomed in, <1 when zoomed
  // out. Updated on every applyViewBox; cleared when there is no viewBox.
  function updateZoomInd() {
    if (!E.viewBox || !E.naturalVB || !(E.naturalVB.w > 0)) {
      zoomIndEl.textContent = "";
      return;
    }
    const z = E.naturalVB.w / E.viewBox.w;
    zoomIndEl.textContent = (z >= 100 ? z.toFixed(0) : z >= 10 ? z.toFixed(1) : z.toFixed(2)) + "x";
  }
  E.updateZoomInd = updateZoomInd;
  // Exposed for the smoke harness: the readout + its formatter so the
  // screen -> viewBox mapping can be exercised without a real pointer event.
  E.updateReadout = updateReadout;
  E.fmtCoord = fmtCoord;

  // --- export helpers ----------------------------------------------------------
  function flash(btn, ok, okText, failText) {
    const orig = btn.dataset.label || btn.textContent;
    btn.textContent = ok ? okText : failText;
    if (ok) btn.classList.add("ok");
    setTimeout(() => { btn.textContent = orig; btn.classList.remove("ok"); }, 1400);
  }
  E.flash = flash;

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
  E.download = download;
})(window.EXPLORE);
