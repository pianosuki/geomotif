"use strict";

// Animation mode: the SPA header's Design / Animate mode tabs flip the
// bottom of the stage-area from a still picture into a timeline editor. The
// `keyframes` primitive is the wire format: `anim.tracks` is exactly the
// `tracks` mapping the Python function takes, and `build_keyframes` runs it
// under Pyodide, stashing the per-frame Designs for chunked SVG fetch. Playback
// is a rAF loop reading the cached SVGs; pre-render happens in chunked rAF
// batches (4 frames per tick) so the timeline stays draggable while a cold
// animation fills in. The LRU is keyed on geometry (motif + params + tracks +
// frames + easing + overlays) and never on fps or hold, so a playback-only
// tweak re-uses the cached bundle.
//
// The share-URL `a=` fragment comes with the share step; here the still fragment continues to
// carry the motif + slider state and the timeline lives in-memory only.

(function (E) {
  const {
    timelineEl, stageEl, tracksEl, stageScrubEl, stageScrubWrapEl,
    scrubTimeEl, kfSetAllEl, kfSetAllTEl, transportEl,
    playPauseEl, loopEl, animFramesEl, animFpsEl, animHoldEl, animEaseEl,
    ovDrawEl, ovSpinEl, ovDrawOpts, ovSpinOpts, ovTrailEl, ovTurnsEl,
    expGifEl, animProgressEl, animProgressFill, placeholderEl, phMain,
    EASINGS, ANIM_FRAMES_MIN, ANIM_FRAMES_MAX, ANIM_FPS_MIN, ANIM_FPS_MAX,
    ANIM_HOLD_MIN, PRE_FRAMES_PER_TICK, ANIM_CACHE_SIZE, SPREAD, IS_TOUCH, RESERVED,
  } = E;

  // In-browser LRU for animation frame bundles, separate from the still cache so
  // the two eviction policies do not fight.
  E.animCache = new Map();

  // Playback state. `idx` is the live frame index; `holdLeft` counts down the
  // hold tail; `looping` mirrors the loop toggle; `on` is whether the rAF loop
  // is running.
  E.playState = { raf: null, last: 0, idx: 0, holdLeft: 0, looping: true, on: false };
  E.animOn = false;
  E.anim = null;
  E.bundle = null;
  E.preRaf = null;
  E.scrubbing = false;
  // Playback intent that outlives a single rebuild. startAnim stops playback on
  // every edit, so a burst of edits (say typing a keyframe value) would see
  // `playState.on` false from the second edit onward and lose the "was playing"
  // memory -- leaving the animation frozen with the last rebuild never
  // restarted. This flag is set whenever a run is interrupted by a rebuild and
  // consumed by the rebuild that actually finishes; pausing clears it.
  E.playWanted = false;
  // The keyframe selected by a click/drag: { track: paramName, idx: index },
  // or null when nothing is selected. Selection drives the .sel dot ring, the
  // per-track value input / delete affordance, and Delete/Backspace removal.
  E.selectedKf = null;

  // Keyframe drag axis-locking: on by default, a drag moves the *dominant*
  // axis only (vertical = value, horizontal = time); the small "lock" toggle in
  // the timeline turns it off for free two-axis dragging. Persisted in
  // localStorage like the view toggles so the choice sticks between sessions.
  const AXISLOCK_KEY = "geomotif.axislock";
  try { E.axisLock = localStorage.getItem(AXISLOCK_KEY) !== "off"; }
  catch (err) { E.axisLock = true; }
  function applyAxisLockButton() {
    const btn = E.$("kf-lock");
    if (!btn) return;
    btn.setAttribute("aria-pressed", String(E.axisLock));
    btn.title = E.axisLock
      ? "keyframe drags lock to one axis (value vs time) — click for free two-axis drags"
      : "keyframe drags move value and time together — click to lock to one axis";
  }
  E.toggleAxisLock = (on) => {
    E.axisLock = !!on;
    try { localStorage.setItem(AXISLOCK_KEY, on ? "on" : "off"); } catch (err) { /* private */ }
    applyAxisLockButton();
  };
  {
    const btn = E.$("kf-lock");
    if (btn) btn.addEventListener("click", () => E.toggleAxisLock(!E.axisLock));
    applyAxisLockButton();
  }

  // Keyframe-lane visual preferences -- whether to draw the easing curve
  // between keyframes, fill under it, and (issue added below) the timeline
  // ruler. Each defaults on and persists in localStorage. They are expressed
  // as classes on the timeline element (.kf-no-curve / .kf-no-fill / later
  // .kf-no-ticks) so toggling gating needs no repaint of the lane dots -- the
  // markers are always built and merely hidden in CSS. The settings popover
  // (the keyframe "gear") writes these; applyKfPrefs is called at boot and on
  // change.
  function readKfBool(key, dflt) {
    try {
      const v = localStorage.getItem(key);
      return v == null ? dflt : (v !== "0" && v !== "false");
    } catch (err) { return dflt; }
  }
  E.kfPrefs = {
    curve: readKfBool("geomotif.kf.curve", true),
    fill: readKfBool("geomotif.kf.fill", true),
  };
  function applyKfPrefs() {
    if (!timelineEl) return;
    timelineEl.classList.toggle("kf-no-curve", !E.kfPrefs.curve);
    timelineEl.classList.toggle("kf-no-fill", !E.kfPrefs.fill);
  }
  E.applyKfPrefs = applyKfPrefs;
  E.setKfPref = (key, val) => {
    E.kfPrefs[key] = val;
    try { localStorage.setItem("geomotif.kf." + key, val ? "1" : "0"); } catch (err) { /* private */ }
    applyKfPrefs();
  };
  applyKfPrefs();

  // Live references to the lane / value input / delete button / edit row / row
  // for each track, repopulated on every paintTimeline, so dot selection and
  // drag handlers can update the editor UI without re-querying the DOM.
  const trackRefs = new Map();

  // The animatable parameters of a motif: anything a slider/dropdown/toggle can
  // move, i.e. the settable numeric/bool/Literal params the catalog reports.
  // String-valued choices (a categorical "which shape" picker like Heart's
  // `form`) are excluded: stepping between wholly different forms mid-run is
  // jarring and there is no honest "between", so only things that move
  // continuously -- ints, floats, bools and numeric Literals -- get a track.
  function animatableParams(info) {
    const out = [];
    for (const p of info.params) {
      if (RESERVED.has(p.name)) continue;
      if (!E.isSettable(p)) continue;
      const ann = p.annotation;
      if (p.choices && p.choices.length && p.choices.every((c) => typeof c === "string")) continue;
      if (ann === "int" || ann === "float" || ann === "bool" ||
          (p.choices && p.choices.length) || ann.startsWith("Literal")) {
        out.push(p);
      }
    }
    return out;
  }
  E.animatableParams = animatableParams;

  // The default timeline, per "Default state when entering animation mode": a
  // single track on the motif's primary numeric parameter (the first int/float
  // in ParamInfo order) sweeping from the slider's *current* value to an end
  // value, with cubic easing at 48 frames / 20 fps / hold 12. The first
  // keyframe holds the value the user is already looking at, so entering
  // Animate does not shrink the picture under them; the sweep goes to the
  // farthest end of the declared Range (or a 2x spread of the default when
  // there is none) so the user sees motion immediately and edits from there.
  function defaultAnim(info, st) {
    const nums = info.params.filter((p) =>
      !RESERVED.has(p.name) && (p.annotation === "int" || p.annotation === "float"));
    const tracks = {};
    if (nums.length) {
      const p = nums[0];
      const cur = st[p.name];
      let v0, v1;
      if (p.min != null && p.max != null) {
        const lo = Number(p.min), hi = Number(p.max);
        const c = Number(cur);
        v0 = Math.min(hi, Math.max(lo, Number.isFinite(c) ? c : ((lo + hi) / 2)));
        v1 = (Math.abs(hi - v0) >= Math.abs(v0 - lo)) ? hi : lo;
        if (v1 === v0) v1 = v0 < (lo + hi) / 2 ? hi : lo;
      } else if (p.annotation === "int") {
        const base = Number(cur) || 5;
        v0 = base;
        v1 = Math.max(v0 + 1, Math.ceil(base * SPREAD));
      } else {
        const f = Number(cur) || 0;
        v0 = f;
        v1 = f === 0 ? 1 : (f > 0 ? f * SPREAD : f / SPREAD);
        if (v1 === v0) v1 = v0 + 1;
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
  E.defaultAnim = defaultAnim;

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
  E.animRecipe = animRecipe;

  function animBundleKey(info, st, an) {
    return [
      info.name,
      E.canonical(st),
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
          norm.push([Math.min(1, Math.max(0, t)), E.clone(kf[1])]);
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
  E.recipeToAnim = recipeToAnim;

  function clampInt(v, lo, hi, fallback) {
    const n = Math.round(Number(v));
    if (!Number.isFinite(n)) return fallback;
    return Math.min(hi, Math.max(lo, n));
  }

  function recipeOverlay(o) {
    if (!o || typeof o !== "object") return null;
    if (o.type === "draw_on") {
      const trail = o.trail == null ? null : Number(o.trail);
      // A trail needs a positive length; 0/negative is not a meaningful value
      // and would reveal blank frames, so treat it as "none" (see parseTrail).
      return { type: "draw_on", trail: (Number.isFinite(trail) && trail > 0) ? trail : null };
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
    if (!E.current) return;
    const info = E.byName[E.current];
    if (!info || !info.available) return;
    E.animOn = true;
    E.anim = opts.recipe ? recipeToAnim(opts.recipe) : defaultAnim(info, E.state);
    // A fresh timeline starts with no slider adjustments: any parameter moved
    // during this editor session is what an add-keyframe action will honor.
    E.adjusted = new Set();
    timelineEl.classList.add("on");
    stageEl.classList.add("anim");
    // The stage scrubber is hidden in Design mode; show it now so the master
    // clock (play / loop / scrub) sits directly under the canvas.
    if (stageScrubWrapEl) stageScrubWrapEl.hidden = false;
    // Read-only on touch: scrub + play work, keyframe editing is hidden.
    timelineEl.classList.toggle("touch", IS_TOUCH);
    // The slider panel stays live: moving a slider adjusts a *local preview*
    // of the design (see the control onChange in explore-controls.js) but
    // deliberately does not touch any keyframe -- the timeline only changes
    // when the user clicks an add-keyframe action, which then pulls the
    // adjusted value or the track's value at that time.
    paintTimeline(info, E.state);
    paintTransport(E.anim);
    syncScrubber();
    expGifEl.disabled = false;
    // Write the animation fragment unless we just consumed one from the URL
    // (restoring a share URL keeps the landing hash rather than rewriting it
    // over itself). replaceState keeps the back button on one entry per motif.
    if (!opts.fromFragment) E.writeFragment(E.current, E.state, E.anim, false);
    startAnim(info, E.state, E.anim);
    // Reflect the new mode on the header's tab strip. explore-mode.js owns the
    // tab UI; calling it through E keeps this module unaware of whether the
    // tabs exist (the call is a no-op if they don't).
    if (E.syncModeTabs) E.syncModeTabs();
  }
  E.enterAnim = enterAnim;

  function exitAnim(opts) {
    opts = opts || {};
    E.animOn = false;
    timelineEl.classList.remove("on", "touch");
    stageEl.classList.remove("anim");
    // Hide the stage scrubber on the way back to Design mode.
    if (stageScrubWrapEl) stageScrubWrapEl.hidden = true;
    expGifEl.disabled = true;
    E.playWanted = false;
    stopPlayback();
    if (E.preRaf) { cancelAnimationFrame(E.preRaf); E.preRaf = null; }
    E.bundle = null;
    E.anim = null;
    hideAnimProgress();
    // Return to a still render of the current slider state, unless the caller
    // is about to render something else (e.g. selectMotif switching to a new
    // motif and re-entering Animate on it -- keeps the active mode across a
    // motif switch, so the outgoing motif's still render would be wasted work
    // and could briefly flash before the new motif renders).
    if (!opts.skipStillRender) {
      const info = E.byName[E.current];
      if (info && info.available) E.render(info, E.state);
    }
    // Mirror the exit onto the header's tab strip (see enterAnim).
    if (E.syncModeTabs) E.syncModeTabs();
  }
  E.exitAnim = exitAnim;

  // --- timeline paint ---------------------------------------------------------
  function paintTimeline(info, st) {
    // Drop stale refs to rows/lanes from the previous paint; selection UI
    // state (E.selectedKf) is also cleared so a rebuild starts clean.
    trackRefs.clear();
    E.selectedKf = null;
    tracksEl.innerHTML = "";
    if (IS_TOUCH) {
      const hint = document.createElement("p");
      hint.className = "touch-hint";
      hint.textContent = "timeline editing is best on desktop — scrub and play work here";
      tracksEl.appendChild(hint);
    }
    const params = animatableParams(info);
    if (!params.length) {
      const note = document.createElement("p");
      note.className = "anim-empty";
      note.textContent = "this motif has no animatable parameters";
      tracksEl.appendChild(note);
      return;
    }
    // Empty-state hint card. When the animator opens with no keyframes on
    // any track (e.g. a motif whose default recipe has no sweep -- only bool /
    // Literal params, or a freshly-cleared timeline), a centered hint tells
    // the user the scrub -> slider -> "Set keyframes for all params" loop. It disappears the
    // moment any track has >=1 keyframe, at which point the real track rows
    // paint. The kf-set-all button above #tracks stays visible either way so
    // the user can act on the hint.
    const anyKf = params.some((p) => {
      const tr = E.anim.tracks[p.name];
      return tr && tr.keyframes && tr.keyframes.length;
    });
    if (!anyKf) {
      const card = document.createElement("div");
      card.className = "anim-empty-card";
      card.textContent = "Move the scrubber to a time \u2192 adjust the sliders \u2192 click \u201cSet keyframes for all params\u201d, then press play to preview.";
      tracksEl.appendChild(card);
      return;
    }
    for (const p of params) {
      tracksEl.appendChild(buildTrackRow(info, p, st, E.anim));
    }
  }
  E.paintTimeline = paintTimeline;

  // A track is discrete (steps at the next keyframe rather than easing) when its
  // value is a bool, a Literal choice, or a plain string. The step marker makes
  // that visible so a user is not surprised when a "sweep" snaps instead of
  // gliding.
  function isDiscrete(p) {
    const ann = p.annotation;
    return ann === "bool" || (p.choices && p.choices.length) || ann.startsWith("Literal")
      || ann === "str" || ann === "str | None";
  }

  // Numeric tracks get a value axis: their keyframe dots sit at a height
  // matching their value, and vertical drag edits it. The range is the declared
  // Range when there is one, else the same geometric heuristic the slider uses,
  // so the axis is stable across repaints.
  function isNumericKey(p) {
    return p.annotation === "int" || p.annotation === "float";
  }
  E.isNumericKey = isNumericKey;

  function valueRange(p) {
    if (p.min != null && p.max != null) return [Number(p.min), Number(p.max)];
    const ann = p.annotation;
    const cur = (E.state && E.state[p.name] != null)
      ? E.state[p.name]
      : (p.default != null ? p.default : null);
    if (ann === "int") {
      const base = Number(cur) || 5;
      const lo = Math.max(1, Math.floor(base / SPREAD));
      return [lo, Math.max(lo + 1, Math.ceil(base * SPREAD))];
    }
    if (ann === "float") {
      const f = Number(cur) || 1;
      if (f === 0) return [-1, 1];
      return [f / SPREAD, f * SPREAD];
    }
    return [0, 1];
  }
  E.valueRange = valueRange;

  function parseNum(s, fallback) {
    const n = Number(s);
    return Number.isFinite(n) ? n : fallback;
  }

  // --- keyframe selection + editor UI --------------------------------------
  // A selected dot shows a ring (.sel), and its track's edit row enables the
  // precise value input and the delete button. Selection is per-(track, index),
  // stored on E so Delete/Backspace and the row's controls all agree.
  function syncSelClass(p, an) {
    const ref = trackRefs.get(p.name);
    if (!ref) return;
    for (const dot of ref.lane.querySelectorAll(".kf")) {
      dot.classList.toggle("sel", !!(
        E.selectedKf && E.selectedKf.track === p.name &&
        Number(dot.dataset.idx) === E.selectedKf.idx
      ));
    }
  }

  function syncEditRow(p, an) {
    const ref = trackRefs.get(p.name);
    if (!ref) return;
    const sel = !!(E.selectedKf && E.selectedKf.track === p.name);
    ref.row.classList.toggle("edit", sel);
    const tr = an.tracks[p.name];
    const kf = sel && tr ? tr.keyframes[E.selectedKf.idx] : null;
    if (ref.valueInp) {
      ref.valueInp.disabled = !sel;
      ref.valueInp.value = sel && kf ? String(kf[1]) : "";
    }
    if (ref.timeInp) {
      ref.timeInp.disabled = !sel;
      ref.timeInp.value = sel && kf ? String(kf[0]) : "";
    }
    ref.delBtn.disabled = !sel || !tr || tr.keyframes.length <= 1;
  }

  // Mirror a drag-updated value into the track's number input (only used while
  // dragging a numeric dot).
  function syncValueInput(p, v) {
    const ref = trackRefs.get(p.name);
    if (ref && ref.valueInp && E.selectedKf && E.selectedKf.track === p.name) {
      ref.valueInp.value = String(v);
    }
  }

  // Mirror a drag-updated time into the track's time input (only used while
  // dragging a dot horizontally).
  function syncTimeInput(p, t) {
    const ref = trackRefs.get(p.name);
    if (ref && ref.timeInp && E.selectedKf && E.selectedKf.track === p.name) {
      ref.timeInp.value = String(t);
    }
  }

  function selectKey(p, idx, an) {
    E.selectedKf = { track: p.name, idx };
    syncSelClass(p, an);
    syncEditRow(p, an);
  }
  E.selectKey = selectKey;

  // Remove the selected keyframe (via the track's delete button or the
  // Delete/Backspace key on a focused dot). Keep at least one keyframe per
  // track; rebuilding the timeline clears the selection and redraws dots.
  function removeSelected(p, an) {
    if (!E.selectedKf || E.selectedKf.track !== p.name) return;
    const kfs = an.tracks[p.name] && an.tracks[p.name].keyframes;
    if (!kfs || kfs.length <= 1) return;
    kfs.splice(E.selectedKf.idx, 1);
    E.selectedKf = null;
    const info = E.byName[E.current];
    if (info) {
      paintTimeline(info, E.state);
      E.restartPlayback(info, E.state, an);
    }
  }
  E.removeSelected = removeSelected;

  function buildTrackRow(info, p, st, an) {
    const row = document.createElement("div");
    row.className = "track";
    const numeric = isNumericKey(p);
    if (numeric) row.classList.add("numeric");
    const head = document.createElement("div");
    head.className = "track-head";
    const name = document.createElement("span");
    name.className = "track-name";
    name.textContent = p.name;
    head.appendChild(name);
    // Step marker on discrete tracks so the hold-then-snap behavior reads.
    if (isDiscrete(p)) {
      const step = document.createElement("span");
      step.className = "step-mark";
      step.textContent = "step";
      step.title = "this parameter steps at each keyframe (it does not ease)";
      head.appendChild(step);
    }
    // Per-track easing dropdown (defaults to the global easing; "auto" means
    // inherit). The "auto" option keeps the recipe compact. Hidden on touch
    // (read-only timeline).
    const ease = document.createElement("select");
    ease.className = "track-easing";
    if (IS_TOUCH) ease.disabled = true;
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
      E.restartPlayback(info, st, an);
    });
    head.appendChild(ease);
    // A per-track "add keyframe at the scrubber" button. Sits beside the
    // easing dropdown so the row reads `[name] [step] [+] [easing]` then the
    // lane below. Drops a single keyframe for this param at the scrubber's
    // current time holding the slider's current value -- the same action as
    // the top "Set keyframes for all params" button, but scoped to one track. Disabled on
    // touch (read-only timeline).
    const add = document.createElement("button");
    add.className = "kf-add-one";
    add.type = "button";
    add.textContent = "+";
    add.title = "add keyframe for " + p.name + " at the scrubber";
    if (IS_TOUCH) add.disabled = true;
    add.addEventListener("click", () => {
      const t = currentScrubT();
      dropKeyframe(p, st, an, t);
      paintLaneDots(lane, p, an);
      E.restartPlayback(info, st, an);
    });
    head.appendChild(add);
    row.appendChild(head);

    const lane = document.createElement("div");
    lane.className = "lane";
    lane.dataset.param = p.name;
    if (numeric) lane.classList.add("numeric");
    row.appendChild(lane);

    // The edit row appears under the lane when a keyframe on this track is
    // selected: a precise time input (clamped to 0..1) on every track, a
    // precise value input on numeric tracks, and always a visible delete (x)
    // button (Delete/Backspace on a focused dot still works too). Touch keeps
    // the timeline read-only, so the whole row is hidden there.
    const editRow = document.createElement("div");
    editRow.className = "kf-edit-row";
    const timeLab = document.createElement("span");
    timeLab.className = "kf-edit-label";
    timeLab.textContent = "t";
    const timeInp = document.createElement("input");
    timeInp.type = "number";
    timeInp.className = "kf-time-input";
    timeInp.step = "0.001";
    timeInp.min = "0";
    timeInp.max = "1";
    timeInp.disabled = true;
    timeInp.title = "type the selected keyframe's time (0..1)";
    timeInp.addEventListener("input", () => {
      if (!E.selectedKf || E.selectedKf.track !== p.name) return;
      const kfs = an.tracks[p.name] && an.tracks[p.name].keyframes;
      if (!kfs || !kfs[E.selectedKf.idx]) return;
      const kf = kfs[E.selectedKf.idx];
      // Clamp to the timeline so negative or super-unity times are impossible.
      kf[0] = Math.min(1, Math.max(0, parseNum(timeInp.value, kf[0])));
      // A typed time can reorder the list; fix the sort and re-point the
      // selection so the ring lands back on the same keyframe.
      kfs.sort((a, b) => a[0] - b[0]);
      E.selectedKf.idx = Math.max(0, kfs.indexOf(kf));
      paintLaneDots(lane, p, an);
      E.restartPlayback(info, st, an);
    });
    editRow.appendChild(timeLab);
    editRow.appendChild(timeInp);
    const valueInp = numeric ? document.createElement("input") : null;
    if (valueInp) {
      const lab = document.createElement("span");
      lab.className = "kf-edit-label";
      lab.textContent = "value";
      valueInp.type = "number";
      valueInp.className = "kf-value-input";
      valueInp.step = p.annotation === "int" ? "1" : "any";
      valueInp.disabled = true;
      valueInp.title = "type the selected keyframe's value";
      valueInp.addEventListener("input", () => {
        if (!E.selectedKf || E.selectedKf.track !== p.name) return;
        const kfs = an.tracks[p.name] && an.tracks[p.name].keyframes;
        if (!kfs || !kfs[E.selectedKf.idx]) return;
        const v = parseNum(valueInp.value, kfs[E.selectedKf.idx][1]);
        kfs[E.selectedKf.idx][1] = p.annotation === "int" ? Math.round(v) : v;
        paintLaneDots(lane, p, an);
        E.restartPlayback(info, st, an);
      });
      editRow.appendChild(lab);
      editRow.appendChild(valueInp);
    }
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "kf-del";
    delBtn.textContent = "\u2715"; // x
    delBtn.title = "remove selected keyframe";
    delBtn.disabled = true;
    delBtn.addEventListener("click", () => {
      if (!E.selectedKf || E.selectedKf.track !== p.name) return;
      deleteKeyframe(p, an, E.selectedKf.idx);
      E.selectedKf = null;
      paintLaneDots(lane, p, an);
      syncEditRow(p, an);
      E.restartPlayback(info, st, an);
    });
    editRow.appendChild(delBtn);
    row.appendChild(editRow);

    trackRefs.set(p.name, { lane, valueInp, timeInp, delBtn, editRow, row });
    paintLaneDots(lane, p, an);
    return row;
  }

  const LANE_SVG_NS = "http://www.w3.org/2000/svg";

  // Draw the easing curve between keyframes in a numeric lane: an SVG overlay
  // whose polyline sits at the value each time eases to, so a user can see at a
  // glance how the animation will move between two keyframes (steep = fast,
  // flat = slow). The curve is area-filled to the bottom of the lane by
  // default. A single keyframe -- wherever it sits -- simply holds its value,
  // so the "curve" is a level line across the whole lane, showing the value
  // stays put from the start (or to the end). Numeric tracks only: a bool /
  // Literal track's value has no linear axis, so it gets no curve (the step
  // marker already tells that story). The lane is position:relative, so the
  // overlay svg stretches to it via preserveAspectRatio="none"; vector-effect
  // keeps the stroke a constant screen width. The .kf-no-curve / .kf-no-fill
  // classes on the timeline (keyframe settings) hide it in CSS, so toggling
  // needs no repaint of the dots.
  function paintLaneCurve(lane, p, an, tr, numeric, lo, hi) {
    if (IS_TOUCH || !numeric || !tr || !tr.keyframes || !tr.keyframes.length || hi <= lo) return;
    const kfs = tr.keyframes;
    const easeName = tr.easing || an.easing;
    const N = 96;
    const pts = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N;
      const v = Number(E.trackValueAt(kfs, t, easeName));
      const f = Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
      pts.push([(t * 100).toFixed(2), ((1 - f) * 100).toFixed(2)]);
    }
    const curve = "M " + pts.map((q) => q[0] + " " + q[1]).join(" L ");
    const fill = "M 0 100 L " + pts.map((q) => q[0] + " " + q[1]).join(" L ") + " L 100 100 Z";
    const svg = document.createElementNS(LANE_SVG_NS, "svg");
    svg.setAttribute("class", "kf-curve-svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    const fillP = document.createElementNS(LANE_SVG_NS, "path");
    fillP.setAttribute("class", "kf-curve-fill");
    fillP.setAttribute("d", fill);
    const lineP = document.createElementNS(LANE_SVG_NS, "path");
    lineP.setAttribute("class", "kf-curve-line");
    lineP.setAttribute("d", curve);
    svg.appendChild(fillP);
    svg.appendChild(lineP);
    lane.appendChild(svg);
  }

  function paintLaneDots(lane, p, an) {
    // Keep the lane element; clear and re-add overlays + dots so a redraw after
    // a drop / drag / delete / value edit is one DOM write. The easing curve is
    // painted before the dots so they stay on top of it.
    lane.querySelectorAll(".kf").forEach((d) => d.remove());
    lane.querySelectorAll(".kf-curve-svg").forEach((s) => s.remove());
    const tr = an.tracks[p.name];
    const numeric = isNumericKey(p);
    const loHi = numeric ? valueRange(p) : [0, 1];
    const lo = loHi[0], hi = loHi[1];
    paintLaneCurve(lane, p, an, tr, numeric, lo, hi);
    if (!tr) return;
    for (let i = 0; i < tr.keyframes.length; i++) {
      const [t, v] = tr.keyframes[i];
      const dot = document.createElement("span");
      dot.className = "kf";
      dot.style.left = (t * 100) + "%";
      // Numeric dots sit at a height encoding their value (max at the top of
      // the lane), so vertical position is meaningful; discrete dots centre
      // vertically. The transform (not margins) centres the dot on its point.
      if (numeric && hi > lo) {
        const frac = Math.min(1, Math.max(0, (Number(v) - lo) / (hi - lo)));
        dot.style.top = ((1 - frac) * 100) + "%";
      } else {
        dot.style.top = "50%";
      }
      dot.title = `${p.name} @ t=${t.toFixed(2)} = ${E.formatVal(v)}`;
      dot.dataset.idx = String(i);
      if (E.selectedKf && E.selectedKf.track === p.name && E.selectedKf.idx === i) {
        dot.classList.add("sel");
      }
      // On touch the dots are display-only: no focus, no keydown delete, no
      // drag (pointer-events: none in CSS keeps them out of hit testing).
      if (!IS_TOUCH) {
        dot.tabIndex = 0;
        dot.addEventListener("keydown", (e) => {
          if (e.key === "Backspace" || e.key === "Delete") {
            e.preventDefault();
            selectKey(p, i, an);
            removeSelected(p, an);
          }
        });
        dot.addEventListener("pointerdown", (e) => startDotDrag(e, dot, p, an, lane));
      }
      lane.appendChild(dot);
    }
    syncEditRow(p, an);
  }
  E.paintLaneDots = paintLaneDots;

  // Drag a keyframe dot. Clicking selects it (ring + editor row). Dragging
  // moves the *dominant* axis only: left/right changes the time, and on
  // numeric tracks up/down changes the value, so the dot moves one way in the
  // lane. The drag is axis-locked after a few pixels of travel -- a mostly
  // vertical gesture changes the value without nudging the time (and vice
  // versa). The dragged attribute mutates the keyframe pair in place; on
  // release the list is time-sorted, re-indexed and repainted.
  function startDotDrag(e, dot, p, an, lane) {
    e.preventDefault();
    dot.focus();
    const kfs = an.tracks[p.name].keyframes;
    const kf = kfs[Number(dot.dataset.idx)];
    if (!kf) return;
    selectKey(p, Number(dot.dataset.idx), an);
    const numeric = isNumericKey(p);
    const loHi = numeric ? valueRange(p) : [0, 1];
    const rect = lane.getBoundingClientRect();
    const startX = e.clientX, startY = e.clientY;
    let axis = null; // "x" (time) or "y" (value); locked at the drag threshold
    const AXIS_THRESH = 6; // px of travel before the gesture commits to an axis
    const move = (ev) => {
      // Free two-axis drag (axis lock off): the dot moves both ways in the
      // lane -- horizontal changes the time, vertical the value.
      if (!E.axisLock) {
        const t = Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width));
        kf[0] = t;
        dot.style.left = (t * 100) + "%";
        syncTimeInput(p, t);
        if (numeric && loHi[1] > loHi[0]) {
          const frac = Math.min(1, Math.max(0, 1 - (ev.clientY - rect.top) / rect.height));
          const v = loHi[0] + (loHi[1] - loHi[0]) * frac;
          kf[1] = Number(v.toFixed(4));
          dot.style.top = ((1 - frac) * 100) + "%";
          syncValueInput(p, kf[1]);
        }
        dot.title = `${p.name} @ t=${t.toFixed(2)} = ${E.formatVal(kf[1])}`;
        return;
      }
      // Axis-locked drag: commit to the dominant axis after a few pixels.
      const dx = ev.clientX - startX, dy = ev.clientY - startY;
      if (!axis) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) <= AXIS_THRESH) return;
        axis = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
      }
      if (axis === "x") {
        const t = Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width));
        kf[0] = t;
        dot.style.left = (t * 100) + "%";
        syncTimeInput(p, t);
        dot.title = `${p.name} @ t=${t.toFixed(2)} = ${E.formatVal(kf[1])}`;
        return;
      }
      if (numeric && loHi[1] > loHi[0]) {
        const frac = Math.min(1, Math.max(0, 1 - (ev.clientY - rect.top) / rect.height));
        const v = loHi[0] + (loHi[1] - loHi[0]) * frac;
        kf[1] = Number(v.toFixed(4));
        dot.style.top = ((1 - frac) * 100) + "%";
        syncValueInput(p, kf[1]);
        dot.title = `${p.name} @ t=${kf[0].toFixed(2)} = ${E.formatVal(kf[1])}`;
      }
    };
    const up = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
      // A horizontal drag may have reordered the list; fix the sort and the
      // selection's index so the ring lands on the same keyframe.
      kfs.sort((a, b) => a[0] - b[0]);
      E.selectedKf.idx = Math.max(0, kfs.indexOf(kf));
      paintLaneDots(lane, p, an);
      E.restartPlayback(E.byName[E.current], E.state, an);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
  }

  // An "add keyframe" action (per-track "+", or the Set-keyframes-for-all
  // button) commits a value for the new keyframe. The named easing curves
  // below mirror geomotif.core.spacing and the bridging _value_at, so a drop
  // made without touching the slider drops a value that lies exactly on the
  // current curve instead of bending it.

  // The named easing curves, each mapping [0,1] -> [0,1] monotonically, with
  // the same "name:mode" suffix support Python's _easing_curve has.
  function easeProgress(name, t) {
    const head = String(name || "linear"), sep = head.indexOf(":");
    const base = sep >= 0 ? head.slice(0, sep) : head;
    const mode = sep >= 0 ? head.slice(sep + 1) : "in";
    const easeIn = (u) => {
      if (base === "quadratic") return u * u;
      if (base === "cubic") return u * u * u;
      if (base === "sinusoidal") return 1 - Math.cos(u * Math.PI / 2);
      if (base === "exponential") {
        const k = 10, floor = Math.pow(2, -k);
        return (Math.pow(2, k * (u - 1)) - floor) / (1 - floor);
      }
      if (base === "circular") return 1 - Math.sqrt(1 - u * u);
      return u;
    };
    if (mode === "out") return 1 - easeIn(1 - t);
    if (mode === "in_out") return t < 0.5 ? easeIn(2 * t) / 2 : 1 - easeIn(2 * (1 - t)) / 2;
    return easeIn(t);
  }

  // Mirror of the Python _is_discrete: plain numbers (bool excluded) always
  // interpolate; bools and strings step; anything else of a different kind
  // steps too.
  function isDiscreteVal(a, b) {
    if (typeof a === "boolean" || typeof b === "boolean") return true;
    if (typeof a === "string" || typeof b === "string") return true;
    if (typeof a === "number" && typeof b === "number") return false;
    return typeof a !== typeof b;
  }

  // Mirror of the Python _lerp: numeric blend (integers round), arrays
  // component-wise; anything else holds its start value.
  function lerpValue(a, b, u) {
    if (typeof a === "number" && typeof b === "number") {
      const r = a + (b - a) * u;
      return Number.isInteger(a) && Number.isInteger(b) ? Math.round(r) : r;
    }
    if (Array.isArray(a) && Array.isArray(b)) return a.map((x, i) => lerpValue(x, b[i], u));
    return a;
  }

  // The value a track holds at normalized time `t`, mirroring the Python
  // keyframes primitive's _value_at so a no-adjustment drop lies exactly on
  // the current curve. Discrete tracks step, with the final segment's onset
  // pulled back to its midpoint; numeric tracks ease with the track's (or the
  // global) named curve.
  function trackValueAt(kfs, t, easeName) {
    const last = kfs.length - 1;
    if (t <= kfs[0][0]) return E.clone(kfs[0][1]);
    if (t >= kfs[last][0]) return E.clone(kfs[last][1]);
    if (isDiscreteVal(kfs[0][1], kfs[last][1])) {
      const lastOnset = last >= 1 ? (kfs[last - 1][0] + kfs[last][0]) / 2 : kfs[last][0];
      if (t >= lastOnset) return E.clone(kfs[last][1]);
      let held = kfs[0][1];
      for (const [tk, vk] of kfs) {
        if (tk <= t) held = vk;
        else break;
      }
      return E.clone(held);
    }
    for (let i = 1; i <= last; i++) {
      const t0 = kfs[i - 1][0], t1 = kfs[i][0];
      if (t0 <= t && t <= t1) {
        const local = t1 > t0 ? (t - t0) / (t1 - t0) : 0;
        return E.clone(lerpValue(kfs[i - 1][1], kfs[i][1], easeProgress(easeName, local)));
      }
    }
    return E.clone(kfs[last][1]);
  }
  // Exposed for the smoke harness so an add-keyframe value can be verified
  // against the track's own interpolation.
  E.trackValueAt = trackValueAt;

  // The value a drop should commit at time `t`: the slider's current value
  // when the user has adjusted this parameter during the current timeline
  // edit, otherwise the value the track already interpolates to at `t` (so an
  // unadjusted drop never bends the curve). A param with no track yet has no
  // interpolation -- the slider's value is the only honest choice and, the
  // slider being the source of truth there, it is also the "adjusted" one.
  function pullKeyframeValue(p, st, an, t) {
    const tr = an.tracks[p.name];
    const interp = (tr && tr.keyframes && tr.keyframes.length)
      ? trackValueAt(tr.keyframes, t, (tr.easing || an.easing))
      : null;
    if (interp == null) return E.clone(st[p.name]);
    if (E.adjusted && E.adjusted.has(p.name)) return E.clone(st[p.name]);
    return interp;
  }

  // Parameter adjustments made in animation mode -- a slider the user moved
  // since the current timeline was built -- are remembered so an add-keyframe
  // action commits the adjusted value rather than the track's own value at
  // that time. Every drop consumes the flag, so a second drop without another
  // slider move falls back to the interpolation. Reset on a fresh timeline.
  E.adjusted = new Set();
  E.markParamAdjusted = (name) => { if (E.adjusted) E.adjusted.add(name); };

  // Drop a keyframe for `p` at time `t`. If a keyframe already sits within a
  // small threshold of `t` it is updated in place, so a repeated drop at the
  // same time moves the value rather than stacking dots. The committed value
  // is the slider's adjusted value (when the user moved this parameter) or
  // the track's own value at `t`; see pullKeyframeValue.
  function dropKeyframe(p, st, an, t) {
    if (!an.tracks[p.name]) an.tracks[p.name] = { keyframes: [], easing: null };
    const kfs = an.tracks[p.name].keyframes;
    const THRESH = 0.01;
    const near = kfs.findIndex((kv) => Math.abs(kv[0] - t) < THRESH);
    const val = pullKeyframeValue(p, st, an, t);
    if (near >= 0) kfs[near][1] = val;
    else {
      kfs.push([t, val]);
      kfs.sort((a, b) => a[0] - b[0]);
    }
    if (E.adjusted && E.adjusted.delete) E.adjusted.delete(p.name);
  }
  E.dropKeyframe = dropKeyframe;

  function deleteKeyframe(p, an, idx) {
    const kfs = an.tracks[p.name].keyframes;
    if (kfs.length <= 1) return; // keep at least one
    kfs.splice(idx, 1);
  }
  E.deleteKeyframe = deleteKeyframe;

  // --- transport paint --------------------------------------------------------
  function paintTransport(an) {
    animFramesEl.value = an.frames;
    animFpsEl.value = an.fps;
    animHoldEl.value = an.hold;
    animHoldEl.max = Math.max(0, Math.floor(an.frames / 4));
    animEaseEl.value = an.easing;
    loopEl.setAttribute("aria-pressed", String(E.playState.looping));
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
  E.paintTransport = paintTransport;

  // --- pre-render + playback --------------------------------------------------
  // Build the frame bundle for the current animation. The Python bridge runs
  // `keyframes` once and stashes the per-frame Designs; we then fetch each
  // frame's SVG in chunked rAF batches so the timeline stays responsive. The
  // bundle holds the `frames`-length core (before `hold`); the hold tail is
  // synthesised on playback by repeating the last frame, so changing `hold` is
  // a free re-playback with no re-render.
  function startAnim(info, st, an) {
    // Playback never auto-starts here: entering Animate, or rebuilding the
    // bundle after an adjustment, shows the scrubber's frame and waits for the
    // user to press play. A rebuild made while a run was playing, though, must
    // keep it going once the new bundle is ready -- and the "was playing"
    // intent is remembered on E.playWanted, not from playState.on at this
    // instant, because a burst of edits calls stopPlayback once per edit and
    // only the first one sees `on` true.
    E.playWanted = E.playWanted || E.playState.on;
    stopPlayback();
    if (E.preRaf) { cancelAnimationFrame(E.preRaf); E.preRaf = null; }
    E.playState.idx = 0;
    const key = animBundleKey(info, st, an);
    const cached = E.animCache.get(key);
    if (cached) {
      E.animCache.delete(key);
      E.animCache.set(key, cached);
      const bundle = {
        key, core: cached.frames, bounds: cached.bounds || null,
        count: cached.frames.length + an.hold, ready: cached.frames.length,
        total: cached.frames.length, busy: false, scale: E.scale,
      };
      E.bundle = bundle;
      // A cache hit is instantly ready -- there is no pre-render to show, so
      // the progress bar must not linger (a superseded build that was still
      // filling in owns hideAnimProgress on its own completion, but its tick
      // loop bails the moment E.bundle stops being it). Explicitly take the
      // bar down here, otherwise it sticks at full forever.
      hideAnimProgress();
      drawFrame(0);
      if (E.playWanted) { E.playWanted = false; startPlayback(info, an); }
      return;
    }
    // Each build owns its bundle object; preRenderChunks and the async body
    // bail out when E.bundle no longer points at it, so a rapid edit cannot let
    // an older build's frames bleed into the newest bundle.
    const bundle = { key, core: null, count: 0, ready: 0, total: 0, busy: true, scale: null };
    E.bundle = bundle;
    showAnimProgress(0);
    (async () => {
      await E.ensurePyodide();
      if (E.bundle !== bundle) return; // a newer edit superseded this build
      const out = JSON.parse(E.pyBuildKeyframes(
        info.name, JSON.stringify(st || {}), JSON.stringify(animRecipe(an).tracks),
        an.frames, an.fps, 0, an.easing, JSON.stringify(an.overlays),
        JSON.stringify(info.example || {})
      ));
      if (out.error) {
        if (E.bundle === bundle) {
          E.bundle = null;
          hideAnimProgress();
          showAnimError(out.error);
        }
        return;
      }
      const total = out.count - 0; // bridge built with hold=0; core length == frames
      bundle.core = new Array(total).fill(null);
      bundle.bounds = new Array(total).fill(null);
      bundle.total = total;
      bundle.count = total + an.hold;
      preRenderChunks(bundle, info, an, 0);
    })();
  }
  E.startAnim = startAnim;

  // Fetch PRE_FRAMES_PER_TICK SVGs per rAF tick until `bundle` is full, then
  // draw frame 0. Playback restarts after a rebuild only if play intent is
  // live (E.playWanted -- see startAnim); otherwise the user presses play.
  // The loop self-terminates the moment E.bundle is no longer this bundle, so
  // a newer rebuild's loop is the only one writing frames.
  function preRenderChunks(bundle, info, an, from) {
    let i = from;
    const tick = () => {
      if (E.bundle !== bundle || !bundle.busy) return;
      let made = 0;
      while (i < bundle.total && made < PRE_FRAMES_PER_TICK) {
        const out = JSON.parse(E.pyRenderFrame(i));
        // Every frame carries the same world->display scale (the mapping is
        // per-motif); keep it current so the grid / readout / zoom indicator
        // track scrubbing and playback.
        if (out.scale != null) {
          E.scale = out.scale;
          bundle.scale = out.scale;
        }
        bundle.bounds[i] = (out.bounds && Number.isFinite(out.bounds.w) && out.bounds.w > 0)
          ? out.bounds : null;
        bundle.core[i] = out.error ? null : out.svg;
        i++; made++;
      }
      bundle.ready = i;
      showAnimProgress(bundle.total ? bundle.ready / bundle.total : 1);
      if (i < bundle.total) {
        E.preRaf = requestAnimationFrame(tick);
      } else {
        bundle.busy = false;
        hideAnimProgress();
        // Cache the core bundle for replay.
        if (E.animCache.size >= ANIM_CACHE_SIZE) E.animCache.delete(E.animCache.keys().next().value);
        E.animCache.set(bundle.key, {
          frames: bundle.core.slice(),
          bounds: bundle.bounds ? bundle.bounds.slice() : null,
        });
        // Only the current bundle draws frame 0 and (re)starts playback; a
        // superseded bundle finishing late must not touch the stage.
        if (E.bundle === bundle) {
          drawFrame(0);
          if (E.playWanted) {
            E.playWanted = false;
            startPlayback(info, an);
          }
        }
      }
    };
    E.preRaf = requestAnimationFrame(tick);
  }

  // rAF playback loop. Each tick advances `idx` by the elapsed-time budget at
  // the recipe's fps; the hold tail holds the last core frame for `hold`
  // extra frames. Looping wraps to 0; non-looping stops at the end.
  function startPlayback(info, an) {
    if (!E.bundle || !E.bundle.core) return;
    E.playWanted = false;
    E.playState.on = true;
    E.playState.last = performance.now();
    E.playState.idx = 0;
    E.playState.holdLeft = an.hold;
    playPauseEl.classList.add("playing");
    const step = () => {
      if (!E.playState.on || !E.bundle) return;
      const now = performance.now();
      const frameMs = 1000 / an.fps;
      const dt = now - E.playState.last;
      if (dt >= frameMs) {
        const steps = Math.max(1, Math.floor(dt / frameMs));
        E.playState.last += steps * frameMs;
        for (let s = 0; s < steps; s++) advanceFrame(an);
        drawFrame(E.playState.idx);
        syncScrubber();
      }
      E.playState.raf = requestAnimationFrame(step);
    };
    drawFrame(0);
    syncScrubber();
    E.playState.raf = requestAnimationFrame(step);
  }
  E.startPlayback = startPlayback;

  function advanceFrame(an) {
    const coreLen = E.bundle.core.length;
    if (E.playState.idx < coreLen - 1) {
      E.playState.idx++;
      return;
    }
    // At or past the last core frame: spend the hold tail, then loop or stop.
    if (E.playState.holdLeft > 0) {
      E.playState.holdLeft--;
      return;
    }
    if (E.playState.looping) {
      E.playState.idx = 0;
      E.playState.holdLeft = an.hold;
    } else {
      stopPlayback();
    }
  }

  function stopPlayback() {
    if (E.playState.raf) cancelAnimationFrame(E.playState.raf);
    E.playState.raf = null;
    E.playState.on = false;
    playPauseEl.classList.remove("playing");
  }
  E.stopPlayback = stopPlayback;

  // Draw frame `idx` onto the stage. In animation mode the SVG / PNG exporters
  // follow the scrubber: `lastSvg`/`lastMotif`/`lastFrameIdx` are refreshed here
  // so the SVG button downloads the frame the user is looking at and PNG can
  // rebuild the same frame's design through the `export_stored_png` bridge.
  function drawFrame(idx) {
    if (!E.bundle || !E.bundle.core) return;
    const svg = E.bundle.core[Math.min(idx, E.bundle.core.length - 1)];
    if (!svg) return;
    // The bundle records the world->display scale it was rendered with (see
    // preRenderChunks); carry it onto the namespace so the grid overlay, the
    // readout and the zoom indicator stay right across playback and scrubbing.
    if (E.bundle.scale != null) E.scale = E.bundle.scale;
    // The displayed frame's display bounds follow the frame, so "fit to view"
    // frames the geometry the user is actually looking at (a growing radius
    // changes the picture's box every frame).
    if (E.bundle.bounds) {
      const b = E.bundle.bounds[Math.min(idx, E.bundle.bounds.length - 1)];
      E.dispBounds = (b && b.w > 0) ? b : null;
    }
    E.motifSvgs().forEach((s) => s.remove());
    stageEl.insertAdjacentHTML("beforeend", E.stripXmlDecl(svg));
    placeholderEl.classList.remove("busy", "error");
    placeholderEl.style.display = "none";
    // The display render is a fixed 520x520 canvas, so the stage's zoom/pan
    // viewBox applies the same way it does to a still. Reapply the live
    // viewBox across frames so playback and scrubbing do not clobber the
    // user's zoom/pan; only fit on the first frame or after a motif switch
    // (the zoom belongs to the old picture then).
    const fit = E.lastMotif !== E.current || !E.viewBox;
    // Stash the current frame so SVG export (which reads lastSvg) and PNG
    // export (which keys on lastFrameIdx) match the scrubber, not the last
    // still render.
    E.lastSvg = svg;
    E.lastMotif = E.current;
    E.lastFrameIdx = Math.min(idx, E.bundle.core.length - 1);
    E.captureNatural();
    if (fit) E.fitView();
    else E.applyViewBox();
  }
  E.drawFrame = drawFrame;

  // Scrubber -> frame index. The scrubber spans the full core run (the hold
  // tail is playback-only and not scrubbed). The single clock is the stage
  // scrubber; its `t = 0.000` readout follows so the canvas-side clock reads
  // the live time.
  function syncScrubber() {
    if (!stageScrubEl) return;
    if (!E.bundle || !E.bundle.core) {
      stageScrubEl.value = 0;
      paintScrubTime(0);
      return;
    }
    const t = E.bundle.core.length > 1 ? E.playState.idx / (E.bundle.core.length - 1) : 0;
    const tc = Math.min(1, Math.max(0, t));
    stageScrubEl.value = tc;
    paintScrubTime(tc);
  }
  E.syncScrubber = syncScrubber;

  function paintScrubTime(t) {
    const txt = "t = " + Number(t).toFixed(3);
    if (scrubTimeEl) scrubTimeEl.textContent = txt;
    // The "Set keyframes for all params at t=..." button's t= span follows the same clock
    // so the button always shows the time a drop will land on. Mirrored on
    // every syncScrubber + scrub-input call, so dragging either scrubber or
    // playing back keeps the label honest.
    if (kfSetAllTEl) kfSetAllTEl.textContent = Number(t).toFixed(3);
  }

  // The scrubber's current time as a clamped 0..1 number, read from the stage
  // scrubber's live value. Used by the "Set keyframes for all params" + per-track "+" handlers
  // so a drop lands at the time the user is looking at. Before a bundle is
  // ready the scrubber sits at 0, which is the right default (the default
  // recipe's first keyframe is at t=0).
  function currentScrubT() {
    if (!stageScrubEl) return 0;
    const v = Number(stageScrubEl.value);
    if (!Number.isFinite(v)) return 0;
    return Math.min(1, Math.max(0, v));
  }
  E.currentScrubT = currentScrubT;

  // Restart pre-render + playback after a timeline edit. Reuses the cache when
  // the bundle key is unchanged (e.g. a pure playback param changed); otherwise
  // starts a fresh build.
  function restartPlayback(info, st, an) {
    if (!E.animOn) return;
    startAnim(info, st, an);
    // The timeline changed, so the share URL's `a=` pair must follow. Debounced
    // so a rapid drag rewrites the hash once, not once per pointermove tick.
    E.scheduleFragmentWrite();
  }
  E.restartPlayback = restartPlayback;

  // Debounced rebuild of the animation bundle after a *static* state edit made
  // in Animate mode -- a parameter with no keyframing path (resolution, Point
  // center, ...) can only take effect through the motif's base state, so it
  // rebuilds the frames rather than previewing a dead-end value. The debounce
  // reuses the render cadence so a number input's keystrokes coalesce into one
  // build; the guard ensures only the live animation (and only the newest edit)
  // triggers the rebuild.
  let animRebuildTimer = null;
  function scheduleAnimRebuild(info, st, an) {
    if (animRebuildTimer) clearTimeout(animRebuildTimer);
    animRebuildTimer = setTimeout(() => {
      animRebuildTimer = null;
      if (!E.animOn || E.anim !== an) return;
      if (!info || !info.available || E.byName[info.name] !== info) return;
      restartPlayback(info, st, an);
    }, E.RENDER_DEBOUNCE_MS || 30);
  }
  E.scheduleAnimRebuild = scheduleAnimRebuild;

  function showAnimError(msg) {
    E.motifSvgs().forEach((s) => s.remove());
    placeholderEl.classList.remove("busy");
    placeholderEl.classList.add("error");
    placeholderEl.style.display = "";
    phMain.textContent = msg;
  }
  E.showAnimError = showAnimError;

  function showAnimProgress(frac) {
    animProgressEl.classList.add("on");
    animProgressFill.style.width = (frac * 100) + "%";
  }
  E.showAnimProgress = showAnimProgress;
  function hideAnimProgress() { animProgressEl.classList.remove("on"); }
  E.hideAnimProgress = hideAnimProgress;

  // --- discoverable keyframe creation -------------------------------------
  // The "Set keyframes for all params at t=..." button at the top of the
  // tracks section drops a keyframe for every animatable parameter at the
  // scrubber's current time, each holding its slider's current value. It is
  // the obvious affordance -- the per-track "+" buttons remain, but this is
  // the one a new user finds first. The t= span is live, so the button always
  // tells the user what they will get.
  if (kfSetAllEl) {
    kfSetAllEl.addEventListener("click", () => {
      if (!E.animOn || !E.current) return;
      const info = E.byName[E.current];
      if (!info || !info.available) return;
      const an = E.anim;
      const params = animatableParams(info);
      if (!params.length) return;
      const t = currentScrubT();
      const wasEmpty = !params.some((p) => {
        const tr = an.tracks[p.name];
        return tr && tr.keyframes && tr.keyframes.length;
      });
      for (const p of params) dropKeyframe(p, E.state, an, t);
      // Always repaint after the drop. When the timeline was empty the whole
      // track list has to come in (the empty-state card is replaced by real
      // rows); when it already had keyframes the affected lanes' dots must
      // appear immediately rather than waiting for a slider to touch them.
      if (wasEmpty) {
        paintTimeline(info, E.state);
      } else {
        for (const p of params) {
          const ref = trackRefs.get(p.name);
          if (ref) paintLaneDots(ref.lane, p, an);
          else {
            const lane = tracksEl.querySelector(`.lane[data-param="${p.name}"]`);
            if (lane) paintLaneDots(lane, p, an);
          }
        }
      }
      E.restartPlayback(info, E.state, an);
    });
  }

  // --- GIF export -------------------------------------------------------------
  // Rebuilds the same run the SPA just played, with the recipe's hold, and
  // writes it through the pure-stdlib `save_gif` to Pyodide's in-memory FS. The
  // bytes match `geomotif render --animation spec.json` by construction (same
  // primitive, same writer, same default export styling).
  expGifEl.addEventListener("click", async () => {
    if (!E.animOn || !E.current) return;
    // Show the "exporting…" indicator and let it paint before the synchronous
    // Pyodide call blocks the main thread (see startExport in explore-view.js).
    await E.startExport(expGifEl);
    try {
      await E.ensurePyodide();
      const info = E.byName[E.current];
      const an = E.anim;
      const result = E.pyExportGif(
        info.name, JSON.stringify(E.state || {}), JSON.stringify(animRecipe(an).tracks),
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
      E.download(new Blob([data], { type: "image/gif" }), `${info.name}.gif`);
      E.flash(expGifEl, true, "saved", "failed");
    } catch (e) {
      E.flash(expGifEl, false, "saved", "failed");
    } finally {
      E.endExport(expGifEl);
    }
  });

  // --- transport events -------------------------------------------------------
  playPauseEl.addEventListener("click", () => {
    if (!E.animOn || !E.bundle) return;
    if (E.playState.on) { E.playWanted = false; stopPlayback(); }
    else startPlayback(E.byName[E.current], E.anim);
  });

  loopEl.addEventListener("click", () => {
    E.playState.looping = !E.playState.looping;
    loopEl.setAttribute("aria-pressed", String(E.playState.looping));
  });

  animFramesEl.addEventListener("input", () => {
    if (!E.anim) return;
    const v = Math.min(ANIM_FRAMES_MAX, Math.max(ANIM_FRAMES_MIN, Math.round(Number(animFramesEl.value) || E.anim.frames)));
    E.anim.frames = v;
    animHoldEl.max = Math.max(0, Math.floor(v / 4));
    if (E.anim.hold > Math.floor(v / 4)) {
      E.anim.hold = Math.floor(v / 4);
      animHoldEl.value = E.anim.hold;
    }
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });

  animFpsEl.addEventListener("input", () => {
    if (!E.anim) return;
    const v = Math.min(ANIM_FPS_MAX, Math.max(ANIM_FPS_MIN, Math.round(Number(animFpsEl.value) || E.anim.fps)));
    E.anim.fps = v;
    animFpsEl.value = v;
    // fps is a playback-only param: no re-render, just keep the live loop on the
    // new cadence. It still changes the share URL's recipe, so the fragment
    // follows on the same debounced cadence.
    if (E.playState.on) {
      stopPlayback();
      startPlayback(E.byName[E.current], E.anim);
    }
    E.scheduleFragmentWrite();
  });

  animHoldEl.addEventListener("input", () => {
    if (!E.anim) return;
    const max = Math.max(0, Math.floor(E.anim.frames / 4));
    const v = Math.min(max, Math.max(ANIM_HOLD_MIN, Math.round(Number(animHoldEl.value) || 0)));
    E.anim.hold = v;
    animHoldEl.value = v;
    // hold is a playback-only param: the bundle's core is unchanged, only the
    // tail length moves. No re-render. The recipe's hold rides the share URL,
    // so the fragment follows.
    if (E.bundle) E.bundle.count = E.bundle.core.length + v;
    if (E.playState.on) {
      stopPlayback();
      startPlayback(E.byName[E.current], E.anim);
    }
    E.scheduleFragmentWrite();
  });

  animEaseEl.addEventListener("change", () => {
    if (!E.anim) return;
    E.anim.easing = animEaseEl.value;
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });

  // Scrubbers: drag to scrub (canvas shows the frame at that time), click to
  // jump. While scrubbing, playback is paused so the hand on the scrubber is
  // the only clock. The single scrubber is the stage scrubber
  // (#stage-scrub-input); the time readout follows.
  function onScrubDown() {
    E.scrubbing = true;
    if (E.playState.on) stopPlayback();
  }
  function onScrubInput() {
    if (!E.bundle || !E.bundle.core || !stageScrubEl) return;
    const t = Math.min(1, Math.max(0, Number(stageScrubEl.value)));
    const idx = Math.round(t * (E.bundle.core.length - 1));
    E.playState.idx = Math.min(idx, E.bundle.core.length - 1);
    paintScrubTime(t);
    drawFrame(E.playState.idx);
  }
  function onScrubUp() { E.scrubbing = false; }

  if (stageScrubEl) {
    stageScrubEl.addEventListener("pointerdown", onScrubDown);
    stageScrubEl.addEventListener("input", onScrubInput);
    stageScrubEl.addEventListener("pointerup", onScrubUp);
  }

  // Overlay checkboxes. Toggling one adds/removes the matching entry on
  // `anim.overlays` and re-renders (overlays are post-passes on the geometry).
  function overlayEntry(type) {
    return E.anim.overlays.find((o) => o.type === type);
  }
  // Parse the trail field for the draw-on overlay. Empty means "none" (no
  // comet) and a non-positive number is treated the same way: a trail needs a
  // length, so 0 is not a meaningful value -- lowering the arrow buttons to 0
  // returns the motion to a plain pen reveal instead of silently cancelling it
  // into blank frames.
  function parseTrail() {
    const s = ovTrailEl.value.trim();
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  ovDrawEl.addEventListener("change", () => {
    if (!E.anim) return;
    if (ovDrawEl.checked) {
      if (!overlayEntry("draw_on")) E.anim.overlays.push({ type: "draw_on", trail: null });
      const e = overlayEntry("draw_on");
      e.trail = parseTrail();
      if (e.trail === null && ovTrailEl.value.trim() !== "") ovTrailEl.value = "";
    } else {
      E.anim.overlays = E.anim.overlays.filter((o) => o.type !== "draw_on");
    }
    paintTransport(E.anim);
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });
  ovTrailEl.addEventListener("input", () => {
    if (!E.anim) return;
    const e = overlayEntry("draw_on");
    if (!e) return;
    e.trail = parseTrail();
    // Drop the explicit 0 back to the "none" placeholder so the field reads
    // what it means.
    if (e.trail === null && ovTrailEl.value.trim() !== "") ovTrailEl.value = "";
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });
  ovSpinEl.addEventListener("change", () => {
    if (!E.anim) return;
    if (ovSpinEl.checked) {
      if (!overlayEntry("spin")) E.anim.overlays.push({ type: "spin", turns: 1.0 });
      const e = overlayEntry("spin");
      e.turns = Number(ovTurnsEl.value) || 1.0;
    } else {
      E.anim.overlays = E.anim.overlays.filter((o) => o.type !== "spin");
    }
    paintTransport(E.anim);
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });
  ovTurnsEl.addEventListener("input", () => {
    if (!E.anim) return;
    const e = overlayEntry("spin");
    if (!e) return;
    e.turns = Number(ovTurnsEl.value) || 1.0;
    restartPlayback(E.byName[E.current], E.state, E.anim);
  });
})(window.EXPLORE);
