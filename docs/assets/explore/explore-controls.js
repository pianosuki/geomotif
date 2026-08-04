"use strict";

// Parameter controls: each row in the controls panel is built from the motif's
// catalog params. The mapping mirrors explore.py's settable/fixed split: an
// annotation the CLI turns into a flag becomes a live control; anything else
// (Projection, Callable, Sequence, tuple, nested motifs, ...) is listed as
// "held" -- the command line reports the same params as not settable, and the
// SPA shows them the same way.
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

(function (E) {
  const {
    controlsEl, commandEl,
    RESERVED, SETTABLE, SPREAD,
  } = E;

  // Whether the whole controls panel is currently disabled (the scipy-only
  // unavailable-motif case). Recorded by paintControls so a reset button's
  // repaint rebuilds the list with the same disabled state.
  let controlsDisabled = false;

  function paintControls(info, st, disabled) {
    controlsDisabled = disabled;
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
        held.map((p) => `<code>${E.esc(p.name)}</code>`).join("") +
        `</span>`;
      note.title =
        "These parameters have no scalar axis the CLI can flag -- a Projection, a " +
        "Callable, a Sequence, a nested motif, ... -- so they stay at the motif's " +
        "declared or example value.";
      controlsEl.appendChild(note);
    }
  }
  E.paintControls = paintControls;

  function buildControl(info, p, st, disabled) {
    const row = document.createElement("div");
    row.className = "control" + (disabled ? " disabled" : "");
    const label = document.createElement("div");
    label.className = "control-label";
    const id = document.createElement("span");
    id.className = "control-id";
    const name = document.createElement("span");
    name.className = "control-name";
    name.textContent = p.name;
    const ann = document.createElement("span");
    ann.className = "control-ann";
    ann.textContent = p.annotation;
    id.appendChild(name);
    id.appendChild(ann);
    label.appendChild(id);
    // A small per-parameter reset, so any control can be snapped back to the
    // value it started at (the motif's example or declared default) in one
    // click instead of fussing the input back by hand.
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "reset-param";
    reset.title = `reset ${p.name} to its default`;
    reset.textContent = "reset";
    reset.addEventListener("click", () => {
      st[p.name] = E.clone(initialValue(info, p));
      paintControls(info, st, disabled);
      onChange();
    });
    label.appendChild(reset);
    row.appendChild(label);

    const body = document.createElement("div");
    body.className = "control-body";
    row.appendChild(body);

    const onChange = () => {
      paintCommand(info, st);
      if (E.animOn && E.anim) {
        // In animation mode a slider move is a *local* adjustment: it updates
        // the preview picture but never edits the timeline -- no keyframe is
        // created or moved here. The param is flagged so the next
        // add-keyframe action (per-track "+" or Set-keyframes-for-all) pulls
        // this adjusted value; a param the user never touched falls back to
        // the value the track already interpolates to at the scrubber's time.
        // Playback is paused so the still preview of the design at the new
        // value is what the user sees.
        const keyframable = canKeyframe(p);
        if (keyframable && E.markParamAdjusted) E.markParamAdjusted(p.name);
        if (E.stopPlayback) E.stopPlayback();
        if (!keyframable && E.scheduleAnimRebuild) {
          // A parameter that has no keyframing path (its value can only live
          // in the motif's base state -- `int | None` like `resolution`, a
          // Point/center, a string) is a real edit, not a preview: rebuild the
          // animation bundle so playback and scrubbing honor the new static
          // value instead of silently ignoring it.
          E.scheduleAnimRebuild(info, st, E.anim);
        }
        E.scheduleRender(info, st);
        return;
      }
      E.scheduleRender(info, st);
    };
    addControlBody(body, p, st, disabled, onChange);
    return row;
  }

  // The value a control resets to: the motif's curated example value when it
  // names this parameter, else the declared default -- exactly the split
  // initState uses to build the initial control state.
  function initialValue(info, p) {
    return (p.name in info.example) ? E.clone(info.example[p.name]) : E.clone(p.default);
  }

  // Whether a parameter can ever own a timeline track (mirrors
  // animatableParams in explore-animation.js): only continuous numeric / bool /
  // Literal annotations. Everything else -- `int | None` like resolution, Point,
  // Bounds, str -- lives purely in the motif's base state, so changing it in
  // animation mode rebuilds the frames instead of previewing a dead-end value.
  function canKeyframe(p) {
    if (p.choices && p.choices.length && p.choices.every((c) => typeof c === "string")) return false;
    const ann = p.annotation;
    if (ann === "int" || ann === "float" || ann === "bool") return true;
    if (p.choices && p.choices.length) return true;
    return ann.startsWith("Literal");
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
  E.formatVal = formatVal;

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

  // --- live command line ------------------------------------------------------
  // Mirrors _flag_for in cli.py: reserved params are skipped, non-flag annotations
  // are held at their default, defaults are omitted, and a bool becomes --x or
  // --no-x (argparse BooleanOptionalAction). Point is x,y and Bounds is
  // min_x,min_y,max_x,max_y -- the metavar the CLI's parsers accept.
  function isSettable(p) {
    if (p.choices || p.annotation.startsWith("Literal")) return true;
    return SETTABLE.has(p.annotation);
  }
  E.isSettable = isSettable;

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
  E.paintCommand = paintCommand;

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
  E.equalEncoded = equalEncoded;
})(window.EXPLORE);
