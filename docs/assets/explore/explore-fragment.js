"use strict";

// Share-URL fragment layer. The hash carries one or two key=value pairs
// separated by `&`:
//
//   #m=<still>&a=<anim>
//
// `m=` is the still spec: base64url of a compact JSON blob `{"m": motif,
// "p": params}`. base64url keeps the value free of `+`/`/`/`=` so it never
// needs percent-encoding. The CLI never sees this compact form: the SPA
// expands it back to the full `{"motif":..., "params":...}` shape before
// calling from_spec, so a shared view round-trips with `geomotif render
// --spec` byte-for-byte by construction.
//
// `a=` is the animation recipe: the `animRecipe(anim)` output
// compressed with lz-string's `compressToEncodedURIComponent` -- the one
// vendored client dependency (see lz-string.js). That compressor's alphabet
// is URL-safe (no `&`, no `=`, no `/`), so its output can sit directly in
// the hash without a second base64 pass. Landing on a URL with an `a=` pair
// boots straight into animation mode with the timeline populated.
//
// Both values use alphabets that omit `&` and `=`, so `&` is a safe pair
// separator and `=` cleanly splits each pair into key/value. Either pair
// may be absent; a still-only share URL is just `#m=...`.

(function (E) {
  const { SHARE_URL_LIMIT, RENDER_DEBOUNCE_MS, RESERVED } = E;

  function encodeFragment(motif, params, anim) {
    // Still pair: base64url of `{"m": motif, "p": params}`. btoa handles
    // Latin-1; motif params are ASCII (numbers, strings, arrays, plain objects),
    // so no UTF-8 re-encoding is needed.
    const json = JSON.stringify({ m: motif, p: params });
    const b64 = btoa(json);
    const still = "m=" + b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    // Animation pair (only when the timeline is live): the recipe compressed with
    // lz-string's URI-safe codec. Its alphabet omits `&`/`=`/`/`, so the output
    // drops straight into the hash without a second base64 pass.
    const parts = [still];
    if (anim) {
      const recipe = E.animRecipe(anim);
      const compressed = LZString.compressToEncodedURIComponent(JSON.stringify(recipe));
      if (compressed) parts.push("a=" + compressed);
    }
    return "#" + parts.join("&");
  }
  E.encodeFragment = encodeFragment;

  function decodeFragment(hash) {
    if (!hash) return null;
    let frag = String(hash);
    if (frag.startsWith("#")) frag = frag.slice(1);
    if (!frag) return null;
    // The hash is `&`-separated `key=value` pairs. Each value's alphabet omits
    // `&` and `=`, so a split on `&` then first-`=` split cleanly partitions it.
    // An unknown key is ignored, so a later `x=` pair degrades instead of
    // throwing the whole restore away.
    let mRaw = null, aRaw = null;
    for (const part of frag.split("&")) {
      const eq = part.indexOf("=");
      if (eq < 0) continue;
      const key = part.slice(0, eq);
      const val = part.slice(eq + 1);
      if (key === "m") mRaw = val;
      else if (key === "a") aRaw = val;
    }
    if (mRaw == null) return null;
    // Still pair: base64url -> JSON `{"m":..., "p":...}`. A malformed or
    // hand-edited value degrades to null (the caller falls back to the default
    // first motif).
    let motif, params;
    {
      let b64 = mRaw.replace(/-/g, "+").replace(/_/g, "/");
      while (b64.length % 4) b64 += "=";
      try {
        const obj = JSON.parse(atob(b64));
        if (!obj || typeof obj.m !== "string") return null;
        if (obj.p != null && typeof obj.p !== "object") return null;
        motif = obj.m;
        params = obj.p || {};
      } catch (e) {
        return null;
      }
    }
    // Animation pair: lz-string URI-safe decompress -> JSON recipe. An empty or
    // garbage value yields null, so a still-only share URL or a stale `a=` part
    // boots into still mode rather than throwing.
    let anim = null;
    if (aRaw != null && aRaw !== "") {
      try {
        const json = LZString.decompressFromEncodedURIComponent(aRaw);
        const recipe = json == null ? null : JSON.parse(json);
        if (recipe && typeof recipe === "object" && recipe.type === "keyframes") {
          anim = recipe;
        }
      } catch (e) {
        anim = null;
      }
    }
    return { motif, params, anim };
  }
  E.decodeFragment = decodeFragment;

  function readFragment() {
    return decodeFragment(location.hash);
  }
  E.readFragment = readFragment;

  // Write the current view into the URL fragment. `push` false uses replaceState
  // (in-session sync); `push` true uses pushState (explicit share, a real
  // history entry the back button can return to). `anim` is the live animation
  // recipe when the timeline is open, so a shared animation URL carries the
  // keyframes alongside the still spec.
  function writeFragment(motif, params, anim, push) {
    const frag = encodeFragment(motif, params, anim);
    if (frag === location.hash) return;
    const url = location.pathname + location.search + frag;
    if (push) history.pushState(null, "", url);
    else history.replaceState(null, "", url);
  }
  E.writeFragment = writeFragment;

  // Fold a params dict decoded from a share URL into the freshly-seeded state.
  // Only settable params that the catalog actually knows about are written, so a
  // stale share URL (renamed param, dropped field) degrades gracefully instead
  // of feeding from_spec a key the motif rejects.
  function applyOverride(st, info, override) {
    if (!override || typeof override !== "object") return;
    const known = Object.create(null);
    for (const p of info.params) known[p.name] = p;
    for (const key of Object.keys(override)) {
      const p = known[key];
      if (!p || RESERVED.has(p.name)) continue;
      if (!E.isSettable(p)) continue;
      st[key] = E.clone(override[key]);
    }
  }
  E.applyOverride = applyOverride;

  // Debounced replaceState of the full fragment (still + animation). Every
  // animation-mode change point (keyframe drop/drag/delete, easing, overlays,
  // frames, fps, hold) routes through here so a timeline edit never spams the
  // history stack -- it replaces the current entry on the same ~30 ms cadence
  // the still mode uses.
  function scheduleFragmentWrite() {
    if (E.fragTimer) clearTimeout(E.fragTimer);
    E.fragTimer = setTimeout(() => {
      E.fragTimer = null;
      if (E.current) writeFragment(E.current, E.state, E.animOn ? E.anim : null, false);
    }, RENDER_DEBOUNCE_MS);
  }
  E.scheduleFragmentWrite = scheduleFragmentWrite;
})(window.EXPLORE);
