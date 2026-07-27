import itertools
import math
import random
from collections import Counter

import pytest

from geomotif.core.types import Bounds
from geomotif.motifs.tilings import (
    AmmannBeenker,
    CairoPentagonal,
    HerringboneTiling,
    HexagonalTiling,
    PenroseP2,
    PenroseP3,
    RhombilleTiling,
    RobinsonTriangle,
    SnubSquare,
    SquareTiling,
    TriangularTiling,
    TruchetTiling,
    TruncatedSquare,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
REGION = Bounds(-150.0, -150.0, 150.0, 150.0)

#: Every periodic tiling, with a size small enough that a unit cell is
#: quick to reason about and large enough that the region holds a few.
PERIODIC = [
    SquareTiling,
    TriangularTiling,
    HexagonalTiling,
    RhombilleTiling,
    CairoPentagonal,
    TruncatedSquare,
    SnubSquare,
    HerringboneTiling,
]


def area(points):
    """Shoelace area of a closed polygon, unsigned."""
    n = len(points)
    return (
        abs(
            math.fsum(
                points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                for i in range(n)
            )
        )
        / 2.0
    )


def sides(points):
    """Return each edge length of a closed polygon."""
    n = len(points)
    return [math.dist(points[i], points[(i + 1) % n]) for i in range(n)]


def corner_angles(points):
    """Return each interior angle of a closed polygon, in degrees."""
    n = len(points)
    out = []
    for i in range(n):
        before = points[i - 1]
        here = points[i]
        after = points[(i + 1) % n]
        a = math.atan2(before[1] - here[1], before[0] - here[0])
        b = math.atan2(after[1] - here[1], after[0] - here[0])
        out.append(math.degrees(abs((a - b + math.pi) % math.tau - math.pi)))
    return out


def inside(polygon, point):
    """Even-odd point-in-polygon."""
    x, y = point
    n = len(polygon)
    hit = False
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def covers_once(motif, *, samples=120, reach=6, seed=5):
    """Return how many translated tiles contain each of several random points.

    A tiling covers the plane exactly once, so every count must be 1. Points
    are drawn from inside the lattice cell itself rather than from a box
    around the origin, so that the translations searched are guaranteed to
    reach whichever tile owns each one.
    """
    cell = [path.points for path in motif.cell().paths]
    (ux, uy), (vx, vy) = motif.basis()
    rng = random.Random(seed)
    counts: Counter[int] = Counter()
    for _ in range(samples):
        a, b = rng.random(), rng.random()
        point = (a * ux + b * vx, a * uy + b * vy)
        found = 0
        for i in range(-reach, reach + 1):
            for j in range(-reach, reach + 1):
                shifted = (point[0] - i * ux - j * vx, point[1] - i * uy - j * vy)
                found += sum(inside(tile, shifted) for tile in cell)
        counts[found] += 1
    return counts


# --- the periodic ones ------------------------------------------------------


@pytest.mark.parametrize("cls", PERIODIC)
def test_the_cell_exactly_fills_its_own_lattice_cell(cls):
    # The sharpest cheap check there is: a tiling's tiles fill the lattice
    # cell with nothing left over and nothing doubled, so their areas add up
    # to the determinant of the basis. A wrong basis or a stray tile fails.
    motif = cls(region=REGION)
    (ux, uy), (vx, vy) = motif.basis()
    tiles = math.fsum(area(path.points) for path in motif.cell().paths)
    assert tiles == pytest.approx(abs(ux * vy - uy * vx))


@pytest.mark.parametrize("cls", PERIODIC)
def test_every_tile_is_a_closed_loop(cls):
    for path in cls(region=REGION).cell().paths:
        assert path.closed
        assert len(path.points) >= 3


@pytest.mark.parametrize("cls", [CairoPentagonal, SnubSquare, HerringboneTiling, RhombilleTiling])
def test_the_lattice_covers_the_plane_exactly_once(cls):
    # Equal areas would still allow a gap paid for by an overlap somewhere
    # else, so the four least obvious lattices are also sampled directly.
    assert set(covers_once(cls(region=REGION))) == {1}


@pytest.mark.parametrize("cls", PERIODIC)
def test_a_tiling_fills_the_region_it_is_given(cls):
    bounds = cls(region=REGION).build().bounds
    assert bounds.min_x == pytest.approx(REGION.min_x)
    assert bounds.max_y == pytest.approx(REGION.max_y)


def test_turning_off_clipping_keeps_whole_tiles():
    clipped = SquareTiling(size=40.0, region=REGION).build()
    whole = SquareTiling(size=40.0, region=REGION, clip=False).build()
    assert whole.bounds.width > clipped.bounds.width
    assert all(len(path.points) == 4 for path in whole.paths)


def test_a_bigger_tile_means_fewer_of_them():
    coarse = SquareTiling(size=80.0, region=REGION).build()
    fine = SquareTiling(size=20.0, region=REGION).build()
    assert len(fine.paths) > len(coarse.paths)


def test_the_triangular_cell_is_two_equilateral_triangles():
    for path in TriangularTiling(size=30.0, region=REGION).cell().paths:
        assert sides(path.points) == pytest.approx([30.0] * 3)


def test_the_hexagonal_cell_is_one_regular_hexagon():
    (path,) = HexagonalTiling(size=30.0, region=REGION).cell().paths
    assert sides(path.points) == pytest.approx([30.0] * 6)
    assert corner_angles(path.points) == pytest.approx([120.0] * 6)


def test_the_rhombille_cell_is_three_rhombi_meeting_in_the_middle():
    paths = RhombilleTiling(size=30.0, region=REGION).cell().paths
    assert len(paths) == 3
    for path in paths:
        assert sides(path.points) == pytest.approx([30.0] * 4)
        assert sorted(corner_angles(path.points)) == pytest.approx([60.0, 60.0, 120.0, 120.0])


def test_the_cairo_pentagon_has_four_equal_sides_and_two_right_angles():
    size = 25.0
    for path in CairoPentagonal(size=size, region=REGION).cell().paths:
        lengths = sorted(sides(path.points))
        assert lengths[1:] == pytest.approx([size] * 4)
        # The odd side out is sqrt(3) - 1 times the rest, which is what makes
        # the two right angles fit.
        assert lengths[0] == pytest.approx(size * (math.sqrt(3.0) - 1.0))
        assert sorted(corner_angles(path.points)) == pytest.approx(
            [90.0, 90.0, 120.0, 120.0, 120.0]
        )


def test_the_four_cairo_pentagons_are_one_pinwheel():
    # Each is the previous one turned a quarter turn about the corner they
    # share, which is the right angle four of them meet at.
    corners = [path.points for path in CairoPentagonal(size=25.0, region=REGION).cell().paths]
    assert all(pytest.approx((0.0, 0.0), abs=1e-9) == tile[1] for tile in corners)
    for first, second in itertools.pairwise(corners):
        for (x, y), (u, v) in zip(first, second, strict=True):
            assert (u, v) == pytest.approx((-y, x))


def test_the_truncated_square_cell_is_an_octagon_and_a_square():
    size = 25.0
    octagon, square = TruncatedSquare(size=size, region=REGION).cell().paths
    assert sides(octagon.points) == pytest.approx([size] * 8)
    assert corner_angles(octagon.points) == pytest.approx([135.0] * 8)
    assert sides(square.points) == pytest.approx([size] * 4)


def test_the_snub_square_cell_is_two_squares_and_four_triangles():
    size = 25.0
    shapes = Counter(len(path.points) for path in SnubSquare(size=size, region=REGION).cell().paths)
    assert shapes == {3: 4, 4: 2}
    for path in SnubSquare(size=size, region=REGION).cell().paths:
        assert sides(path.points) == pytest.approx([size] * len(path.points))


def test_the_two_snub_squares_are_thirty_degrees_apart():
    first, second = (
        path for path in SnubSquare(size=25.0, region=REGION).cell().paths if len(path.points) == 4
    )

    def lean(points):
        x, y = points[1][0] - points[0][0], points[1][1] - points[0][1]
        return math.degrees(math.atan2(y, x)) % 90.0

    assert abs(lean(first.points) - lean(second.points)) == pytest.approx(30.0)


@pytest.mark.parametrize(("length", "width"), [(60.0, 30.0), (50.0, 50.0), (90.0, 20.0)])
def test_the_herringbone_cell_is_one_brick_each_way(length, width):
    lying, standing = HerringboneTiling(length=length, width=width, region=REGION).cell().paths
    assert sorted(sides(lying.points)) == pytest.approx(sorted([length, length, width, width]))
    assert sorted(sides(standing.points)) == pytest.approx(sorted([length, length, width, width]))
    # One brick is the other turned ninety degrees, which is the pattern.
    assert lying.points[1][0] - lying.points[0][0] == pytest.approx(length)
    assert standing.points[2][1] - standing.points[1][1] == pytest.approx(length)


def test_herringbone_works_at_any_proportion():
    # Not only the usual two-to-one: the basis follows from the brick, so a
    # square brick and a nine-to-two one both tile.
    for length, width in ((45.0, 45.0), (90.0, 20.0), (33.0, 21.0)):
        motif = HerringboneTiling(length=length, width=width, region=REGION)
        assert set(covers_once(motif, samples=60)) == {1}


# --- Truchet ----------------------------------------------------------------


def test_a_truchet_tile_is_two_quarter_circles():
    motif = TruchetTiling(size=20.0, cols=4, rows=3)
    design = motif.build()
    assert len(design.paths) == 2 * 4 * 3
    for path in design.paths:
        # A quarter circle of radius half a cell: its ends are a chord of
        # r*sqrt(2) apart, and its length is a quarter of the circumference.
        assert math.dist(path.points[0], path.points[-1]) == pytest.approx(10.0 * math.sqrt(2.0))
        assert path.length == pytest.approx(math.tau * 10.0 / 4.0, rel=1e-3)


def test_the_arcs_meet_at_the_middle_of_every_cell_edge():
    size = 20.0
    motif = TruchetTiling(size=size, cols=3, rows=3)
    for path in motif.build().paths:
        for end in (path.points[0], path.points[-1]):
            # Every end sits half way along a cell edge, so exactly one of
            # its coordinates lands on the grid and the other in the middle.
            offsets = [(coordinate + size * 1.5) % size for coordinate in end]
            assert sorted(round(o, 6) for o in offsets) == pytest.approx([0.0, size / 2.0])


def test_the_same_seed_draws_the_same_tiles():
    first = TruchetTiling(seed=7, cols=5, rows=5).build()
    second = TruchetTiling(seed=7, cols=5, rows=5).build()
    assert [p.points for p in first.paths] == [p.points for p in second.paths]


def test_a_different_seed_draws_different_tiles():
    first = TruchetTiling(seed=1, cols=6, rows=6).build()
    second = TruchetTiling(seed=2, cols=6, rows=6).build()
    assert [p.points for p in first.paths] != [p.points for p in second.paths]


def test_the_patch_is_the_size_it_says():
    bounds = TruchetTiling(size=20.0, cols=5, rows=4, center=(3.0, -2.0)).build().bounds
    assert bounds.width == pytest.approx(100.0)
    assert bounds.height == pytest.approx(80.0)
    assert bounds.center == pytest.approx((3.0, -2.0))


# --- the Penrose pair -------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "counts"),
    [
        (PenroseP3, [10, 20, 50, 130, 340, 890]),
        (PenroseP2, [10, 30, 80, 210, 550, 1440]),
    ],
)
def test_the_substitution_grows_at_the_rate_the_rule_says(cls, counts):
    for depth, expected in enumerate(counts):
        assert len(cls(depth=depth).tiles()) == expected


