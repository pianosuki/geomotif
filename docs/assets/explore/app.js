"use strict";

// Entry point: the cross-cutting event wiring that does not belong to a single
// module (copy command, share URL, back-button restore, the SVG/PNG/spec
// exports that span the still + animation render paths), then boot(). The
// modules loaded before this file have already attached their functions and
// wired their own listeners; this just stitches the last few pieces together.

(function (E) {
  const { copyEl, shareEl, expSvgEl, expPngEl, expSpecEl, expSpecAnimEl, commandEl } = E;

  // --- copy the live command line ---------------------------------------------
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
  // is the one the address bar shows afterwards. When the animation recipe
  // pushes the fragment past a safe URL limit (~2 KB), the URL would be
  // truncated by some browsers / chat clients; the share then falls back to
  // copying the spec JSON (which already carries the `animation` key from the
  // spec export) and flashes a hint to feed it to `geomotif render --animation`.
  // The CLI reproduces the GIF byte-for-byte from that spec either way.
  shareEl.addEventListener("click", async () => {
    if (!E.current) return;
    const animArg = E.animOn ? E.anim : null;
    const frag = E.encodeFragment(E.current, E.state, animArg);
    if (frag.length > E.SHARE_URL_LIMIT) {
      try {
        const spec = { geomotif: E.catalog ? E.catalog.geomotif : null, motif: E.current, params: E.state };
        if (animArg) spec.animation = E.animRecipe(animArg);
        await navigator.clipboard.writeText(JSON.stringify(spec, null, 2) + "\n");
        shareEl.textContent = "spec copied — too long for URL";
        shareEl.classList.add("ok");
        setTimeout(() => { shareEl.textContent = "copy share URL"; shareEl.classList.remove("ok"); }, 2000);
      } catch (e) {
        shareEl.textContent = "copy failed";
      }
      return;
    }
    try {
      E.writeFragment(E.current, E.state, animArg, true);
      await navigator.clipboard.writeText(location.href);
      shareEl.textContent = "copied";
      shareEl.classList.add("ok");
      setTimeout(() => { shareEl.textContent = "copy share URL"; shareEl.classList.remove("ok"); }, 1200);
    } catch (e) {
      shareEl.textContent = "copy failed";
    }
  });

  // Restoring from a back/forward navigation: the browser fires popstate when
  // the user lands on a fragment we wrote. Re-seed both still state and
  // timeline from it so the back button walks through shared views (still and
  // animated) rather than jumping past them.
  window.addEventListener("popstate", () => {
    const restored = E.readFragment();
    if (restored && E.byName[restored.motif]) {
      E.selectMotif(restored.motif, restored.params, { fromFragment: true, anim: restored.anim });
    }
  });

  // --- export (SVG / PNG / spec JSON) ------------------------------------------
  // All three downloads are built from `lastSvg` / `lastMotif` / `lastParams`
  // (or `lastFrameIdx` in animation mode), which `render()` / `drawFrame()`
  // refresh on every successful render. SVG reuses the cached prolog-bearing
  // SVG directly (no Pyodide call); PNG rebuilds the design under Pyodide with
  // the CLI's default styling so the bytes match `geomotif render <motif> --out
  // x.png`; in animation mode PNG rebuilds the *current frame's* design through
  // the `export_stored_png` bridge so the download matches the scrubber. Spec
  // is the full `to_spec` shape the CLI's `--spec` flag reads, written in JS
  // from `state` plus the catalog's geomotif version (with the `animation` key
  // alongside when the timeline is live).
  expSvgEl.addEventListener("click", () => {
    if (!E.lastSvg) return;
    // Keep the XML prolog so the file opens standalone and matches save_svg.
    E.download(new Blob([E.lastSvg], { type: "image/svg+xml" }), `${E.lastMotif}.svg`);
    E.flash(expSvgEl, true, "saved", "failed");
  });

  expPngEl.addEventListener("click", async () => {
    if (!E.lastMotif) return;
    // Show the "exporting…" indicator and let it paint before the synchronous
    // Pyodide call blocks the main thread (see startExport in explore-view.js).
    await E.startExport(expPngEl);
    try {
      await E.ensurePyodide();
      let data;
      if (E.animOn && E.bundle && E.lastFrameIdx >= 0) {
        // Animation mode: rebuild the frame the scrubber is showing, not the
        // last still. The design was already stashed by build_keyframes.
        const bytes = E.pyExportFramePng(E.lastFrameIdx);
        data = bytes instanceof Uint8Array ? bytes.slice() : new Uint8Array(bytes);
        E.download(new Blob([data], { type: "image/png" }), `${E.lastMotif}.png`);
      } else {
        const bytes = E.pyExportPng(E.lastMotif, JSON.stringify(E.lastParams || {}));
        // Pyodide converts Python bytes -> Uint8Array; build a Blob from a copy so
        // the underlying buffer is not shared with the Python heap.
        data = bytes instanceof Uint8Array ? bytes.slice() : new Uint8Array(bytes);
        E.download(new Blob([data], { type: "image/png" }), `${E.lastMotif}.png`);
      }
      E.flash(expPngEl, true, "saved", "failed");
    } catch (e) {
      E.flash(expPngEl, false, "saved", "failed");
    } finally {
      E.endExport(expPngEl);
    }
  });

  // Spec JSON export. The full `to_spec` shape (version key + motif name +
  // params, plus an `animation` key when the timeline is live) -- this is the
  // exact shape the CLI's `--spec` flag reads, so the downloaded file loads
  // straight into `geomotif render --spec <file>` (and `--animation` when the
  // `animation` key is present). Two buttons trigger it: the Design panel's
  // `#exp-spec` (still mode) and the Animator panel's `#exp-spec-anim`
  // (animation mode). Both produce the same bytes; the animator copy just
  // lives next to the GIF button so an animation-only user does not have to
  // flip back to Design to grab the spec.
  function exportSpec(btn) {
    if (!E.lastMotif) return;
    const spec = {
      geomotif: E.catalog ? E.catalog.geomotif : null,
      motif: E.lastMotif,
      params: E.state,
    };
    if (E.animOn && E.anim) spec.animation = E.animRecipe(E.anim);
    const blob = new Blob([JSON.stringify(spec, null, 2) + "\n"], { type: "application/json" });
    E.download(blob, `${E.lastMotif}.json`);
    E.flash(btn, true, "saved", "failed");
  }
  expSpecEl.addEventListener("click", () => exportSpec(expSpecEl));
  expSpecAnimEl.addEventListener("click", () => exportSpec(expSpecAnimEl));

  // --- go ---------------------------------------------------------------------
  E.initViewToggles();
  // The mode tabs default to Design (E.animOn is false at boot); syncing here
  // sets the initial aria-selected / tabIndex so a share URL that boots into
  // Animate mode can flip them later via enterAnim -> syncModeTabs.
  if (E.syncModeTabs) E.syncModeTabs();
  E.boot();
})(window.EXPLORE);
