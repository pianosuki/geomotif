"""Arc-length measurement and resampling, generalized to any polyline.

This is the engine that makes "equal spacing" mean equal *real* distance
rather than equal steps of some parameter. A curve is measured with a dense
polyline, the cumulative lengths are tabulated, and that table is inverted so
a requested fraction of the total length lands exactly where it should.

Because it operates on polylines rather than on any particular curve, every
motif in the library -- including fractals, tilings and string art, which
have no closed-form parametrization at all -- gets arc-length placement and
the whole spacing-curve family for free.
"""

from __future__ import annotations

import bisect
import itertools
import math
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from .spacing import coerce_spacing
from .types import Design, Path, select_styles

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from .motif import Distribution
    from .spacing import SpacingLike
    from .types import Point

__all__ = [
    "ArcTable",
    "Placement",
    "densify",
    "resample",
    "resample_path",
    "samples_for_turns",
]

#: Whether points are placed by real distance along a curve, or by even
#: steps through the curve's own parametrization.
type Placement = Literal["length", "parameter"]

# Density of the polyline used to measure arc length: enough for sub-pixel
# accuracy at typical canvas scales without noticeable cost.
_MIN_SAMPLES = 512
_SAMPLES_PER_TURN = 256


def samples_for_turns(turns: float) -> int:
    """Return a sensible densification count for a curve spanning ``turns``.

    Sample density has to scale with how much the curve actually bends, or a
    tightly wound motif is measured by a polyline that cuts every corner. This
    is the adaptive heuristic the spiral generator used, exposed so every
    motif can share one answer.
    """
    return max(_MIN_SAMPLES, int(_SAMPLES_PER_TURN * (abs(turns) + 1.0)))


def densify(
    fn: Callable[[float], Point],
    *,
    samples: int,
    domain: tuple[float, float] = (0.0, 1.0),
) -> tuple[Point, ...]:
    """Evaluate ``fn`` at evenly spaced parameters across ``domain``.

    Returns ``samples + 1`` points, so both endpoints of the domain are
    included and the result contains exactly ``samples`` segments.
    """
    if samples < 1:
        raise ValueError(f"samples must be >= 1, got {samples}")
    lo, hi = domain
    span = hi - lo
    return tuple(fn(lo + span * (j / samples)) for j in range(samples + 1))


def _vertices(points: Sequence[Point], *, closed: bool) -> tuple[Point, ...]:
    """Return the walk order, appending the wrap-around vertex when closed."""
    vertices = tuple(points)
    if closed and len(vertices) > 2:
        vertices = (*vertices, vertices[0])
    return vertices


