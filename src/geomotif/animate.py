"""Frames: the same design over time, or the same motif over a parameter.

A still image says what a design *is*. An animation says how it is made, which
for most of this catalog is the more interesting half -- watching a Hilbert
curve fill its square, or a rose's petal count climb, tells you something the
finished picture cannot.

Each function here returns a plain tuple of :class:`~geomotif.Design` s, one
per frame, so they compose with everything else: transform them, restyle them,
export one as SVG, or hand the lot to
:func:`~geomotif.io.gif.save_gif`::

    from geomotif.animate import draw_on, keyframes, spin, sweep
    from geomotif.io.gif import save_gif
    from geomotif.motifs import HilbertCurve, Rose

    save_gif(draw_on(HilbertCurve(depth=5).build(), frames=60), "hilbert.gif")
    save_gif(spin(Rose(n=5).build(), frames=48), "rose.gif")
    save_gif(sweep(Rose(), "n", range(2, 12)), "petals.gif")
    save_gif(keyframes(Rose(), {"n": [(0.0, 3), (1.0, 9)]}, frames=48), "grow.gif")

Nothing here is expensive: a frame is the same geometry seen differently, not
the motif built again -- except in :func:`sweep` and :func:`keyframes`, where
building it again is precisely the point.

:func:`keyframes` animates several parameters at once across arbitrary time
points, and is what the 1.3.0 web explorer's animation editor is built on;
:func:`compose` chains the post-passes (:func:`draw_on`, :func:`spin`) onto a
run of frames so a single ``--animation`` flag reproduces whatever the web
app produced.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from .core.sampling import ArcTable
from .core.spacing import (
    CircularSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    QuadraticSpacing,
    SineSpacing,
    SpacingCurve,
)
from .core.transform import Affine
from .core.types import Design, Path, select_styles

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .core.motif import SupportsBuild
    from .core.types import Point

__all__ = [
    "compose",
    "draw_on",
    "draw_on_overlay",
    "keyframes",
    "spin",
    "spin_overlay",
    "sweep",
]


def draw_on(
    design: Design,
    frames: int = 48,
    *,
    trail: float | None = None,
    hold: int = 0,
) -> tuple[Design, ...]:
    """Return frames revealing a design progressively, as a pen would draw it.

    Progress is measured in **arc length**, not in vertices, so the pen moves
    at a constant speed rather than racing through the sparse parts of the
    geometry and crawling through the dense ones. Strokes are drawn in the
    order the design holds them, and loose points appear in step with the
    strokes.

    Parameters
    ----------
    design : Design
        What to draw.
    frames : int
        How many frames to return, before ``hold``. Must be >= 1.
    trail : float, optional
        Draw only the last ``trail`` units of length rather than everything so
        far -- a comet rather than a pen. In the design's own units.
    hold : int
        Extra copies of the finished drawing to append, so an animation that
        loops pauses on the result instead of restarting the instant it
        arrives.

    Returns
    -------
    tuple of Design
        ``frames + hold`` of them. The first is a fraction of the way in
        rather than empty: a frame with nothing in it is a flash of blank
        canvas at the start of every loop.
    """
    if frames < 1:
        raise ValueError(f"frames must be >= 1, got {frames}")
    if hold < 0:
        raise ValueError(f"hold must be >= 0, got {hold}")
    if trail is not None and trail <= 0:
        raise ValueError(f"trail must be > 0, got {trail}")

    lengths = [path.length for path in design.paths]
    drawn = [_revealed(design, lengths, (i + 1) / frames, trail) for i in range(frames)]
    return tuple(drawn + [drawn[-1]] * hold)


def spin(
    design: Design,
    frames: int = 36,
    *,
    turns: float = 1.0,
    about: Point | None = None,
    hold: int = 0,
) -> tuple[Design, ...]:
    """Return frames of a design turning about a point.

    Parameters
    ----------
    design : Design
        What to turn.
    frames : int
        How many frames make up the whole rotation. Must be >= 1.
    turns : float
        Revolutions across the whole animation. Negative turns clockwise.
    about : (float, float), optional
        center of rotation. Defaults to the middle of the design's bounds,
        which is what keeps it inside the canvas.
    hold : int
        Extra copies of the finished drawing to append, so an animation that
        loops pauses on the result instead of restarting the instant it
        arrives.

    Returns
    -------
    tuple of Design
        ``frames + hold`` of them. The last frame stops one step short of the
        first, so a looping animation does not show the same picture twice in
        a row.
    """
    if frames < 1:
        raise ValueError(f"frames must be >= 1, got {frames}")
    if hold < 0:
        raise ValueError(f"hold must be >= 0, got {hold}")
    center = about if about is not None else (design.bounds.center if len(design) else (0.0, 0.0))
    step = math.tau * turns / frames
    turned = tuple(design.transformed(Affine.rotate(i * step, about=center)) for i in range(frames))
    return tuple(list(turned) + [turned[-1]] * hold)


def sweep(motif: SupportsBuild, parameter: str, values: Iterable[object]) -> tuple[Design, ...]:
    """Return one frame per value of one of a motif's parameters.

    The motif is rebuilt for each value, which is the only way to animate a
    parameter -- and cheap enough, since the whole catalog is built rather
    than loaded.

    Parameters
    ----------
    motif : Motif
        A dataclass motif, which every builtin one is.
    parameter : str
        Which parameter to vary.
    values : iterable
        What to set it to, in order.

    Returns
    -------
    tuple of Design

    Raises
    ------
    TypeError
        If the motif is not a dataclass, so there is nothing to vary by name.
    ValueError
        If it has no such parameter. The message lists the ones it does have.

    Examples
    --------
    >>> from geomotif.motifs import Rose
    >>> len(sweep(Rose(), "n", [3, 4, 5]))
    3
    """
    return _swept(motif, parameter, values)


def _swept(motif: object, parameter: str, values: Iterable[object]) -> tuple[Design, ...]:
    """Rebuild a motif once per value of one parameter.

    Typed as ``object`` for the same reason as the registry's introspection
    helpers: mypy cannot intersect the motif protocol with the dataclass one,
    and written against a motif type the whole body reads as unreachable. The
    narrowing has to happen where the class is not yet known to be a motif.
    """
    if not is_dataclass(motif) or isinstance(motif, type):
        raise TypeError(
            f"cannot sweep a parameter of {type(motif).__name__}: it is not a dataclass, "
            f"so it has no named parameters to vary. Build the frames yourself"
        )
    known = [field.name for field in fields(motif) if field.init]
    if parameter not in known:
        raise ValueError(f"{type(motif).__name__} takes one of {known}, got {parameter!r}")
    built = [replace(motif, **{parameter: value}) for value in values]
    return tuple(cast("SupportsBuild", changed).build() for changed in built)


def _revealed(
    design: Design,
    lengths: list[float],
    fraction: float,
    trail: float | None,
) -> Design:
    """Return the part of a design drawn once ``fraction`` of it has been walked."""
    total = math.fsum(lengths)
    distance = total * fraction
    behind = 0.0 if trail is None else max(distance - trail, 0.0)

    paths: list[Path] = []
    sources: list[int] = []
    walked = 0.0
    for index, (path, length) in enumerate(zip(design.paths, lengths, strict=True)):
        start, walked = walked, walked + length
        if length == 0.0:
            # A stroke with no length sits at one point of the walk rather than
            # spanning any of it, so the two tests below -- has the pen got
            # here, has the trail left it behind -- become the same test, and
            # the strict inequalities in them exclude it from every frame
            # including the last. It appears when the pen reaches it.
            if behind <= start <= distance:
                paths.append(path)
                sources.append(index)
            continue
        if walked <= behind or start >= distance:
            continue
        if start >= behind and walked <= distance:
            # Wholly drawn, so keep it exactly as it was -- closed flag and all,
            # which a sliced piece of it could not honestly claim.
            paths.append(path)
            sources.append(index)
            continue
        table = ArcTable(path.points, closed=path.closed)
        piece = table.segment(behind - start, distance - start)
        if len(piece) > 1:
            paths.append(replace(path, points=piece, closed=False))
            sources.append(index)

    # Loose points have no length to walk along, so they arrive in step with
    # the strokes -- and, in a design that is nothing but points, in step with
    # the frames themselves, which is the only clock a scatter field has.
    behind_fraction = 0.0 if trail is None or total == 0.0 else behind / total
    kept = list(
        range(
            round(len(design.points) * behind_fraction),
            round(len(design.points) * min(fraction, 1.0)),
        )
    )
    return Design(
        tuple(paths),
        tuple(design.points[i] for i in kept),
        select_styles(design.meta, paths=sources, points=kept),
    )


# --- keyframes: many parameters across arbitrary time points -----------------


#: The easing curves :func:`keyframes` accepts, by name. Each is a
#: :class:`~geomotif.core.spacing.SpacingCurve` mapping ``[0, 1] -> [0, 1]``
#: monotonically, which is exactly the shape a per-track interpolation needs.
#: The default mode of each modal curve (``"in"`` -- slow start, fast end) is
#: what "easing in" has always meant; a ``name:mode`` suffix such as
#: ``"cubic:out"`` picks a different one.
_EASINGS: dict[str, Callable[..., SpacingCurve]] = {
    "linear": LinearSpacing,
    "quadratic": QuadraticSpacing,
    "cubic": CubicSpacing,
    "sinusoidal": SineSpacing,
    "exponential": ExponentialSpacing,
    "circular": CircularSpacing,
}

#: The metadata key set on a frame that fell back to the last valid design
#: because its interpolated parameters were rejected by the motif. The web
#: explorer reads it to badge the segment as "interpolated through an invalid
#: range -- adjust keyframes".
FALLBACK_KEY = "keyframes_fallback"


def keyframes(
    motif: SupportsBuild,
    tracks: Mapping[str, object],
    *,
    frames: int = 48,
    fps: float = 20.0,
    hold: int = 0,
    easing: str = "linear",
) -> tuple[Design, ...]:
    """Return one design per frame, with named parameters eased across keyframes.

    Where :func:`sweep` varies a single parameter across a list of values,
    :func:`keyframes` varies several at once, each across its own time points.
    It is the primitive the 1.3.0 web explorer's animation editor is built on,
    so an animation a user shares from the browser reproduces in the CLI
    byte-for-byte.

    Parameters
    ----------
    motif : Motif
        A dataclass motif, which every builtin one is. The motif is rebuilt for
        each frame with that frame's interpolated parameters.
    tracks : mapping of str to track
        One entry per parameter to animate. A track is either a sequence of
        ``(time, value)`` pairs or a mapping ``{"keyframes": [(t, value), ...],
        "easing": "..."}``. The mapping may also carry ``"segments"``: a list
        of per-segment easing names, one per gap between consecutive
        keyframes, each ``None``/empty meaning "use the track default". The
        easing for a segment is its own override, else the track ``easing``,
        else the neutral linear curve. ``time`` is a fraction of the whole run
        in ``[0, 1]``.
    frames : int
        How many frames to return, before ``hold``. Must be >= 1.
    fps : float
        Recorded for the spec round-trip; it does not change the frames
        produced. The GIF writer's frame rate comes from the spec (or the
        CLI's ``--fps``), not from here.
    hold : int
        Extra copies of the finished frame to append, so a looping animation
        pauses on the result instead of restarting the instant it arrives.
    easing : str
        Top-level (playback) interpolation curve applied as a *final layer on
        top of* every track's keyframe program: the frame time is warped by
        this curve before each track's per-keyframe easing runs. One of
        ``linear`` (the default -- the identity, so it never interferes with
        keyframing), ``quadratic``, ``cubic``, ``sinusoidal``, ``exponential``,
        ``circular``. A ``name:mode`` suffix (``"cubic:out"``) selects an
        ease-out variant.

    Returns
    -------
    tuple of Design
        ``frames + hold`` of them. Numeric parameters interpolate
        component-wise; ``bool``, ``Literal`` and ``str`` parameters step at
        the next keyframe; integer parameters round and deduplicate, so two
        adjacent frames that round to the same value share one built
        :class:`Design`. An eased value a motif rejects falls back to the last
        frame that built, with a note in its metadata.

    Raises
    ------
    TypeError
        If the motif is not a dataclass, so there is nothing to vary by name.
    ValueError
        If a track names a parameter the motif does not have, a keyframe time
        is outside ``[0, 1]``, or the easing name is not recognized.

    Examples
    --------
    >>> from geomotif.animate import keyframes
    >>> from geomotif.motifs import Rose
    >>> len(keyframes(Rose(), {"n": [(0.0, 3), (1.0, 9)]}, frames=6))
    6
    """
    if frames < 1:
        raise ValueError(f"frames must be >= 1, got {frames}")
    if hold < 0:
        raise ValueError(f"hold must be >= 0, got {hold}")

    base_curve = _easing_curve(easing)
    normalized = {name: _normalize_track(track) for name, track in tracks.items()}
    # Typed as ``object`` for the same reason as ``_swept``: mypy cannot
    # intersect the motif protocol with the dataclass one, and written
    # against a motif type the narrowing below reads as unreachable.
    obj: object = motif
    if not (is_dataclass(obj) and not isinstance(obj, type)):
        raise TypeError(
            f"cannot keyframe {type(motif).__name__}: it is not a dataclass, "
            f"so it has no named parameters to vary. Build the frames yourself"
        )
    known = [field.name for field in fields(obj) if field.init]
    for name in normalized:
        if name not in known:
            raise ValueError(f"{type(motif).__name__} takes one of {known}, got {name!r}")

    # The motif's own build is the fallback for a frame whose interpolated
    # parameters the motif rejects before any frame has succeeded.
    base_fallback = motif.build()

    result: list[Design] = []
    prev_params: dict[str, object] | None = None
    prev_design: Design | None = None
    for i in range(frames):
        t = i / (frames - 1) if frames > 1 else 0.0
        params = {
            name: _value_at(t, kfs, curves, base_curve)
            for name, (kfs, curves) in normalized.items()
        }
        if prev_params is not None and params == prev_params and prev_design is not None:
            # Two adjacent frames that round to the same integers (or step to
            # the same discrete value) share one built Design, so a 60-frame
            # sweep of ``n`` from 3 to 9 holds 7 distinct frames, not 60
            # near-duplicates.
            result.append(prev_design)
            continue
        try:
            design = cast("SupportsBuild", replace(obj, **params)).build()
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            ZeroDivisionError,
            OverflowError,
            RecursionError,
        ):
            fallback = prev_design if prev_design is not None else base_fallback
            design = replace(
                fallback,
                meta=MappingProxyType({**fallback.meta, FALLBACK_KEY: True}),
            )
        result.append(design)
        prev_params = params
        prev_design = design

    if result:
        result.extend([result[-1]] * hold)
    # Touch fps so a reader knows it was not forgotten; the value lives in the
    # spec, not in the frames, and the GIF writer reads it from there.
    _ = fps
    return tuple(result)


def compose(
    motions: Iterable[Callable[[tuple[Design, ...]], tuple[Design, ...]]],
    frames: tuple[Design, ...],
) -> tuple[Design, ...]:
    """Chain motion post-passes onto a run of frames.

    :func:`keyframes` only animates motif parameters. The existing
    :func:`draw_on` and :func:`spin` operate on a built design and are applied
    as post-passes -- one frame at a time, in step with the timeline -- so a
    Hilbert curve can draw itself on while its ``depth`` sweeps from 3 to 6.
    :func:`draw_on_overlay` and :func:`spin_overlay` adapt them to a whole run
    of frames; this helper chains any number of such motions in order, so the
    CLI's ``--animation`` flag is a single spec rather than a tangle of nested
    flags.

    Parameters
    ----------
    motions : iterable of callables
        Each ``motion(frames) -> frames``, applied left to right.
    frames : tuple of Design
        The run to transform, typically the result of :func:`keyframes`.

    Returns
    -------
    tuple of Design
        The run after every motion has been applied in turn.
    """
    result = frames
    for motion in motions:
        result = motion(result)
    return result


def draw_on_overlay(
    *, trail: float | None = None
) -> Callable[[tuple[Design, ...]], tuple[Design, ...]]:
    """Return a motion that reveals each frame progressively, in step with the timeline.

    Frame ``i`` of ``n`` shows the first ``(i + 1) / n`` of that frame's arc
    length -- a pen drawing alongside the parameter sweep, so a Hilbert curve
    can grow from depth 3 to 6 while it draws itself on. ``trail`` passes
    straight through to the same per-path reveal :func:`draw_on` uses.
    """

    def apply(frames: tuple[Design, ...]) -> tuple[Design, ...]:
        n = len(frames)
        if n == 0:
            return frames
        return tuple(
            _revealed(frame, [path.length for path in frame.paths], (i + 1) / n, trail)
            for i, frame in enumerate(frames)
        )

    return apply


def spin_overlay(
    *, turns: float = 1.0, about: Point | None = None
) -> Callable[[tuple[Design, ...]], tuple[Design, ...]]:
    """Return a motion that turns each frame in step with the timeline.

    Frame ``i`` of ``n`` is rotated by ``turns * i / (n - 1)`` revolutions, so
    the *final* frame has completed exactly ``turns`` revolutions (fractions
    stay fractional: the last frame is a full ``turns`` turn on from the
    first, which is back at the starting orientation whenever ``turns`` is a
    whole number, and partway around otherwise). ``about`` defaults to each
    frame's own center, which is what keeps it on the canvas; give a point to
    rotate about a fixed one instead.
    """

    def apply(frames: tuple[Design, ...]) -> tuple[Design, ...]:
        n = len(frames)
        if n <= 1:
            return frames
        step = math.tau * turns / (n - 1)

        def center(frame: Design) -> Point:
            return frame.bounds.center if len(frame) else (0.0, 0.0)

        return tuple(
            frame.transformed(
                Affine.rotate(i * step, about=about if about is not None else center(frame))
            )
            for i, frame in enumerate(frames)
        )

    return apply


# --- keyframes internals -----------------------------------------------------


def _easing_curve(name: str) -> SpacingCurve:
    """Return the spacing curve a global or per-track easing name picks.

    A ``name:mode`` suffix (``"cubic:out"``) selects an ease-out variant of a
    modal curve; non-modal curves (``linear``) ignore a suffix.
    """
    head, _, mode = name.partition(":")
    factory = _EASINGS.get(head)
    if factory is None:
        raise ValueError(f"unknown easing {name!r}; try {sorted(_EASINGS)}")
    if mode:
        try:
            return factory(mode=mode)
        except TypeError as exc:
            raise ValueError(f"easing {head!r} takes no mode, got {mode!r}") from exc
    return factory()


def _normalize_track(
    track: object,
) -> tuple[list[tuple[float, object]], list[SpacingCurve]]:
    """Return a track as ``(sorted keyframes, per-segment easing curves)``.

    A track is either a sequence of ``(time, value)`` pairs (all segments use
    the neutral linear curve) or a mapping ``{"keyframes": [...], "easing":
    "..."}``. ``easing`` is the track's default and may be a single name (every
    segment) or a list of names, one per segment (the shape the explorer writes
    once a keyframe gets its own easing). ``segments`` is an optional list of
    per-segment names that override the track default, each ``None``/empty
    meaning "use the track default". Times are coerced to float and must lie in
    ``[0, 1]``. This is the *programmed* easing only -- the top-level playback
    easing is applied as a separate final layer in :func:`keyframes`.
    """
    if isinstance(track, Mapping):
        raw = track.get("keyframes", track.get("frames"))
        if raw is None:
            raise ValueError("a track mapping needs a 'keyframes' entry")
        track_easing = track.get("easing")
        segments_raw = track.get("segments")
    else:
        raw = track
        track_easing = None
        segments_raw = None
    try:
        kfs = [(float(t), v) for t, v in raw]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"a track's keyframes must be (time, value) pairs, got {track!r}") from exc
    if not kfs:
        raise ValueError("a track needs at least one keyframe")
    kfs.sort(key=lambda kv: kv[0])
    for t, _ in kfs:
        if not 0.0 <= t <= 1.0:
            raise ValueError(f"keyframe time {t} is out of [0, 1]")
    # A list `easing` is treated as the per-segment list (some recipes wrote the
    # segment names there); a string is the track default.
    if isinstance(track_easing, list):
        segments_raw = list(track_easing)
        track_easing = None
    n = len(kfs) - 1
    curves: list[SpacingCurve] = []
    for i in range(n):
        name = None
        if (
            segments_raw is not None
            and i < len(segments_raw)
            and isinstance(segments_raw[i], str)
            and segments_raw[i]
        ):
            name = segments_raw[i]
        elif isinstance(track_easing, str) and track_easing:
            name = track_easing
        curves.append(_easing_curve(name) if name else LinearSpacing())
    return kfs, curves


def _value_at(
    t: float,
    kfs: list[tuple[float, object]],
    curves: list[SpacingCurve],
    global_curve: SpacingCurve,
) -> object:
    """Return the value a track holds at raw time ``t``.

    The top-level playback easing is a *final layer* on top of every track's
    keyframe program: ``t`` is first warped by ``global_curve`` (the identity
    when linear, the default), and only then is the per-segment program
    evaluated. This is what makes the global and per-keyframe easings separate
    yet layered -- editing one never rewrites the other.

    Before the first keyframe the first value holds; at or after the last, the
    last. Discrete parameters (``bool``, ``str``, mismatched types) step rather
    than ease: each interior value holds from its own time until the next
    keyframe, and the *last* value takes over from the midpoint of the final
    segment. Numeric ones ease component-wise with each segment's own curve,
    integers rounded.
    """
    t = global_curve(t)
    if t <= kfs[0][0]:
        return kfs[0][1]
    if t >= kfs[-1][0]:
        return kfs[-1][1]
    if _is_discrete(kfs[0][1], kfs[-1][1]):
        # The last value would otherwise only ever be seen at the instant
        # t == its own time (usually 1.0), i.e. on the final frame alone. Pull
        # its onset back to the midpoint of the last segment so it gets a span.
        last_onset = (kfs[-2][0] + kfs[-1][0]) / 2 if len(kfs) >= 2 else kfs[-1][0]
        if t >= last_onset:
            return kfs[-1][1]
        held = kfs[0][1]
        for tk, vk in kfs[:-1]:
            if tk <= t:
                held = vk
            else:
                break
        return held
    for i, ((t0, v0), (t1, v1)) in enumerate(itertools.pairwise(kfs)):
        if t0 <= t <= t1:
            local = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            curve = curves[i] if i < len(curves) else LinearSpacing()
            return _lerp(v0, v1, curve(local))
    return kfs[-1][1]


def _is_discrete(v0: object, v1: object) -> bool:
    """Return whether two keyframe values should step rather than interpolate.

    ``bool`` and ``str`` step (so a ``Literal`` parameter snaps between its
    choices); so do mismatched *kinds* -- a :class:`Point` next to a
    ``Bounds``, or a design next to a bare number -- since there is no honest
    blend between them. Plain numbers interpolate even when their exact types
    differ: a dragged float keyframe (e.g. ``98.51``) easing toward an integer
    keyframe (``400``) must blend smoothly, not step. Everything else that is
    the same type -- value dataclasses, nested motifs -- interpolates.
    """
    if isinstance(v0, bool) or isinstance(v1, bool):
        return True
    if isinstance(v0, str) or isinstance(v1, str):
        return True
    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
        return False
    return type(v0) is not type(v1)


def _lerp(v0: object, v1: object, u: float) -> object:
    """Ease between two keyframe values, component-wise where they are composite.

    Integers round, so two adjacent frames that round to the same value are
    caught by the dedupe in :func:`keyframes` rather than here. A value
    dataclass (``Bounds``, ``IFSMap``, a nested motif) interpolates each of
    its own init fields, holding the discrete ones and easing the numeric ones
    -- which is what lets a nested motif's parameters move too.
    """
    if isinstance(v0, bool) or isinstance(v1, bool) or isinstance(v0, str) or isinstance(v1, str):
        return v0
    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
        result = v0 + (v1 - v0) * u
        if isinstance(v0, int) and isinstance(v1, int):
            return round(result)
        return result
    if isinstance(v0, tuple) and isinstance(v1, tuple):
        return tuple(_lerp(a, b, u) for a, b in zip(v0, v1, strict=True))
    if (
        dataclasses.is_dataclass(v0)
        and not isinstance(v0, type)
        and dataclasses.is_dataclass(v1)
        and not isinstance(v1, type)
        and type(v0) is type(v1)
    ):
        updates: dict[str, object] = {}
        for field in fields(v0):
            if not field.init:
                continue
            a, b = getattr(v0, field.name), getattr(v1, field.name)
            updates[field.name] = a if _is_discrete(a, b) else _lerp(a, b, u)
        return replace(v0, **updates)
    return v0
