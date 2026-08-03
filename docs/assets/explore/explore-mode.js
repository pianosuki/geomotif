"use strict";

// Top-level Design / Animate mode tabs (Workstream C1). A segmented control in
// the SPA header replaces the stage-toolbar Play button as the single entry
// point to animation mode: clicking Animate calls E.enterAnim(), clicking
// Design calls E.exitAnim(). The tab state mirrors E.animOn so a share URL
// that boots straight into animation (selectMotif -> enterAnim) lights the
// Animate tab without a separate wiring path -- enterAnim / exitAnim call
// E.syncModeTabs() once the mode flips.
//
// Keyboard: ArrowLeft / ArrowRight move focus between tabs and activate the
// newly focused one, the standard tablist pattern; Enter / Space are the
// <button> default and need no handler here. aria-selected is kept in sync
// with E.animOn; the tabpanel roles land with the animator panel in C2, so for
// now the tabs announce as a mode switcher over the same right-hand controls.

(function (E) {
  const { modeDesignEl, modeAnimateEl } = E;
  // The two tabs in tabbing order; the active one keeps tabIndex 0 and the
  // inactive gets -1 so the keyboard stays on a single rail (roving tabindex).
  const tabs = [modeDesignEl, modeAnimateEl];

  // Reflect E.animOn onto the tab strip. Called at boot (from app.js after
  // initViewToggles) and after every enterAnim / exitAnim, so the tabs never
  // drift from the real mode even when the mode flip came from a share URL
  // restore rather than a tab click.
  function syncModeTabs() {
    const on = !!E.animOn;
    modeDesignEl.setAttribute("aria-selected", String(!on));
    modeAnimateEl.setAttribute("aria-selected", String(on));
    modeDesignEl.tabIndex = on ? -1 : 0;
    modeAnimateEl.tabIndex = on ? 0 : -1;
  }
  E.syncModeTabs = syncModeTabs;

  // Clicking a tab is a no-op when that mode is already active -- the tabs are
  // a state indicator as much as a switch, and a redundant click should not
  // re-enter animation (which would rebuild the bundle) or re-render a still.
  modeDesignEl.addEventListener("click", () => {
    if (!E.animOn) return;
    E.exitAnim();
  });
  modeAnimateEl.addEventListener("click", () => {
    if (E.animOn) return;
    if (!E.current) return; // nothing to animate yet (no motif picked)
    E.enterAnim();
  });

  // Arrow-key navigation: left moves toward Design, right toward Animate. The
  // newly focused tab activates immediately so a single keypress switches
  // modes (the user does not need Enter after moving focus).
  function onKey(e) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const n = e.key === "ArrowLeft"
      ? (i + tabs.length - 1) % tabs.length
      : (i + 1) % tabs.length;
    tabs[n].focus();
    tabs[n].click();
  }
  modeDesignEl.addEventListener("keydown", onKey);
  modeAnimateEl.addEventListener("keydown", onKey);
})(window.EXPLORE);
