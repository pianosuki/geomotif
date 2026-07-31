"""The geometric value types every motif produces and every tool consumes.

A :class:`Design` is the universal currency of this library: zero or more
stroked :class:`Path` polylines plus zero or more loose :class:`Point` s that
carry no stroke (dot art, scatter fields, lattice sites). Motifs build them,
transforms rewrite them, exporters write them out.

Everything here is immutable, so designs compose without aliasing surprises
and can be shared freely between threads. Operations that would mutate return
a new value instead -- :meth:`Design.transformed`, :meth:`Design.resampled`,
:meth:`Design.fit`.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from .motif import Distribution
    from .spacing import SpacingLike
    from .transform import Affine

__all__ = [
    "EMPTY_META",
    "PATH_STYLE_KEY",
    "POINT_STYLE_KEY",
    "Bounds",
    "Design",
    "Path",
    "Point",
    "select_styles",
]

type Point = tuple[float, float]

#: Shared read-only default for :attr:`Design.meta`, so the common case of
#: "no metadata" costs no allocation and cannot be mutated by a caller.
EMPTY_META: Mapping[str, object] = MappingProxyType({})

#: Reserved :attr:`Design.meta` keys holding one style per stroke and one per
#: loose point -- see :mod:`geomotif.core.style` for what goes in them. The
#: mechanics live here, rather than there, because the operations that reshape
#: a design have to keep the lists lined up with the geometry, and they are
#: defined in this module.
#:
#: Hyphenated deliberately: no Python parameter can be named ``path-style``, so
#: a motif's own parameters can never collide with these where
#: :func:`~geomotif.core.registry.spec` lays the two side by side in ``meta``.
PATH_STYLE_KEY = "path-style"
POINT_STYLE_KEY = "point-style"


def _clean_points(points: Iterable[Point], *, owner: str) -> tuple[Point, ...]:
    """Coerce an iterable of pairs to a tuple of finite float pairs.

    Rejecting NaN and infinity here, at construction, is deliberate: a single
    bad coordinate otherwise propagates silently through bounds, arc length
    and export, and surfaces as an unreadable SVG or an empty plot much later.
    """
    cleaned: list[Point] = []
    for index, point in enumerate(points):
        try:
            x, y = point
        except (TypeError, ValueError):
            raise TypeError(f"{owner}[{index}] must be an (x, y) pair, got {point!r}") from None
        fx, fy = float(x), float(y)
        if not math.isfinite(fx) or not math.isfinite(fy):
            raise ValueError(f"{owner}[{index}] must be finite, got ({fx}, {fy})")
        cleaned.append((fx, fy))
    return tuple(cleaned)


def select_styles(
    meta: Mapping[str, object],
    *,
    paths: Sequence[int] | None = None,
    points: Sequence[int] | None = None,
) -> Mapping[str, object]:
    """Return ``meta`` with its style lists following reshaped geometry.

    Any operator that drops, splits or reorders a design's strokes has to say
    so, or the metadata it carries over lands on the wrong geometry -- a
    clipped design whose colours have all shifted by one. ``paths`` and
    ``points`` give the *source* index of every element the result keeps, in
    the order it keeps them, which is something every such operator knows.

    Parameters
    ----------
    meta : mapping
        The metadata to rewrite. Returned unchanged, and uncopied, when it
        carries no styles at all -- which is the usual case.
    paths, points : sequence of int, optional
        Source indices, one per element of the result. ``None`` leaves that
        list alone, which is the right answer for an operation that reshaped
        only the other one.

    Returns
    -------
    Mapping[str, object]
        Read-only, ready to hand to :class:`Design`.
    """
    if PATH_STYLE_KEY not in meta and POINT_STYLE_KEY not in meta:
        return meta
    updated = dict(meta)
    for key, indices in ((PATH_STYLE_KEY, paths), (POINT_STYLE_KEY, points)):
        stored = _style_list(meta, key)
        if indices is None or stored is None:
            continue
        updated[key] = tuple(
            stored[index] if 0 <= index < len(stored) else None for index in indices
        )
    return MappingProxyType(updated)


def _style_list(meta: Mapping[str, object], key: str) -> tuple[object, ...] | None:
    """Return the styles stored under ``key``, or ``None`` if there are none.

    Typed as ``object`` rather than as the style class: this module is the one
    every other imports, including the one that defines what a style *is*, so
    it knows only that the value is a tuple as long as the geometry.
    """
    stored = meta.get(key)
    return stored if isinstance(stored, tuple) else None


def _padded_styles(meta: Mapping[str, object], key: str, count: int) -> tuple[object, ...]:
    """Return the styles under ``key`` stretched or trimmed to exactly ``count``."""
    stored = _style_list(meta, key) or ()
    if len(stored) == count:
        return stored
    return (*stored[:count], *(None,) * max(0, count - len(stored)))


def _concatenated_styles(left: Design, right: Design) -> dict[str, tuple[object, ...]]:
    """Lay two designs' style lists end to end, so overlaying keeps both.

    Without this the right-biased ``meta`` merge would hand the whole result
    the second design's styles, and ``layer(red, blue)`` would come out
    entirely blue -- which is the one thing a layer exists to prevent.
    """
    merged: dict[str, tuple[object, ...]] = {}
    for key, sizes in (
        (PATH_STYLE_KEY, (len(left.paths), len(right.paths))),
        (POINT_STYLE_KEY, (len(left.points), len(right.points))),
    ):
        if key not in left.meta and key not in right.meta:
            continue
        merged[key] = _padded_styles(left.meta, key, sizes[0]) + _padded_styles(
            right.meta, key, sizes[1]
        )
    return merged


@dataclass(frozen=True, slots=True)
class Bounds:
    """An axis-aligned rectangle enclosing some geometry."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.min_x > self.max_x or self.min_y > self.max_y:
            raise ValueError(
                "bounds must have min <= max, got "
                f"x[{self.min_x}, {self.max_x}] y[{self.min_y}, {self.max_y}]"
            )

    @classmethod
    def from_points(cls, points: Iterable[Point]) -> Bounds:
        """Return the tightest bounds containing every point.

        Raises
        ------
        ValueError
            If ``points`` is empty; an empty set has no meaningful extent,
            and returning a zero rectangle at the origin would be a lie that
            quietly skews every later ``fit`` and ``clip``.
        """
        xs: list[float] = []
        ys: list[float] = []
        for x, y in points:
            xs.append(x)
            ys.append(y)
        if not xs:
            raise ValueError("cannot compute bounds of an empty point set")
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        """Horizontal extent."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Vertical extent."""
        return self.max_y - self.min_y

    @property
    def center(self) -> Point:
        """Midpoint of the rectangle."""
        return ((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    def __contains__(self, point: Point) -> bool:
        x, y = point
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def union(self, other: Bounds) -> Bounds:
        """Return the smallest bounds containing both rectangles."""
        return Bounds(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    def padded(self, amount: float) -> Bounds:
        """Return these bounds grown by ``amount`` on every side."""
        return Bounds(
            self.min_x - amount,
            self.min_y - amount,
            self.max_x + amount,
            self.max_y + amount,
        )


@dataclass(frozen=True, slots=True)
class Path:
    """One continuous polyline.

    ``closed`` means the last point connects back to the first. The closing
    segment is implied, never stored, so a closed path's points are never
    duplicated at the seam.

    Points are normalized to a tuple of finite ``(float, float)`` pairs at
    construction, so any sequence of pairs may be passed in.
    """

    points: tuple[Point, ...]
    closed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", _clean_points(self.points, owner="points"))

    def __iter__(self) -> Iterator[Point]:
        return iter(self.points)

    def __len__(self) -> int:
        return len(self.points)

    @property
    def length(self) -> float:
        """Total polyline length, including the closing segment if closed.

        A two-point "closed" path is treated as a single open segment: its
        closing segment retraces the one it already has, and counting that
        twice reports a length no plotter would ever draw.
        """
        total = math.fsum(math.dist(a, b) for a, b in itertools.pairwise(self.points))
        if self.closed and len(self.points) > 2:
            total += math.dist(self.points[-1], self.points[0])
        return total

    @property
    def bounds(self) -> Bounds:
        """Tightest rectangle containing every vertex."""
        return Bounds.from_points(self.points)


@dataclass(frozen=True, slots=True)
class Design:
    """The universal result: zero or more strokes plus zero or more loose points.

    ``meta`` carries the motif name and its resolved parameters (including any
    resolved random seed), which is what makes a design reproducible,
    serializable to a spec file, and self-labelling in the gallery.
    """

    paths: tuple[Path, ...] = ()
    points: tuple[Point, ...] = ()
    meta: Mapping[str, object] = EMPTY_META

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(self.paths))
        object.__setattr__(self, "points", _clean_points(self.points, owner="points"))

    def __iter__(self) -> Iterator[Point]:
        """Iterate every point: each path in order, then the loose points."""
        for path in self.paths:
            yield from path.points
        yield from self.points

    def __len__(self) -> int:
        return sum(len(path) for path in self.paths) + len(self.points)

    def __add__(self, other: Design) -> Design:
        """Overlay two designs, concatenating their paths and loose points.

        ``meta`` is merged right-biased. A composed design no longer describes
        a single motif, so composers that care about reproducibility should
        set their own ``meta`` on the result rather than trust the merge.
        Styles are the exception: they describe individual strokes rather than
        the design as a whole, so the two lists are laid end to end instead.
        """
        if not isinstance(other, Design):
            return NotImplemented
        if not self.meta:
            meta = other.meta
        elif not other.meta:
            meta = self.meta
        else:
            meta = MappingProxyType({**self.meta, **other.meta})
        styles = _concatenated_styles(self, other)
        if styles:
            meta = MappingProxyType({**meta, **styles})
        return Design(self.paths + other.paths, self.points + other.points, meta)

    @property
    def bounds(self) -> Bounds:
        """Bounds over every point in every path plus the loose points."""
        return Bounds.from_points(self)

    def transformed(self, m: Affine) -> Design:
        """Return this design with ``m`` applied to every point."""
        paths = tuple(replace(path, points=tuple(m(p) for p in path.points)) for path in self.paths)
        return Design(paths, tuple(m(p) for p in self.points), self.meta)

    def flipped_y(self) -> Design:
        """Return this design mirrored about the x-axis.

        The y-up/y-down question is a property of the target coordinate space,
        not of any motif, which is why it lives here rather than as a flag on
        every builder.
        """
        paths = tuple(
            replace(path, points=tuple((x, -y) for x, y in path.points)) for path in self.paths
        )
        return Design(paths, tuple((x, -y) for x, y in self.points), self.meta)

    def resampled(
        self,
        count: int | None = None,
        *,
        step: float | None = None,
        spacing: SpacingLike | None = None,
        distribute: Distribution = "length",
    ) -> Design:
        """Return this design resampled to ``count`` points (or a fixed ``step``).

        See :func:`geomotif.core.sampling.resample` for the full contract.
        """
        # Imported here rather than at module scope: the sampling engine is
        # built on top of these types, so a top-level import would be circular.
        from .sampling import resample

        return resample(self, count, step=step, spacing=spacing, distribute=distribute)

    def fit(
        self,
        width: float,
        height: float,
        *,
        padding: float = 0.0,
        flip_y: bool = False,
    ) -> Design:
        """Return this design scaled and centered inside a ``width`` x ``height`` canvas.

        Scaling is uniform, so the design is never distorted; it is centered
        in whichever axis has slack. The result sits in ``[0, width] x
        [0, height]``, with ``flip_y=True`` producing y-down (screen/SVG)
        coordinates.

        Parameters
        ----------
        width, height : float
            Canvas size. Both must be positive.
        padding : float, optional
            Margin reserved on all four sides.
        flip_y : bool, optional
            Mirror vertically so y increases downward.

        Returns
        -------
        Design
            The fitted design. A design with no extent in either axis (a
            single point, or a perfectly vertical line) is translated but
            never scaled, since there is no finite scale that fills a canvas
            from nothing.
        """
        if width <= 0 or height <= 0:
            raise ValueError(f"width and height must be > 0, got {width}x{height}")
        if padding < 0:
            raise ValueError(f"padding must be >= 0, got {padding}")
        inner_w = width - 2.0 * padding
        inner_h = height - 2.0 * padding
        if inner_w <= 0 or inner_h <= 0:
            raise ValueError(f"padding {padding} leaves no room inside {width}x{height}")

        b = self.bounds
        scales = [inner_w / b.width] if b.width > 0 else []
        if b.height > 0:
            scales.append(inner_h / b.height)
        scale = min(scales) if scales else 1.0

        offset_x = padding + (inner_w - b.width * scale) / 2.0
        offset_y = padding + (inner_h - b.height * scale) / 2.0

        def place(p: Point) -> Point:
            x = offset_x + (p[0] - b.min_x) * scale
            y = offset_y + (p[1] - b.min_y) * scale
            return (x, height - y) if flip_y else (x, y)

        paths = tuple(
            replace(path, points=tuple(place(p) for p in path.points)) for path in self.paths
        )
        return Design(paths, tuple(place(p) for p in self.points), self.meta)
