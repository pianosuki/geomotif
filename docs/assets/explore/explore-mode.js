"use strict";

// Top-level Design / Animate mode tabs and the right-panel swap they drive.
// A segmented control in the SPA header replaces the
// stage-toolbar Play button as the single entry point to animation mode:
// clicking Animate calls E.enterAnim(), clicking Design calls E.exitAnim().
// The tab state mirrors E.animOn so a share URL that boots straight into
// animation (selectMotif -> enterAnim) lights the Animate tab without a
// separate wiring path -- enterAnim / exitAnim call E.syncModeTabs() once the
// mode flips.
//
// The right-hand panel is a Design / Animate tabpair. The Design panel
// (.controls) carries the still SVG / PNG / spec export row; the Animate panel
// (.animator) carries the scrubber, the timeline, the transport / overlays,
// and the GIF + spec-JSON animation exports. The single #controls slider list
// is reparented between the two panels with appendChild (no cloning), so every
// slider handler survives the swap -- the user moves the same sliders to set
// keyframe values they already know from Design mode.
//
// Keyboard: ArrowLeft / ArrowRight move focus between tabs and activate the
// newly focused one, the standard tablist pattern; Enter / Space are the
// <button> default and need no handler here. aria-selected is kept in sync
// with E.animOn, and each panel carries role="tabpanel" labeled by its tab.

(function (E) {
  const { modeDesignEl, modeAnimateEl, designPanelEl, animatorEl,
          controlsSlotEl, animControlsSlotEl, controlsEl } = E;
  // The two tabs in tabing order; the active one keeps tabIndex 0 and the
  // inactive gets -1 so the keyboard stays on a single rail (roving tabindex).
  const tabs = [modeDesignEl, modeAnimateEl];

  // Reflect E.animOn onto the tab strip. Called at boot (from app.js after
  // initViewToggles) and after every enterAnim / exitAnim, so the tabs never
  // drift from the real mode even when the mode flip came from a share URL
  // restore rather than a tab click. Also drives the panel swap (syncPanels)
  // so the visible aside and the reparented #controls follow the mode.
  function syncModeTabs() {
    const on = !!E.animOn;
    modeDesignEl.setAttribute("aria-selected", String(!on));
    modeAnimateEl.setAttribute("aria-selected", String(on));
    modeDesignEl.tabIndex = on ? -1 : 0;
    modeAnimateEl.tabIndex = on ? 0 : -1;
    syncPanels(on);
  }
  E.syncModeTabs = syncModeTabs;

  // Swap the right-hand panel to match the mode. The hidden attribute on the
  // animator aside is the only show/hide lever -- the Design aside is always
  // visible (its contents are simply the still controls + exports). The
  // #controls list is reparented, not cloned: appendChild moves the live
  // element, so every slider's event listener keeps firing. In Design mode
  // #controls lives in #controls-slot (inside .controls); in Animate mode it
  // lives in #anim-controls-slot (inside .animator, below the scrubber).
  function syncPanels(animate) {
    if (animate) {
      designPanelEl.hidden = true;
      animatorEl.hidden = false;
      if (animControlsSlotEl && controlsEl && controlsEl.parentElement !== animControlsSlotEl) {
        animControlsSlotEl.appendChild(controlsEl);
      }
    } else {
      animatorEl.hidden = true;
      designPanelEl.hidden = false;
      if (controlsSlotEl && controlsEl && controlsEl.parentElement !== controlsSlotEl) {
        controlsSlotEl.appendChild(controlsEl);
      }
    }
  }
  E.syncPanels = syncPanels;

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
