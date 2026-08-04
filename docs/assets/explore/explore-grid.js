"use strict";

// Coordinate grid overlay: a Desmos-style coordinate plane
// rendered as an SVG layer behind the motif. The overlay is the first child
// of .stage; its viewBox attribute mirrors E.viewBox on every zoom/pan tick,
// so the plane stays aligned with the picture as the user moves around. On
// every applyViewBox() call (and on a theme switch) explore-view.js asks this
// module to repaint, which recomputes a "nice" step from the live world width
// (the viewBox mapped back through the display scale), draws major (solid
// --line-2) and minor (dotted --line) gridlines, the x/y axes through the
// world origin with small arrowheads, and tick labels pinned to the edge the
// axis went out toward, so they persist -- and keep pointing at the right
// numbers -- when the axes are panned/zoomed off-screen (Desmos-style edge
// keeping: numbers ride along beside the axis it belongs to).
//
// The stage renders in *world* coordinates: the motif SVG's viewBox is the
// fixed 520x520 display square, where the world origin (0, 0, y up) sits at
// E.origin (the canvas centre, 260, 260) and every world unit spans E.scale
// display units. This module reads both from the namespace (set from each
// render result) and draws gridlines at whole world multiples, so the numbers
// along the axes are the real coordinates the library plots and the user's
// radius/scale sliders move in.
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
  E.fmt = fmt;

  // The world origin in display units: E.origin, with the canvas-centre
  // default so the grid is well-defined before the first render too.
  function origin() {
    return E.origin && E.origin.x != null ? E.origin : { x: 260, y: 260 };
  }

  function paintGrid() {
    ensure();
    if (gMinor) gMinor.replaceChildren();
    if (gMajor) gMajor.replaceChildren();
    if (gAxes) gAxes.replaceChildren();
    if (gLabels) gLabels.replaceChildren();
    const vb = E.viewBox;
    const sc = E.scale;
    if (!vb || !overlay || !(sc > 0)) return;
    // Mirror the motif's viewBox so a coordinate (x, y) lands on the same
    // screen pixel in both SVGs. preserveAspectRatio matches the motif SVG's
    // (the default xMidYMid meet), so the overlay can never drift from the
    // picture even when the viewBox is non-square.
    overlay.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    const c = readColors();
    const o = origin();
    const ox = o.x, oy = o.y;
    const x0 = vb.x, y0 = vb.y, x1 = vb.x + vb.w, y1 = vb.y + vb.h;

    // Visible world range: invert display -> world (display x = ox + w*sc,
    // display y = oy - w*sc), so a "nice" step is chosen in the motif's own
    // units and the labels show real coordinates.
    const wx0 = (x0 - ox) / sc, wx1 = (x1 - ox) / sc;
    const wy0 = (oy - y1) / sc, wy1 = (oy - y0) / sc;
    const worldStep = niceStep(wx1 - wx0, 6);
    const uStep = worldStep * sc; // display units per major step
    // Axes through the world origin: the y-axis (world x = 0) is visible when
    // the origin's x lands in the box, the x-axis (world y = 0) when its y does.
    const visX = ox >= x0 && ox <= x1;
    const visY = oy >= y0 && oy <= y1;

    // Stroke widths, dashes, arrowheads and label text all stay constant on
    // screen regardless of the zoom: the strokes get vector-effect:
    // non-scaling-stroke (so stroke-width and stroke-dasharray are in CSS
    // pixels), and the arrowhead / label sizes are computed in screen pixels
    // and converted back into user units at paint time. Without this the 1px
    // hairlines balloon to fat fuzzy bars and the labels grow once the viewBox
    // shrinks on a deep zoom.
    const stagePx = (overlay.getBoundingClientRect().width) || 520;
    const scPx = vb.w / stagePx; // user units per screen pixel
    const arrowSize = 7 * scPx, half = arrowSize * 0.5;
    const fs = 11 * scPx; // ~11px on-screen label text
    const hairline = { "vector-effect": "non-scaling-stroke" };

    // Minor gridlines (dotted, faint) -- skip the ones that coincide with a
    // major so the major lines read as the primary scaffold.
    const minor = worldStep / 5;
    for (let wx = Math.ceil(wx0 / minor) * minor; wx <= wx1 + 1e-9; wx += minor) {
      if (Math.abs(wx / worldStep - Math.round(wx / worldStep)) < 1e-9) continue;
      const ux = ox + wx * sc;
      gMinor.appendChild(el("line", {
        x1: ux, y1: y0, x2: ux, y2: y1,
        stroke: c.line, "stroke-width": 1, "stroke-dasharray": "1 3", ...hairline,
      }));
    }
    for (let wy = Math.ceil(wy0 / minor) * minor; wy <= wy1 + 1e-9; wy += minor) {
      if (Math.abs(wy / worldStep - Math.round(wy / worldStep)) < 1e-9) continue;
      const uy = oy - wy * sc;
      gMinor.appendChild(el("line", {
        x1: x0, y1: uy, x2: x1, y2: uy,
        stroke: c.line, "stroke-width": 1, "stroke-dasharray": "1 3", ...hairline,
      }));
    }

    // Major gridlines (solid), at whole world multiples.
    for (let wx = Math.ceil(wx0 / worldStep) * worldStep; wx <= wx1 + 1e-9; wx += worldStep) {
      const ux = ox + wx * sc;
      gMajor.appendChild(el("line", { x1: ux, y1: y0, x2: ux, y2: y1, stroke: c.line2, "stroke-width": 1, ...hairline }));
    }
    for (let wy = Math.ceil(wy0 / worldStep) * worldStep; wy <= wy1 + 1e-9; wy += worldStep) {
      const uy = oy - wy * sc;
      gMajor.appendChild(el("line", { x1: x0, y1: uy, x2: x1, y2: uy, stroke: c.line2, "stroke-width": 1, ...hairline }));
    }

    // Axes through the world origin, clamped to the viewBox, with arrowheads
    // at the box edges so the direction of each axis reads even when the
    // origin is off-screen. Display y grows downward, so "up" (positive world
    // y) is toward the top of the box.
    if (visY) {
      gAxes.appendChild(el("line", { x1: x0, y1: oy, x2: x1, y2: oy, stroke: c.ink, "stroke-width": 1.5, ...hairline }));
      gAxes.appendChild(el("path", { d: `M ${x1} ${oy} l ${-arrowSize} ${-half} l 0 ${2 * half} z`, fill: c.ink }));
      gAxes.appendChild(el("path", { d: `M ${x0} ${oy} l ${arrowSize} ${-half} l 0 ${2 * half} z`, fill: c.ink }));
    }
    if (visX) {
      gAxes.appendChild(el("line", { x1: ox, y1: y0, x2: ox, y2: y1, stroke: c.ink, "stroke-width": 1.5, ...hairline }));
      // The y-axis arrowheads mirror the x-axis ones: the two tips sit on the
      // box edges (y0, y1) and the flat base of each runs *inside* the box
      // toward the centre, so the top one points up and the bottom one down
      // (positive world y increases toward the top of the box) -- and neither
      // is pushed outside the clip path.
      gAxes.appendChild(el("path", { d: `M ${ox} ${y0} l ${-half} ${arrowSize} l ${2 * half} 0 z`, fill: c.ink }));
      gAxes.appendChild(el("path", { d: `M ${ox} ${y1} l ${-half} ${-arrowSize} l ${2 * half} 0 z`, fill: c.ink }));
    }

    // Tick labels, decoupled from axis/origin visibility: the x numbers are
    // pinned along the x-axis when that is on-screen, the y numbers along the
    // y-axis. When an axis scrolls off, the labels follow Desmos and stick to
    // the edge the axis went out *toward*: panning up pushes the x-axis past
    // the top so the x numbers hang on the top edge, and panning right pushes
    // the y-axis past the right so the y numbers hug the right edge -- they
    // ride along with the axis, staying readably close to it, instead of
    // jumping to the far edge. There is no crowding cap: niceStep already
    // keeps ~6 majors on screen, so a deep zoom keeps showing numbers instead
    // of hiding them. Label offsets are negative (toward the inside of the
    // box) to keep the rows from being pushed under the clip path.
    let labelY;
    if (visY && oy + fs <= y1 - fs * 0.3) labelY = oy + fs; // just under the x-axis
    else if (visY) labelY = y1 - fs * 0.3; // axis on-screen but low in the box
    else if (oy < y0) labelY = y0 + fs * 0.3; // axis panned off the top -> top edge
    else labelY = y1 - fs * 0.3; // axis panned off the bottom -> bottom edge
    for (let wx = Math.ceil(wx0 / worldStep) * worldStep; wx <= wx1 + 1e-9; wx += worldStep) {
      // The visible origin gets its own "0"; but when the x-axis is panned
      // off-screen the x-row pins to the edge, so "0" must ride along with the
      // other numbers instead of vanishing. It is nudged to the left of the
      // y-axis when that is still on-screen, so the axis stroke cannot cross
      // the digit as it does when the zero sits dead on x = ox.
      if (Math.abs(wx) < 1e-9 && visY) continue;
      const zeroRide = Math.abs(wx) < 1e-9;
      const t = el("text", {
        x: zeroRide && visX ? ox - fs * 0.42 : ox + wx * sc,
        y: labelY, "text-anchor": zeroRide && visX ? "end" : "middle",
        "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
      });
      t.textContent = fmt(wx);
      gLabels.appendChild(t);
    }
    let labelX, anchor;
    if (visX) { labelX = ox - fs * 0.35; anchor = "end"; } // left of the y-axis
    else if (ox < x0) { labelX = x0 + fs * 0.3; anchor = "start"; } // axis left of view -> left edge
    else { labelX = x1 - fs * 0.35; anchor = "end"; } // axis right of view -> right edge
    for (let wy = Math.ceil(wy0 / worldStep) * worldStep; wy <= wy1 + 1e-9; wy += worldStep) {
      if (Math.abs(wy) < 1e-9 && visX) continue;
      // When the y-axis is panned off-screen and its zero rides the pinned
      // edge row, an on-screen x-axis runs its stroke straight through y = oy
      // -- so that "0" drops a full line below the x-axis instead of being
      // crossed by it (mirroring the on-screen origin label's clear-of-the-
      // axis placement).
      const zeroRide = Math.abs(wy) < 1e-9;
      const t = el("text", {
        x: labelX,
        y: zeroRide && visY ? oy + fs : oy - wy * sc,
        dy: zeroRide && visY ? 0 : fs * 0.35,
        "text-anchor": anchor,
        "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
      });
      t.textContent = fmt(wy);
      gLabels.appendChild(t);
    }
    // The origin's own "0" marks the crossing itself, so it moves with the
    // plane and only appears when the origin is actually on-screen. It tucks
    // into the quadrant its row shares with the x numbers (below): the glyph's
    // baseline sits on the x-row's line (y = oy + fs), so the whole digit is
    // clear of the x-axis stroke instead of being crossed by it, and it is
    // anchored end at a short offset left of the y-axis so that stroke cannot
    // cover it either.
    if (visX && visY) {
      const t = el("text", {
        x: ox, y: oy + fs, dx: -fs * 0.42, "text-anchor": "end",
        "font-size": fs, fill: c.muted, "font-family": "var(--mono)",
      });
      t.textContent = "0";
      gLabels.appendChild(t);
    }
  }
  E.paintGrid = paintGrid;
})(window.EXPLORE);