class ArcTable:
    """Cumulative-length table over a polyline, with O(log n) inverse lookup.

    Building the table is O(n); every subsequent "where is the point at
    distance d?" query is a binary search plus one linear interpolation. That
    is what keeps resampling to thousands of points cheap.
    """

    __slots__ = ("_cumulative", "_vertices")

    def __init__(self, points: Sequence[Point], *, closed: bool = False) -> None:
        vertices = _vertices(points, closed=closed)
        if not vertices:
            raise ValueError("cannot measure an empty polyline")
        # Measured with math.dist even where numpy is installed, and
        # deliberately: an array conversion costs more than this single pass
        # over the vertices saves, and numpy's hypot disagrees with math.dist
        # in the last bit, which would move every point the table then places.
        cumulative = [0.0]
        for a, b in itertools.pairwise(vertices):
            cumulative.append(cumulative[-1] + math.dist(a, b))
        self._vertices = vertices
        self._cumulative = cumulative

    @property
    def total(self) -> float:
        """Total length of the polyline."""
        return self._cumulative[-1]

    @property
    def vertices(self) -> tuple[Point, ...]:
        """The measured points, including the closing vertex if closed."""
        return self._vertices

    def point_at(self, distance: float) -> Point:
        """Return the point ``distance`` along the polyline, clamped to its ends.

        A zero-length polyline (every vertex coincident) always returns its
        single location rather than dividing by zero -- the degenerate case
        should collapse gracefully, not explode.
        """
        cumulative = self._cumulative
        total = cumulative[-1]
        if total == 0.0:
            return self._vertices[0]
        if distance <= 0.0:
            return self._vertices[0]
        if distance >= total:
            return self._vertices[-1]

        j = bisect.bisect_left(cumulative, distance)
        if j <= 0:
            return self._vertices[0]
        segment = cumulative[j] - cumulative[j - 1]
        frac = 0.0 if segment == 0.0 else (distance - cumulative[j - 1]) / segment
        return _lerp(self._vertices[j - 1], self._vertices[j], frac)

    def point_at_fraction(self, s: float) -> Point:
        """Return the point at fraction ``s`` of the total length."""
        return self.point_at(s * self._cumulative[-1])

    def points_at(self, distances: Iterable[float]) -> tuple[Point, ...]:
        """Return the point at each distance, in the order they were asked for.

        Exactly what calling :meth:`point_at` on each in turn returns, and
        several times faster for the run of lookups that resampling actually
        performs. Those arrive in increasing order, so the segment holding one
        is at or after the segment that held the last, and the whole run walks
        the table once between them instead of binary-searching all of it every
        time.

        Order is exploited, never assumed: a distance that goes backwards seeks
        again, so this has no precondition to get wrong and no fast and slow
        version to keep in agreement.
        """
        cumulative = self._cumulative
        vertices = self._vertices
        total = cumulative[-1]
        first, final = vertices[0], vertices[-1]
        if total == 0.0:
            return tuple(first for _ in distances)

        limit = len(cumulative) - 1
        placed: list[Point] = []
        segment = 1
        for distance in distances:
            if distance <= 0.0:
                placed.append(first)
                continue
            if distance >= total:
                placed.append(final)
                continue
            if distance < cumulative[segment - 1]:
                segment = max(bisect.bisect_left(cumulative, distance), 1)
            while segment < limit and cumulative[segment] < distance:
                segment += 1
            start = cumulative[segment - 1]
            span = cumulative[segment] - start
            ax, ay = vertices[segment - 1]
            bx, by = vertices[segment]
            frac = 0.0 if span == 0.0 else (distance - start) / span
            placed.append((ax + (bx - ax) * frac, ay + (by - ay) * frac))
        return tuple(placed)

    def segment(self, start: float, end: float) -> tuple[Point, ...]:
        """Return the part of the polyline lying between two distances.

        The ends are exact -- interpolated where they fall inside a segment --
        and every vertex between them is kept as it was, so this is a *piece*
        of the polyline rather than a resampling of one. That is what an
        animation drawing itself on needs: the geometry so far, at the
        resolution it was built at.

        Distances outside the polyline clamp to its ends, and a range that
        collapses to a point returns that one point.
        """
        if end < start:
            start, end = end, start
        start = max(start, 0.0)
        end = min(end, self.total)
        if end <= start:
            return (self.point_at(start),)
        kept = [self.point_at(start)]
        kept.extend(
            vertex
            for distance, vertex in zip(self._cumulative, self._vertices, strict=True)
            if start < distance < end
        )
        kept.append(self.point_at(end))
        return tuple(kept)

    def points_at_fractions(self, fractions: Iterable[float]) -> tuple[Point, ...]:
        """Return the point at each fraction of the total length."""
        total = self._cumulative[-1]
        return self.points_at([s * total for s in fractions])


def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _point_at_index_fraction(vertices: Sequence[Point], s: float) -> Point:
    """Return the point at fraction ``s`` through the vertex *sequence*.

    This is parametric rather than arc-length placement: it advances evenly
    through the samples that describe the curve, so spacing compresses
    wherever the curve tightens.
    """
    last = len(vertices) - 1
    if last <= 0:
        return vertices[0]
    position = min(max(s, 0.0), 1.0) * last
    index = min(int(position), last - 1)
    return _lerp(vertices[index], vertices[index + 1], position - index)