@pytest.mark.parametrize("cls", [PenroseP2, PenroseP3])
@pytest.mark.parametrize("depth", [0, 2, 4])
def test_every_tile_is_one_of_the_two_robinson_triangles(cls, depth):
    for tile in cls(depth=depth, radius=100.0).tiles():
        legs = (abs(tile.apex - tile.first), abs(tile.apex - tile.second))
        base = abs(tile.first - tile.second)
        assert legs[0] == pytest.approx(legs[1])
        # The acute one's base is its leg over phi; the obtuse one's is phi
        # times it. Nothing else is a Robinson triangle.
        assert base / legs[0] == pytest.approx(1.0 / PHI if tile.kind == 0 else PHI)


@pytest.mark.parametrize("cls", [PenroseP2, PenroseP3])
def test_subdividing_never_changes_the_area_covered(cls):
    def covered(depth):
        return math.fsum(
            abs(((t.first - t.apex).conjugate() * (t.second - t.apex)).imag) / 2.0
            for t in cls(depth=depth, radius=100.0).tiles()
        )

    first = covered(0)
    assert covered(3) == pytest.approx(first)
    assert covered(5) == pytest.approx(first)


def test_every_rhomb_edge_is_the_same_length():
    # In P3 the legs are the rhombs' own edges, so at a given depth they are
    # all equal; the bases are the two diagonals, one a golden ratio shorter
    # than the edge and one that much longer.
    legs, bases = set(), set()
    for tile in PenroseP3(depth=4, radius=100.0).tiles():
        legs.add(round(abs(tile.apex - tile.first), 6))
        legs.add(round(abs(tile.apex - tile.second), 6))
        bases.add(round(abs(tile.first - tile.second), 6))
    assert len(legs) == 1
    assert len(bases) == 2
    short, long = sorted(bases)
    leg = legs.pop()
    assert leg / short == pytest.approx(PHI)
    assert long / leg == pytest.approx(PHI)


