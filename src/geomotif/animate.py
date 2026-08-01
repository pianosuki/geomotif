"""Frames: the same design over time, or the same motif over a parameter.

A still image says what a design *is*. An animation says how it is made, which
for most of this catalogue is the more interesting half -- watching a Hilbert
curve fill its square, or a rose's petal count climb, tells you something the
finished picture cannot.

Each function here returns a plain tuple of :class:`~geomotif.Design` s, one
per frame, so they compose with everything else: transform them, restyle them,
export one as SVG, or hand the lot to
:func:`~geomotif.io.gif.save_gif`::

    from geomotif.animate import draw_on, spin, sweep
    from geomotif.io.gif import save_gif
    from geomotif.motifs import HilbertCurve, Rose

    save_gif(draw_on(HilbertCurve(depth=5).build(), frames=60), "hilbert.gif")
    save_gif(spin(Rose(n=5).build(), frames=48), "rose.gif")
    save_gif(sweep(Rose(), "n", range(2, 12)), "petals.gif")

Nothing here is expensive: a frame is the same geometry seen differently, not
the motif built again -- except in :func:`sweep`, where building it again is
precisely the point.
"""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass, replace
from typing import TYPE_CHECKING, cast

from .core.sampling import ArcTable
from .core.transform import Affine
from .core.types import Design, Path, select_styles

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .core.motif import SupportsBuild
    from .core.types import Point

__all__ = ["draw_on", "spin", "sweep"]


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
        Centre of rotation. Defaults to the middle of the design's bounds,
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
    centre = about if about is not None else (design.bounds.center if len(design) else (0.0, 0.0))
    step = math.tau * turns / frames
    turned = tuple(design.transformed(Affine.rotate(i * step, about=centre)) for i in range(frames))
    return tuple(list(turned) + [turned[-1]] * hold)


def sweep(motif: SupportsBuild, parameter: str, values: Iterable[object]) -> tuple[Design, ...]:
    """Return one frame per value of one of a motif's parameters.

    The motif is rebuilt for each value, which is the only way to animate a
    parameter -- and cheap enough, since the whole catalogue is built rather
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
