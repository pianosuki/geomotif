"""Bases for tilings: one cell repeated on a lattice, or tiles that subdivide.

The two cover the field between them. :class:`LatticeTiling` is the periodic
case -- square, triangular, hexagonal, rhombille, Cairo, herringbone, Truchet
-- where a single cell is stamped along two basis vectors. :class:`Substitution
Tiling` is the aperiodic case -- Penrose, Ammann-Beenker, girih -- where a
handful of seed tiles are replaced by smaller copies of themselves, over and
over.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..core.motif import Motif
from ..core.registry import spec
from ..core.transform import Affine, clip_to
from ..core.types import Design

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ..core.types import Bounds, Path, Point

__all__ = ["LatticeTiling", "SubstitutionTiling"]

# Ceilings on how much geometry a single motif may expand to. Both are far
# above any plausible design and far below anything that would hang the
# process: a mistyped basis vector or depth should raise, not swap.
_MAX_CELLS = 100_000
_MAX_TILES = 200_000


@dataclass(frozen=True, slots=True)
class LatticeTiling(Motif, ABC):
    """Base for a periodic tiling: one cell, repeated on two basis vectors.

    Implement :meth:`cell` (the geometry of one tile) and :meth:`basis` (the
    two translations that repeat it), and give the motif a :attr:`region` to
    fill::

        @register("tiling.square", family="tiling")
        @dataclass(frozen=True, slots=True)
        class SquareTiling(LatticeTiling):
            size: float = 10.0

            def basis(self) -> tuple[Point, Point]:
                return ((self.size, 0.0), (0.0, self.size))

            def cell(self) -> Design:
                s = self.size
                return Design((Path(((0, 0), (s, 0), (s, s), (0, s)), closed=True),))

    :meth:`basis` is a method rather than a field because for most tilings the
    vectors follow from the motif's own parameters, as above; a tiling that
    genuinely wants caller-supplied vectors can declare a field and return it.
    """

    #: The area to fill. Required: a periodic tiling is infinite otherwise.
    region: Bounds = field(kw_only=True)
    #: Trim strokes at the region border. Turn off to keep whole cells, and
    #: with them the outline of every tile that merely overlaps the edge.
    clip: bool = field(default=True, kw_only=True)

    @abstractmethod
    def basis(self) -> tuple[Point, Point]:
        """Return the two translation vectors that generate the lattice."""

    @abstractmethod
    def cell(self) -> Design:
        """Return the geometry of a single cell, at lattice origin."""

    @override
    def build(self) -> Design:
        cell = self.cell()
        if len(cell) == 0:
            raise ValueError(f"{type(self).__name__}.cell() produced no geometry")

        basis = self.basis()
        (ux, uy), (vx, vy) = basis
        paths: list[Path] = []
        points: list[Point] = []
        # Accumulated in flat lists rather than by repeatedly adding designs:
        # concatenating tuples inside the loop would make a large tiling
        # quadratic in its own cell count.
        for i, j in self._lattice_range(cell.bounds, basis):
            placed = cell.transformed(Affine.translate(i * ux + j * vx, i * uy + j * vy))
            paths.extend(placed.paths)
            points.extend(placed.points)

        design = Design(tuple(paths), tuple(points), meta=spec(self))
        return clip_to(design, self.region) if self.clip else design

    def _lattice_range(self, cell: Bounds, basis: tuple[Point, Point]) -> Iterable[tuple[int, int]]:
        """Yield every lattice index whose translated cell overlaps the region.

        The candidates come from mapping the region -- grown by the cell's own
        reach, so that a cell straddling the border still counts -- back
        through the inverse of the basis. That is a rectangle in lattice
        space and therefore a superset, so each candidate is then checked
        against the region for real: a caller who turned :attr:`clip` off
        still gets only the cells that are actually there.
        """
        (ux, uy), (vx, vy) = basis
        determinant = ux * vy - uy * vx
        if determinant == 0.0:
            raise ValueError(
                f"{type(self).__name__}.basis() vectors {(ux, uy)} and {(vx, vy)} are "
                f"parallel, so they generate a line rather than a lattice"
            )

        # A cell whose geometry sits far from the lattice origin still reaches
        # the region from a long way off, so the pad is measured from the
        # origin to the cell's furthest side, not from the cell's own extent.
        reach = self.region.padded(
            max(abs(cell.min_x), abs(cell.max_x), abs(cell.min_y), abs(cell.max_y))
        )
        corners = (
            (reach.min_x, reach.min_y),
            (reach.max_x, reach.min_y),
            (reach.min_x, reach.max_y),
            (reach.max_x, reach.max_y),
        )
        # Inverse of the 2x2 basis matrix, applied to each corner: where the
        # region's corners land in lattice coordinates.
        coordinates = [
            ((x * vy - y * vx) / determinant, (y * ux - x * uy) / determinant) for x, y in corners
        ]
        i_lo, i_hi = min(c[0] for c in coordinates), max(c[0] for c in coordinates)
        j_lo, j_hi = min(c[1] for c in coordinates), max(c[1] for c in coordinates)

        i_range = range(math.floor(i_lo), math.ceil(i_hi) + 1)
        j_range = range(math.floor(j_lo), math.ceil(j_hi) + 1)
        total = len(i_range) * len(j_range)
        if total > _MAX_CELLS:
            raise ValueError(
                f"{type(self).__name__} would fill its region with {total} cells "
                f"(limit {_MAX_CELLS}); use a larger basis or a smaller region"
            )

        region = self.region
        for i in i_range:
            for j in j_range:
                dx, dy = i * ux + j * vx, i * uy + j * vy
                if (
                    cell.min_x + dx > region.max_x
                    or cell.max_x + dx < region.min_x
                    or cell.min_y + dy > region.max_y
                    or cell.max_y + dy < region.min_y
                ):
                    continue
                yield i, j


@dataclass(frozen=True, slots=True)
class SubstitutionTiling[TileT](Motif, ABC):
    """Base for an aperiodic tiling: seed tiles, subdivided :attr:`depth` times.

    The tile type is yours -- a dataclass of three vertices, a rhomb with an
    orientation, whatever the substitution rule needs. The base only ever
    passes tiles back to your own methods, so it never has to know.

    Implement :meth:`seed` (the starting tiles), :meth:`subdivide` (one tile
    to its replacements) and :meth:`outline` (a tile to the strokes that draw
    it).

    Notes
    -----
    Tile count grows geometrically -- a rule with three replacements reaches
    a hundred thousand tiles by depth eleven -- so the expansion is capped and
    raises rather than exhausting memory.

    Shared edges are drawn once per tile that owns them, so a plotter will
    trace most edges twice. Deduplicating them means comparing floating-point
    vertices for equality, which is a judgement call about tolerance the base
    should not be making for you.
    """

    #: Number of subdivision rounds.
    depth: int = field(default=4, kw_only=True)

    @abstractmethod
    def seed(self) -> Iterable[TileT]:
        """Return the tiles the subdivision starts from."""

    @abstractmethod
    def subdivide(self, tile: TileT) -> Iterable[TileT]:
        """Return the tiles that replace ``tile`` in the next round."""

    @abstractmethod
    def outline(self, tile: TileT) -> Iterable[Path]:
        """Return the strokes that draw ``tile``."""

    def tiles(self) -> tuple[TileT, ...]:
        """Return the seed tiles subdivided :attr:`depth` times.

        Exposed separately from :meth:`build` because the tiles themselves are
        often what you want -- to count them, to check a substitution rule
        preserves area, or to colour them by type.
        """
        if self.depth < 0:
            raise ValueError(f"depth must be >= 0, got {self.depth}")

        current = tuple(self.seed())
        if not current:
            raise ValueError(f"{type(self).__name__}.seed() returned no tiles")

        for round_number in range(self.depth):
            current = tuple(child for tile in current for child in self.subdivide(tile))
            if not current:
                raise ValueError(
                    f"{type(self).__name__}.subdivide() emptied the tiling in round "
                    f"{round_number + 1}: every tile must be replaced by at least one tile"
                )
            if len(current) > _MAX_TILES:
                raise ValueError(
                    f"{type(self).__name__} expanded to {len(current)} tiles after "
                    f"{round_number + 1} of {self.depth} rounds (limit {_MAX_TILES}); "
                    f"use a smaller depth"
                )
        return current

    @override
    def build(self) -> Design:
        paths = tuple(path for tile in self.tiles() for path in self.outline(tile))
        if not paths:
            raise ValueError(f"{type(self).__name__}.outline() produced no strokes")
        return Design(paths, meta=spec(self))