def test_kites_and_darts_are_built_from_two_lengths_only():
    # P2 divides its triangles the other way, so a leg of one is the base of
    # the other and only two lengths exist in the whole tiling -- which is
    # the classical statement that a kite and a dart share their edges.
    lengths = set()
    for tile in PenroseP2(depth=4, radius=100.0).tiles():
        for a, b in ((tile.apex, tile.first), (tile.first, tile.second), (tile.second, tile.apex)):
            lengths.add(round(abs(a - b), 6))
    assert len(lengths) == 2
    short, long = sorted(lengths)
    assert long / short == pytest.approx(PHI)


def test_the_rhombs_are_two_triangles_glued_along_their_base():
    # P3's whole point: every base edge is shared by exactly two triangles of
    # the same kind, and those two are mirror images -- which is to say, a
    # rhombus. Only the edge of the patch has a base with nobody on the far
    # side of it.
    tiles = PenroseP3(depth=4, radius=100.0).tiles()
    bases: dict[tuple[tuple[float, float], ...], list[RobinsonTriangle]] = {}
    for tile in tiles:
        key = tuple(sorted((_key(tile.first), _key(tile.second))))
        bases.setdefault(key, []).append(tile)
    whole = [owners for owners in bases.values() if len(owners) == 2]
    assert len(whole) * 2 + sum(len(o) for o in bases.values() if len(o) == 1) == len(tiles)
    for first, second in whole:
        assert first.kind == second.kind
        assert _reflect(first.apex, first.first, first.second) == pytest.approx(second.apex)


