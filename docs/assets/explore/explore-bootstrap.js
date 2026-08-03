"use strict";

// Single shared namespace for the explore SPA. Every module attaches its
// public surface (functions, constants, DOM handles, mutable state) to this
// object so the split files read like one file without a build step. Loaded
// first so the namespace exists before any module's IIFE runs.
window.EXPLORE = window.EXPLORE || {};

(function (E) {
  // --- constants ---------------------------------------------------------------
  // Pyodide ships from the official CDN; the version is a single pin so a later
  // step can vendor it for offline use. The geomotif wheel is copied next to the
  // SPA at deploy time; its name carries the catalog's version, so the
  // pinned build and the runtime stay in lockstep automatically.
  E.PYODIDE_VERSION = "0.26.4";
  E.CACHE_SIZE = 256;

  // A URL fragment past ~2 KB risks truncation in some browsers and chat
  // clients. When the animation recipe pushes the share fragment over this limit
  // the share button copies the spec JSON instead (see the share handler).
  E.SHARE_URL_LIMIT = 2000;

  // Parameter names the CLI reserves for its own flags and never accepts on a
  // motif -- mirrors RESERVED in src/geomotif/cli.py so the command line is
  // copy-paste accurate.
  E.RESERVED = new Set([
    "aa_level", "antialias", "background", "by", "compression", "distribute",
    "dither", "dot_radius", "ease", "fit", "fps", "frames", "hold", "ink",
    "keep_duplicates", "landscape", "loop", "margin", "motion", "optimize",
    "out", "padding", "paper", "precision", "quality", "samples", "snap",
    "snap_mode", "spec", "stride", "title", "transparent",
  ]);

  // Annotations the CLI turns into a flag -- mirrors _flag_for in cli.py. Anything
  // else (Projection, Callable, Sequence[Point], nested motifs, ...) is not a
  // flag and is held at its declared default.
  E.SETTABLE = new Set([
    "bool", "int", "int | None", "float", "float | None",
    "str", "str | None", "Point", "Point | None", "Bounds", "Bounds | None",
  ]);

  // Spread used by the geometric heuristic for numeric params without a declared
  // Range -- mirrors explore._SPREAD so the SPA's guessed sliders cover the same
  // ground the CLI explore page would.
  E.SPREAD = 2.0;

  // Render debounce. Each input event clears the pending timer and arms a fresh
  // one; when it fires the actual render runs inside a requestAnimationFrame so
  // the browser has finished painting the input's own state. ~30 ms is long
  // enough to coalesce a rapid slider drag, short enough to feel instant.
  E.RENDER_DEBOUNCE_MS = 30;

  E.ZOOM_STEP = Math.sqrt(2); // one button click ≈ one stop

  E.THEME_KEY = "geomotif.theme";
  E.GRID_KEY = "geomotif.grid";
  E.AXES_KEY = "geomotif.axes";
  E.LABELS_KEY = "geomotif.labels";

  // Animation-mode bounds and pre-render chunk size.
  E.EASINGS = ["linear", "quadratic", "cubic", "sinusoidal", "exponential", "circular"];
  E.ANIM_FRAMES_MIN = 32; E.ANIM_FRAMES_MAX = 240;
  E.ANIM_FPS_MIN = 1; E.ANIM_FPS_MAX = 60;
  E.ANIM_HOLD_MIN = 0;
  E.PRE_FRAMES_PER_TICK = 4;
  E.ANIM_CACHE_SIZE = 16;

  // A coarse pointer (touch) makes keyframe dot dragging genuinely awkward, so
  // the timeline degrades to read-only (scrub + play) with an "edit on desktop"
  // hint, mirroring the "Mobile" considerations.
  E.IS_TOUCH = (window.matchMedia && window.matchMedia("(pointer: coarse)").matches)
    || (navigator.maxTouchPoints || 0) > 0;

  // --- DOM handles -------------------------------------------------------------
  // Scripts sit at the end of <body>, so the document is parsed and
  // getElementById resolves. Stable references (set once, never reassigned):
  // modules destructure these at the top of their IIFE so the existing
  // bare-name style survives the split.
  E.$ = (id) => document.getElementById(id);
  E.statusEl = E.$("status");
  E.toastEl = E.$("toast");
  E.progressEl = E.$("progress");
  E.progressFill = E.progressEl.querySelector("i");
  E.familiesEl = E.$("families");
  E.motifsEl = E.$("motifs");
  E.stageEl = E.$("stage");
  E.placeholderEl = E.$("placeholder");
  E.phMain = E.$("ph-main");
  E.metaEl = E.$("meta");
  E.controlsEl = E.$("controls");
  E.commandEl = E.$("command");
  E.copyEl = E.$("copy");
  E.shareEl = E.$("share");
  E.expSvgEl = E.$("exp-svg");
  E.expPngEl = E.$("exp-png");
  E.expSpecEl = E.$("exp-spec");
  E.zoomOutEl = E.$("zoom-out");
  E.zoomInEl = E.$("zoom-in");
  E.fitEl = E.$("fit");
  E.tgGridEl = E.$("tg-grid");
  E.tgAxesEl = E.$("tg-axes");
  E.tgLabelsEl = E.$("tg-labels");
  // The three view toggles collapse into a gear-triggered popover under
  // 50rem. The popover wrapper (#tg-popover) holds the toggle body and the
  // gear button (#tg-gear); explore-view.js toggles the wrapper's `.open`
  // class and mirrors aria-expanded. On wide viewports the gear is hidden
  // and the body unwraps inline (display: contents), so the same three toggle
  // buttons serve both layouts.
  E.tgPopoverEl = E.$("tg-popover");
  E.tgGearEl = E.$("tg-gear");
  E.gridOverlayEl = E.$("grid-overlay");
  E.coordReadoutEl = E.$("coord-readout");
  E.zoomIndEl = E.$("zoom-ind");
  E.themeEl = E.$("theme");
  E.modeDesignEl = E.$("mode-design");
  E.modeAnimateEl = E.$("mode-animate");
  // The Design / Animate tabs each own a tabpanel aside
  // (.controls / .animator). The shared #controls list lives in a slot
  // (#controls-slot) so explore-mode.js can reparent it into the animator
  // (and back) with appendChild -- preserving every slider handler -- rather
  // than cloning. expGifEl now lives in the animator; the still SVG / PNG /
  // spec exports stay in the Design panel, and an animation-mode spec export
  // (#exp-spec-anim) sits beside the GIF button.
  E.designPanelEl = E.$("design-panel");
  E.animatorEl = E.$("animator");
  E.controlsSlotEl = E.$("controls-slot");
  E.animControlsSlotEl = E.$("anim-controls-slot");
  E.overlaysEl = E.$("overlays");
  E.expSpecAnimEl = E.$("exp-spec-anim");
  E.timelineEl = E.$("timeline");
  E.animProgressEl = E.$("anim-progress");
  E.animProgressFill = E.animProgressEl.querySelector("i");
  E.transportEl = E.$("transport");
  E.playPauseEl = E.$("tp-play");
  E.loopEl = E.$("tp-loop");
  E.animFramesEl = E.$("tp-frames");
  E.animFpsEl = E.$("tp-fps");
  E.animHoldEl = E.$("tp-hold");
  E.animEaseEl = E.$("tp-easing");
  E.tracksEl = E.$("tracks");
  // A prominent "Set keyframe at t=..." button at the top of the tracks
  // section drops a keyframe for every animatable parameter at the scrubber's
  // current time. The t= span (#kf-set-all-t) updates live with the scrubber
  // so the button always reflects the time the user will get. The row wraps the
  // button so CSS can hide the whole affordance on touch (read-only timeline).
  E.kfSetAllEl = E.$("kf-set-all");
  E.kfSetAllTEl = E.$("kf-set-all-t");
  E.kfSetAllRowEl = E.$("kf-set-all-row");
  // The single master clock, pinned directly under the stage (the animator
  // panel no longer carries a scrubber). scrubTimeEl is the `t = 0.000` readout
  // beside the stage scrubber.
  E.stageScrubEl = E.$("stage-scrub-input");
  E.stageScrubWrapEl = E.$("stage-scrubber");
  E.scrubTimeEl = E.$("scrub-time");
  E.ovDrawEl = E.$("ov-draw");
  E.ovSpinEl = E.$("ov-spin");
  E.ovDrawOpts = E.$("ov-draw-opts");
  E.ovSpinOpts = E.$("ov-spin-opts");
  E.ovTrailEl = E.$("ov-trail");
  E.ovTurnsEl = E.$("ov-turns");
  E.expGifEl = E.$("exp-gif");

  // --- shared mutable state ----------------------------------------------------
  // These change as the user interacts; modules read/write through E.<name> so
  // every file sees the live value (a destructured `const` would capture a
  // stale snapshot). The catalog/Pyodide/load state lives here too.
  E.catalog = null;
  E.byName = Object.create(null);
  E.current = null;
  E.state = {};
  E.familyFilter = null;
  E.searchQuery = "";

  E.pyPromise = null;
  E.pyodide = null;
  E.pyRender = null;
  E.pyExportPng = null;
  E.pyExportFramePng = null;
  E.pyBuildKeyframes = null;
  E.pyRenderFrame = null;
  E.pyClearFrames = null;
  E.pyExportGif = null;
  E.WHEEL_URL = "";

  // LRU cache, insertion-ordered: the oldest entry is evicted when full.
  E.cache = new Map();

  // The last successfully rendered, full-prolog SVG (the bytes the CLI would
  // write) and the motif/params that produced it. Kept so the SVG / PNG / spec
  // exports reuse the same picture the user is looking at without a second
  // Pyodide round-trip for the SVG case, and so PNG/spec can rebuild it with
  // the right defaults. In animation mode `lastFrameIdx` marks the scrubber's
  // frame so PNG export rebuilds the *current* frame, not the last still. The
  // LRU stays keyed on geometry alone (name + params), never on the viewBox,
  // so zooming and panning never evict a render.
  E.lastSvg = null;
  E.lastMotif = null;
  E.lastParams = null;
  E.lastFrameIdx = -1;

  // viewBox for zoom/pan: the live box applied to the stage's <svg>, in user
  // units. `null` while no SVG is displayed (placeholder, unavailable motif, or
  // error). `naturalVB` is the box the renderer emitted -- the one "fit"
  // restores to.
  E.viewBox = null;
  E.naturalVB = null;

  // World -> display mapping, refreshed from every render/animation-frame
  // result. The display renderer anchors the world origin (0, 0, y-up) at the
  // centre of the stage canvas and scales by a fixed per-motif factor, so the
  // grid overlay and the cursor readout read `scale` to translate between the
  // live viewBox (display units, y-down) and world coordinates. `scale` is
  // null until the first successful render.
  E.scale = null;
  E.origin = { x: 260, y: 260 };

  E.renderTimer = null;
  E.fragTimer = null;
  E.pan = null;
})(window.EXPLORE);
