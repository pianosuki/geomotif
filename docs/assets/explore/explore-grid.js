"use strict";

// Coordinate grid overlay: a Desmos-style coordinate plane
// rendered as an SVG layer behind the motif. The overlay is the first child
// of .stage; its viewBox attribute mirrors E.viewBox on every zoom/pan tick,
// so the plane stays aligned with the picture as the user moves around. On
// every applyViewBox() call (and on a theme switch) explore-view.js asks this
// module to repaint, which recomputes a "nice" step from the live viewBox
// width, draws major (solid --line-2) and minor (dotted --line) gridlines,
// the x/y axes through the origin with small arrowheads, and tick labels in
// --muted mono -- but only when they fit without crowding (a density check
// caps the label count).
//
// Pure client-side viewBox math: no Pyodide, no cache impact (the LRU stays
// keyed on geometry). The .no-grid class on .stage hides the whole overlay;
// .no-axes and .no-labels toggle the axis and label groups inside it. The
// toggle buttons themselves are wired in explore-view.js, which owns the
// localStorage persistence (geomotif.grid / .axes / .labels).

(function (E) {
  const SVGNS = "http://www.w3.org/2000/svg";
  let overlay, gMinor, gMajor, gAxes, gLabels;

  // The overlay reads the theme's stroke/label tokens from CSS so it switches
  // with the rest of the UI. We cache per theme and only re-read when the
  // theme actually changes (the tokens flip via [data-theme]); a repaint
  // during a drag would otherwise call getComputedStyle on every tick.
  let cachedTheme = null;
  let colors = null;
  function readColors() {
    const t = document.documentElement.dataset.theme || "light";
    if (t === cachedTheme && colors) return colors;
    cachedTheme = t;
    const cs = getComputedStyle(document.documentElement);
    const get = (n) => cs.getPropertyValue(n).trim();
    colors = {
      line: get("--line"),
      line2: get("--line-2"),
      ink: get("--ink"),
      muted: get("--muted"),
    };
    return colors;
  }
  // Force a re-read on the next paint -- called after a theme switch.
  E.invalidateGridColors = () => { cachedTheme = null; };

  function ensure() {
    if (overlay) return;
    overlay = E.gridOverlayEl;
    if (!overlay) return;
    gMinor = overlay.querySelector(".grid-minor");
    gMajor = overlay.querySelector(".grid-major");
    gAxes = overlay.querySelector(".grid-axes");
    gLabels = overlay.querySelector(".grid-labels");
  }

  // Pick a "nice" step (~1, 2, 5 x 10^k) so roughly `target` lines span
  // `range` -- the standard chart-axis heuristic. Returns 1 as a floor so a
  // very tight zoom never divides by a sub-unit mess.
  function niceStep(range, target) {
    if (!(range > 0) || !(target > 0)) return 1;
    const raw = range / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    let s;
    if (norm < 1.5) s = 1;
    else if (norm < 3) s = 2;
    else if (norm < 7) s = 5;
    else s = 10;
    return s * mag;
  }
  E.niceStep = niceStep;

  function el(name, attrs) {
    const e = document.createElementNS(SVGNS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // Format a tick value without trailing zeros: integers stay integer, sub-
  // unit values keep two decimals so the grid reads precisely on a deep zoom.
  function fmt(v) {
    if (Math.abs(v) < 1e-9) return "0";
    const s = Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1);
    return s.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
  }

  function paintGrid() {
    ensure();
    if (gMinor) gMinor.replaceChildren();
    if (gMajor) gMajor.replaceChildren();
    if (gAxes) gAxes.replaceChildren();
    if (gLabels) gLabels.replaceChildren();
    const vb = E.viewBox;
    if (!vb || !overlay) return;
    // Mirror the motif's viewBox so a coordinate (x, y) lands on the same
    // screen pixel in both SVGs; preserveAspectRatio="none" keeps the overlay
    // from letterboxing if the stage is ever not square.
    overlay.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    const c = readColors();
    const x0 = vb.x, y0 = vb.y, x1 = vb.x + vb.w, y1 = vb.y + vb.h;
    const major = niceStep(vb.w, 6);
    const minor = major / 5;
    const fs = vb.w * 0.022; // label font size in user units, ~22px on a 520 box

    // Minor gridlines (dotted, faint) -- skip the ones that coincide with a
    // major so the major lines read as the primary scaffold.
    for (let x = Math.ceil(x0 / minor) * minor; x <= x1 + 1e-9; x += minor) {
      if (Math.abs(x / major - Math.round(x / major)) < 1e-9) continue;
      gMinor.appendChild(el("line", {
        x1: x, y1: y0, x2: x, y2: y1,
        stroke: c.line, "stroke-width": 1, "stroke-dasharray": "1 3",
      }));
    }
    for (let y = Math.ceil(y0 / minor) * minor; y <= y1 + 1e-9; y += minor) {
      if (Math.abs(y / major - Math.round(y / major)) < 1e-9) continue;
      gMinor.appendChild(el("line", {
        x1: x0, y1: y, x2: x1, y2: y,
        stroke: c.line, "stroke-width": 1, "stroke-dasharray": "1 3",
      }));
    }

    // Major gridlines (solid).
    for (let x = Math.ceil(x0 / major) * major; x <= x1 + 1e-9; x += major) {
      gMajor.appendChild(el("line", { x1: x, y1: y0, x2: x, y2: y1, stroke: c.line2, "stroke-width": 1 }));
    }
    for (let y = Math.ceil(y0 / major) * major; y <= y1 + 1e-9; y += major) {
      gMajor.appendChild(el("line", { x1: x0, y1: y, x2: x1, y2: y, stroke: c.line2, "stroke-width": 1 }));
    }

    // Axes through the origin, clamped to the viewBox, with arrowheads at the
    // box edges so the direction of each axis reads even when the origin is
    // off-screen.
    const hasX = y0 <= 0 && 0 <= y1;
    const hasY = x0 <= 0 && 0 <= x1;
    if (hasX) {
      gAxes.appendChild(el("line", { x1: x0, y1: 0, x2: x1, y2: 0, stroke: c.ink, "stroke-width": 1.5 }));
      gAxes.appendChild(el("path", { d: `M ${x1} 0 l -8 -4 l 0 8 z`, fill: c.ink }));
      gAxes.appendChild(el("path", { d: `M ${x0} 0 l 8 -4 l 0 8 z`, fill: c.ink }));
    }
    if (hasY) {
      gAxes.appendChild(el("line", { x1: 0, y1: y0, x2: 0, y2: y1, stroke: c.ink, "stroke-width": 1.5 }));
      gAxes.appendChild(el("path", { d: `M 0 ${y1} l -4 -8 l 8 0 z`, fill: c.ink }));
      gAxes.appendChild(el("path", { d: `M 0 ${y0} l -4 8 l 8 0 z`, fill: c.ink }));
    }

    // Tick labels: only when majors are wide enough apart that ~4-char labels
    // do not overlap, and never more than ~10 across the box. The origin gets
    // its own "0" so the two axes do not both label it.
    const crowded = major < fs * 3.5;
    const tooMany = vb.w / major > 10;
    if (hasX && !crowded && !tooMany) {
      for (let x = Math.ceil(x0 / major) * major; x <= x1 + 1e-9; x += major) {
        if (Math.abs(x) < 1e-9) continue;
        const t = el("text", {
          x, y: 0, dy: -fs * 0.4, "text-anchor": "middle",
          "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
        });
        t.textContent = fmt(x);
        gLabels.appendChild(t);
      }
    }
    if (hasY && !crowded && !tooMany) {
      for (let y = Math.ceil(y0 / major) * major; y <= y1 + 1e-9; y += major) {
        if (Math.abs(y) < 1e-9) continue;
        const t = el("text", {
          x: 0, y, dx: fs * 0.4, dy: fs * 0.35, "text-anchor": "start",
          "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
        });
        t.textContent = fmt(y);
        gLabels.appendChild(t);
      }
    }
    if (hasX && hasY) {
      const t = el("text", {
        x: 0, y: 0, dx: fs * 0.4, dy: fs * 0.35, "text-anchor": "start",
        "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
      });
      t.textContent = "0";
      gLabels.appendChild(t);
    }
  }
  E.paintGrid = paintGrid;
})(window.EXPLORE);