def _fractions(count: int, *, closed: bool, spacing: SpacingLike | None) -> list[float]:
    """Return ``count`` eased fractions in [0, 1].

    Closed paths stop short of 1.0: the seam point is the start point, so
    including both would emit a duplicate and leave a visible double dot.
    """
    curve = coerce_spacing(spacing)
    divisor = count if closed else count - 1
    return [curve(i / divisor) for i in range(count)]


def resample_path(
    path: Path,
    count: int | None = None,
    *,
    step: float | None = None,
    spacing: SpacingLike | None = None,
    by: Placement = "length",
) -> Path:
    """Return ``path`` resampled to ``count`` points, or at a fixed ``step``.

    Parameters
    ----------
    path : Path
        The polyline to resample.
    count : int, optional
        Total number of points to return. Must be >= 2. Mutually exclusive
        with ``step``.
    step : float, optional
        Fixed real distance between consecutive points; the count falls out
        of the geometry. Any remainder shorter than ``step`` at the end of
        the path is dropped, so gaps are never uneven. This is the mode you
        want for plotter output and dot placement.
    spacing : SpacingCurve or callable, optional
        Distribution of points along the path. Defaults to equal spacing.
        Cannot be combined with ``step``, which is by definition uniform.
    by : {"length", "parameter"}, optional
        ``"length"`` (default) places points by real distance along the
        curve. ``"parameter"`` advances evenly through the path's own
        vertices instead, which compresses spacing wherever the curve
        tightens -- occasionally useful as a design effect. Only meaningful
        with ``count``.

    Returns
    -------
    Path
        The resampled path, preserving ``closed``.
    """
    if (count is None) == (step is None):
        raise ValueError("pass exactly one of count= or step=")
    if by not in ("length", "parameter"):
        raise ValueError(f"by must be 'length' or 'parameter', got {by!r}")
    if not path.points:
        raise ValueError("cannot resample an empty path")

    if step is not None:
        if step <= 0:
            raise ValueError(f"step must be > 0, got {step}")
        if spacing is not None:
            raise ValueError(
                "step= places points at a fixed distance, so it cannot be combined "
                "with spacing=; pass count= with spacing= instead"
            )
        if by != "length":
            raise ValueError("step= measures real distance, so by='parameter' is meaningless")
        table = ArcTable(path.points, closed=path.closed)
        if table.total == 0.0:
            return replace(path, points=(path.points[0],))
        howmany = int(table.total // step) + 1
        return replace(path, points=table.points_at([i * step for i in range(howmany)]))

    # The exclusivity check above already guarantees this, but it is not a
    # narrowing the type checker can follow, so restate it.
    if count is None:
        raise ValueError("pass exactly one of count= or step=")
    if count < 2:
        raise ValueError(f"count must be >= 2, got {count}")

    fractions = _fractions(count, closed=path.closed, spacing=spacing)

    if by == "parameter":
        vertices = _vertices(path.points, closed=path.closed)
        return replace(path, points=tuple(_point_at_index_fraction(vertices, s) for s in fractions))

    table = ArcTable(path.points, closed=path.closed)
    if table.total == 0.0:
        # Every vertex is the same place: emit that place, count times, rather
        # than failing. Degenerate input should degrade, not raise.
        return replace(path, points=(path.points[0],) * count)
    return replace(path, points=table.points_at_fractions(fractions))


def _allocate(count: int, lengths: Sequence[float]) -> list[int]:
    """Split ``count`` points across paths in proportion to their lengths.

    Uses largest-remainder apportionment so the parts sum to exactly ``count``
    -- asking for 500 points must yield 500 points, not 498 because three
    paths each lost a rounding fraction. Every path receives at least one
    point while the budget allows; if there are more paths than points, the
    longest paths win.
    """
    n = len(lengths)
    if count <= n:
        # Not enough to go around: one point each to the longest paths.
        ranked = sorted(range(n), key=lambda i: lengths[i], reverse=True)
        allocation = [0] * n
        for i in ranked[:count]:
            allocation[i] = 1
        return allocation

    total = math.fsum(lengths)
    if total == 0.0:
        base, extra = divmod(count, n)
        return [base + (1 if i < extra else 0) for i in range(n)]

    # Reserve one point per path, then apportion what remains by length.
    budget = count - n
    exact = [budget * length / total for length in lengths]
    allocation = [1 + int(value) for value in exact]
    remainder = count - sum(allocation)
    by_fraction = sorted(range(n), key=lambda i: exact[i] - int(exact[i]), reverse=True)
    for i in by_fraction[:remainder]:
        allocation[i] += 1
    return allocation


def resample(
    design: Design,
    count: int | None = None,
    *,
    step: float | None = None,
    spacing: SpacingLike | None = None,
    distribute: Distribution = "length",
    by: Placement = "length",
) -> Design:
    """Return ``design`` resampled across all of its paths.

    Loose points are passed through untouched: they are already exactly the
    points the motif meant, with no curve to redistribute them along.

    Parameters
    ----------
    design : Design
        The design to resample.
    count : int, optional
        Total number of points. How it is split across paths depends on
        ``distribute``. Mutually exclusive with ``step``.
    step : float, optional
        Fixed distance between consecutive points, applied independently to
        every path. ``distribute`` is irrelevant in this mode.
    spacing : SpacingCurve or callable, optional
        Distribution of points along each path.
    distribute : {"length", "even", "per_path"}, optional
        How a total ``count`` is spread over a multi-path design:

        * ``"length"`` (default) -- proportional to each path's arc length,
          giving uniform visual density across the whole design
        * ``"even"`` -- ``count // len(paths)`` on each path, giving uniform
          per-stroke detail regardless of stroke length
        * ``"per_path"`` -- ``count`` points on *each* path
    by : {"length", "parameter"}, optional
        Placement mode along each individual path; see :func:`resample_path`.

    Returns
    -------
    Design
        A new design with the same loose points and metadata.
    """
    if not design.paths:
        return design

    if step is not None:
        paths = tuple(
            resample_path(path, step=step, spacing=spacing, by=by) for path in design.paths
        )
        return Design(paths, design.points, design.meta)

    if count is None:
        raise ValueError("pass exactly one of count= or step=")
    # Checked here as well as in resample_path because the apportionment
    # below may legitimately hand a single point to a short path -- but a
    # whole design of one point is a caller mistake, not a design decision.
    if count < 2:
        raise ValueError(f"count must be >= 2, got {count}")

    match distribute:
        case "length":
            allocation = _allocate(count, [path.length for path in design.paths])
        case "even":
            per_path = count // len(design.paths)
            if per_path < 2:
                raise ValueError(
                    f"distribute='even' gives {per_path} point(s) per path for count={count} "
                    f"across {len(design.paths)} paths; raise count to at least "
                    f"{2 * len(design.paths)} or use distribute='length'"
                )
            allocation = [per_path] * len(design.paths)
        case "per_path":
            allocation = [count] * len(design.paths)
        case _:
            raise ValueError(
                f"distribute must be 'length', 'even' or 'per_path', got {distribute!r}"
            )

    out: list[Path] = []
    # Which source stroke each surviving one came from: a path allocated no
    # points is dropped entirely, and its style has to go with it rather than
    # slide onto its neighbour.
    kept: list[int] = []
    for index, (path, n) in enumerate(zip(design.paths, allocation, strict=True)):
        match n:
            case 0:
                continue
            case 1:
                out.append(replace(path, points=(path.points[0],)))
            case _:
                out.append(resample_path(path, n, spacing=spacing, by=by))
        kept.append(index)
    return Design(tuple(out), design.points, select_styles(design.meta, paths=kept))