def test_the_kites_and_darts_are_two_triangles_glued_along_a_leg():
    # P2's whole point, and the one thing that distinguishes it from P3: the
    # seam runs down a leg instead of the base, so the pair makes a kite or a
    # dart rather than a rhombus.
    tiles = PenroseP2(depth=4, radius=100.0).tiles()
    seams: dict[tuple[tuple[float, float], ...], list[RobinsonTriangle]] = {}
    for tile in tiles:
        seams.setdefault(tuple(sorted((_key(tile.apex), _key(tile.first)))), []).append(tile)
    whole = [owners for owners in seams.values() if len(owners) == 2]
    lonely = sum(len(o) for o in seams.values() if len(o) == 1)
    assert len(whole) * 2 + lonely == len(tiles)
    # Only the boundary is left unpaired, which is a small fraction of it.
    assert lonely < len(tiles) // 10
    for first, second in whole:
        assert first.kind == second.kind
        assert _reflect(first.second, first.apex, first.first) == pytest.approx(second.second)


def test_a_whole_kite_or_dart_has_two_short_sides_and_two_long():
    tiles = PenroseP2(depth=4, radius=100.0).tiles()
    seams: dict[tuple[tuple[float, float], ...], list[RobinsonTriangle]] = {}
    for tile in tiles:
        seams.setdefault(tuple(sorted((_key(tile.apex), _key(tile.first)))), []).append(tile)
    shapes: Counter[int] = Counter()
    for owners in seams.values():
        if len(owners) != 2:
            continue
        first, second = owners
        quad = (first.apex, first.second, first.first, second.second)
        lengths = sorted(abs(quad[i] - quad[(i + 1) % 4]) for i in range(4))
        assert lengths[0] == pytest.approx(lengths[1])
        assert lengths[2] == pytest.approx(lengths[3])
        assert lengths[2] / lengths[0] == pytest.approx(PHI)
        shapes[first.kind] += 1
    # Both tiles are actually used; a rule that quietly lost one would still
    # tile, and would still be wrong.
    assert set(shapes) == {0, 1}


def test_each_stroke_is_two_edges_of_a_tile_and_never_the_seam():
    for cls in (PenroseP2, PenroseP3):
        for path in cls(depth=2, radius=100.0).build().paths:
            assert len(path.points) == 3
            assert not path.closed


