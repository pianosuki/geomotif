"""Base for motifs that are an exact list of corners.

Distinct from :class:`~geomotif.ParametricMotif` for a reason that matters:
a polygon fed through a parametric ``position(u)`` is measured by evaluating
it at evenly spaced parameters, and a corner survives that only if a sample
happens to land exactly on it. A pentagon measured at 512 samples has none of
its five corners land on one, so every vertex comes out slightly cut. Listing
the corners instead keeps them exact and costs five points rather than five
hundred.

Anything whose shape is *decided by its vertices* belongs here: rectangles,
regular polygons, stars, the whole ``{n/k}`` family, and open polylines such
as the Theodorus spiral's chain of triangles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from ..core.motif import Motif
from ..core.registry import spec
from ..core.types import Design, Path

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = ["PolygonMotif"]


@dataclass(frozen=True, slots=True)
class PolygonMotif(Motif, ABC):
    """Base for a motif drawn as one or more exact corner sequences.

    Implement :meth:`outlines`; :meth:`build` turns each one into a
    :class:`~geomotif.Path`::

        @register("rectangle", family="primitive")
        @dataclass(frozen=True, slots=True)
        class Rectangle(PolygonMotif):
            width: float = 1.0
            height: float = 1.0

            def outlines(self) -> Iterable[Sequence[Point]]:
                w, h = self.width / 2.0, self.height / 2.0
                yield ((-w, -h), (w, -h), (w, h), (-w, h))

    :meth:`outlines` is plural because one shape is not always one loop: the
    star polygon ``{6/2}`` is two overlaid triangles, and drawing it as a
    single path would invent an edge between them that is not there.

    Notes
    -----
    Corners are emitted as given -- no deduplication, no collinear-point
    removal. A motif that wants a vertex repeated (to hold a pen, to mark a
    lattice site) is entitled to it, and guessing otherwise would silently
    change geometry the author chose.
    """

    #: Whether each outline closes back to its first corner. Set to ``False``
    #: for a motif that is an open chain rather than a loop.
    closed: ClassVar[bool] = True

    @abstractmethod
    def outlines(self) -> Iterable[Sequence[Point]]:
        """Return the corner sequences to draw, one per stroke. At least one."""

    @override
    def build(self) -> Design:
        paths: list[Path] = []
        for index, corners in enumerate(self.outlines()):
            points = tuple(corners)
            if len(points) < 2:
                raise ValueError(
                    f"{type(self).__name__}.outlines()[{index}] has {len(points)} "
                    f"corner(s); a stroke needs at least 2"
                )
            paths.append(Path(points, closed=self.closed))

        if not paths:
            raise ValueError(f"{type(self).__name__}.outlines() produced no outlines")
        return Design(tuple(paths), meta=spec(self))
