import math
from collections.abc import Iterable
from dataclasses import dataclass

import pytest

from geomotif import Bounds, Design, LatticeTiling, Path, Point, SubstitutionTiling

type Triangle = tuple[Point, Point, Point]


@dataclass(frozen=True, slots=True)
class SquareTiling(LatticeTiling):
    size: float = 10.0

    def basis(self) -> tuple[Point, Point]:
        return ((self.size, 0.0), (0.0, self.size))

    def cell(self) -> Design:
        s = self.size
        return Design((Path(((0.0, 0.0), (s, 0.0), (s, s), (0.0, s)), closed=True),))


@dataclass(frozen=True, slots=True)
class Sierpinski(SubstitutionTiling[Triangle]):
    size: float = 100.0

    def seed(self) -> Iterable[Triangle]:
        return (((0.0, 0.0), (self.size, 0.0), (self.size / 2, self.size * math.sqrt(3) / 2)),)

    def subdivide(self, tile: Triangle) -> Iterable[Triangle]:
        a, b, c = tile
        ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        bc = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        ca = ((c[0] + a[0]) / 2, (c[1] + a[1]) / 2)
        return ((a, ab, ca), (ab, b, bc), (ca, bc, c))

    def outline(self, tile: Triangle) -> Iterable[Path]:
        return (Path(tile, closed=True),)


def test_lattice_fills_its_region():
    design = SquareTiling(region=Bounds(0.0, 0.0, 30.0, 30.0)).build()
    assert design.bounds == Bounds(0.0, 0.0, 30.0, 30.0)


def test_lattice_clips_to_the_region_by_default():
    design = SquareTiling(size=10.0, region=Bounds(0.0, 0.0, 25.0, 25.0)).build()
    assert design.bounds.max_x == pytest.approx(25.0)


def test_unclipped_cells_overhang_but_stay_near():
    design = SquareTiling(size=10.0, region=Bounds(0.0, 0.0, 25.0, 25.0), clip=False).build()
    assert design.bounds.max_x == pytest.approx(30.0)
    # Whole cells, so every one of them is intact and closed.
    assert all(path.closed and len(path.points) == 4 for path in design.paths)


def test_unclipped_still_omits_cells_the_region_never_reaches():
    design = SquareTiling(size=10.0, region=Bounds(1.0, 1.0, 9.0, 9.0), clip=False).build()
    # The lattice search is a rectangle in lattice space and so overshoots;
    # only cells that genuinely reach the region may survive it.
    assert len(design.paths) == 1


def test_lattice_reaches_a_region_far_from_the_origin():
    design = SquareTiling(size=10.0, region=Bounds(500.0, 500.0, 530.0, 530.0)).build()
    assert design.bounds == Bounds(500.0, 500.0, 530.0, 530.0)


def test_a_skewed_basis_still_tiles():
    @dataclass(frozen=True, slots=True)
    class Rhombic(SquareTiling):
        def basis(self) -> tuple[Point, Point]:
            return ((self.size, 0.0), (self.size / 2, self.size))

    assert len(Rhombic(region=Bounds(0.0, 0.0, 30.0, 30.0)).build().paths) > 0


def test_parallel_basis_vectors_are_rejected():
    @dataclass(frozen=True, slots=True)
    class Degenerate(SquareTiling):
        def basis(self) -> tuple[Point, Point]:
            return ((1.0, 0.0), (2.0, 0.0))

    with pytest.raises(ValueError, match="parallel"):
        Degenerate(region=Bounds(0.0, 0.0, 10.0, 10.0)).build()


def test_an_empty_cell_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Blank(SquareTiling):
        def cell(self) -> Design:
            return Design()

    with pytest.raises(ValueError, match="no geometry"):
        Blank(region=Bounds(0.0, 0.0, 10.0, 10.0)).build()


def test_an_unreasonable_cell_count_is_refused():
    with pytest.raises(ValueError, match="limit"):
        SquareTiling(size=0.01, region=Bounds(0.0, 0.0, 1000.0, 1000.0)).build()


def test_lattice_meta_records_the_parameters():
    meta = SquareTiling(size=5.0, region=Bounds(0.0, 0.0, 10.0, 10.0)).build().meta
    assert meta["motif"] == "SquareTiling"
    assert meta["size"] == 5.0
    assert meta["region"] == Bounds(0.0, 0.0, 10.0, 10.0)


def test_substitution_tile_count_is_geometric():
    assert len(Sierpinski(depth=0).tiles()) == 1
    assert len(Sierpinski(depth=4).tiles()) == 3**4


def test_substitution_builds_one_outline_per_tile():
    design = Sierpinski(depth=3).build()
    assert len(design.paths) == 3**3
    assert all(path.closed for path in design.paths)


def test_substitution_stays_inside_its_seed():
    seeded = Sierpinski(depth=0).build().bounds
    deep = Sierpinski(depth=4).build().bounds
    assert deep.min_x >= seeded.min_x - 1e-9
    assert deep.max_x <= seeded.max_x + 1e-9


def test_negative_depth_is_an_error():
    with pytest.raises(ValueError, match="depth"):
        Sierpinski(depth=-1).tiles()


def test_an_empty_seed_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Seedless(Sierpinski):
        def seed(self) -> Iterable[Triangle]:
            return ()

    with pytest.raises(ValueError, match="no tiles"):
        Seedless().build()


def test_a_subdivision_that_deletes_everything_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Vanishing(Sierpinski):
        def subdivide(self, tile: Triangle) -> Iterable[Triangle]:
            return ()

    with pytest.raises(ValueError, match="emptied"):
        Vanishing(depth=1).tiles()


def test_an_outline_that_draws_nothing_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Invisible(Sierpinski):
        def outline(self, tile: Triangle) -> Iterable[Path]:
            return ()

    with pytest.raises(ValueError, match="no strokes"):
        Invisible(depth=1).build()


def test_a_runaway_subdivision_is_refused():
    @dataclass(frozen=True, slots=True)
    class Explosive(Sierpinski):
        def subdivide(self, tile: Triangle) -> Iterable[Triangle]:
            return (tile,) * 300_000

    with pytest.raises(ValueError, match="limit"):
        Explosive(depth=1).tiles()


def test_generate_resamples_a_tiling():
    assert len(Sierpinski(depth=2).generate(500)) == 500


def test_substitution_meta_records_the_parameters():
    meta = Sierpinski(depth=2).build().meta
    assert meta["motif"] == "Sierpinski"
    assert meta["depth"] == 2