def test_a_penrose_patch_stays_inside_its_radius():
    bounds = PenroseP3(depth=5, radius=90.0, center=(10.0, -5.0)).build().bounds
    assert bounds.max_x <= 100.0 + 1e-9
    assert bounds.min_y >= -95.0 - 1e-9


def _key(z):
    return (round(z.real, 6), round(z.imag, 6))


def _reflect(z, u, v):
    direction = v - u
    return u + direction * ((z - u) / direction).conjugate()


# --- Ammann-Beenker ---------------------------------------------------------


def test_every_ammann_beenker_tile_is_a_rhomb_of_the_same_side():
    size = 20.0
    for corners in AmmannBeenker(size=size, radius=90.0).rhombs():
        assert len(corners) == 4
        assert sides(corners) == pytest.approx([size] * 4)


def test_only_squares_and_forty_five_degree_rhombs_appear():
    angles: Counter[int] = Counter()
    for corners in AmmannBeenker(size=20.0, radius=90.0).rhombs():
        angles[round(min(corner_angles(corners)))] += 1
    assert set(angles) == {45, 90}
    # Both shapes are common; a bug that produced only one would still pass
    # the shape check above.
    assert min(angles.values()) > 10


def test_no_tile_is_placed_twice():
    tiles = AmmannBeenker(size=20.0, radius=90.0).rhombs()
    keys = Counter(tuple(sorted((round(x, 6), round(y, 6)) for x, y in t)) for t in tiles)
    assert max(keys.values()) == 1


def test_the_quasicrystal_covers_its_middle_exactly_once():
    tiles = AmmannBeenker(size=20.0, radius=120.0).rhombs()
    rng = random.Random(3)
    counts: Counter[int] = Counter()
    for _ in range(150):
        point = (rng.uniform(-60.0, 60.0), rng.uniform(-60.0, 60.0))
        counts[sum(inside(tile, point) for tile in tiles)] += 1
    assert set(counts) == {1}


def test_the_patch_grows_with_its_radius():
    small = AmmannBeenker(size=20.0, radius=60.0).rhombs()
    large = AmmannBeenker(size=20.0, radius=120.0).rhombs()
    assert len(large) > 3 * len(small)


def test_the_offsets_choose_a_different_tiling_of_the_same_family():
    default = AmmannBeenker(size=20.0, radius=90.0).rhombs()
    shifted = AmmannBeenker(size=20.0, radius=90.0, offsets=(0.1, 0.2, 0.3, -0.6)).rhombs()
    assert {tuple(sorted(t)) for t in default} != {tuple(sorted(t)) for t in shifted}
    for corners in shifted:
        assert sides(corners) == pytest.approx([20.0] * 4)


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: SquareTiling(size=0.0, region=REGION),
        lambda: TriangularTiling(size=-1.0, region=REGION),
        lambda: HexagonalTiling(size=0.0, region=REGION),
        lambda: RhombilleTiling(size=0.0, region=REGION),
        lambda: CairoPentagonal(size=0.0, region=REGION),
        lambda: TruncatedSquare(size=0.0, region=REGION),
        lambda: SnubSquare(size=0.0, region=REGION),
        lambda: HerringboneTiling(length=0.0, region=REGION),
        lambda: HerringboneTiling(width=0.0, region=REGION),
        lambda: TruchetTiling(size=0.0),
        lambda: TruchetTiling(cols=0),
        lambda: TruchetTiling(rows=0),
        lambda: PenroseP3(radius=0.0),
        lambda: PenroseP2(radius=-1.0),
        lambda: AmmannBeenker(size=0.0),
        lambda: AmmannBeenker(radius=0.0),
        lambda: AmmannBeenker(offsets=(0.5, 0.5)),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_a_negative_depth_is_refused():
    with pytest.raises(ValueError, match="depth"):
        PenroseP3(depth=-1).build()


def test_too_fine_a_multigrid_is_refused_rather_than_attempted():
    with pytest.raises(ValueError, match="crossings"):
        AmmannBeenker(size=0.01, radius=500.0).build()


def test_meta_records_the_parameters():
    design = SquareTiling(size=25.0, region=REGION).build()
    assert design.meta["motif"] == "tiling.square"
    assert design.meta["size"] == 25.0
    assert design.meta["region"] == REGION


def test_a_radius_smaller_than_one_tile_is_refused():
    with pytest.raises(ValueError, match="covered nothing"):
        AmmannBeenker(size=100.0, radius=1.0).build()
