import math
import random
from collections import Counter

import pytest

from geomotif.core.types import Bounds
from geomotif.motifs.girih import (
    _INTERIOR,
    GIRIH_CONTACT,
    GIRIH_SHAPES,
    GirihTile,
    HexStarLattice,
    InterlockingDecagons,
    Rosette,
    RosetteTiling,
    TenfoldGirih,
    _decagon_cell,
    _rays,
    _walk,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
REGION = Bounds(-150.0, -150.0, 150.0, 150.0)


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
    n = len(points)
    return [math.dist(points[i], points[(i + 1) % n]) for i in range(n)]


def corner_angles(points):
    """Interior angles of a closed polygon, in degrees, reflex ones included."""
    n = len(points)
    turn = 1.0 if _ccw(points) else -1.0
    out = []
    for i in range(n):
        before, here, after = points[i - 1], points[i], points[(i + 1) % n]
        a = math.atan2(before[1] - here[1], before[0] - here[0])
        b = math.atan2(after[1] - here[1], after[0] - here[0])
        out.append(math.degrees((turn * (a - b)) % math.tau))
    return out


def _ccw(points):
    n = len(points)
    return (
        math.fsum(
            points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
            for i in range(n)
        )
        > 0.0
    )


def inside(polygon, point):
    x, y = point
    n = len(polygon)
    hit = False
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def covers_once(motif, *, samples=90, reach=4, seed=5):
    """Count how many translated tiles contain each of several random points.

    Sampled from inside the lattice cell rather than from a box about the
    origin, so the translations searched are certain to reach whichever tile
    owns each point.
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


# --- the five tiles ---------------------------------------------------------


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_every_girih_tile_has_the_same_side(shape):
    # The one property that makes the five a set rather than five shapes:
    # any tile can sit against any other, either way round.
    for length in sides(_walk(_INTERIOR[shape], 40.0)):
        assert length == pytest.approx(40.0)


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_every_girih_angle_is_a_multiple_of_thirty_six(shape):
    for angle in corner_angles(_walk(_INTERIOR[shape], 10.0)):
        assert angle % 36.0 == pytest.approx(0.0, abs=1e-6) or angle % 36.0 == pytest.approx(
            36.0, abs=1e-6
        )


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_the_walk_reproduces_the_angles_it_was_given(shape):
    # Offset by one corner: the walk turns by an angle *after* placing the
    # corner it belongs to, so the first angle in the table lands on the
    # second corner.
    angles = _INTERIOR[shape]
    assert corner_angles(_walk(angles, 3.0)) == pytest.approx(angles[-1:] + angles[:-1])


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_a_tile_is_its_outline_and_its_straps(shape):
    corners = len(_INTERIOR[shape])
    design = GirihTile(shape=shape).build()
    outline = design.paths[0]
    assert outline.closed
    assert len(outline.points) == corners
    assert len(design.paths) > 1


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_two_straps_leave_every_edge_midpoint(shape):
    # Two lines out of each midpoint is the rule; what stops them differs
    # from tile to tile, but how many start never does.
    tile = GirihTile(shape=shape, size=50.0)
    corners = tile.corners()
    midpoints = [
        ((corners[i][0] + corners[i - 1][0]) / 2.0, (corners[i][1] + corners[i - 1][1]) / 2.0)
        for i in range(len(corners))
    ]
    starts = []
    for path in tile.build().paths[1:]:
        starts.append(path.points[0])
        if len(path.points) == 3:
            starts.append(path.points[-1])  # a pair that stopped on each other
    assert len(starts) == 2 * len(corners)
    for middle in midpoints:
        assert sum(math.dist(middle, s) < 1e-9 for s in starts) == 2


@pytest.mark.parametrize("shape", GIRIH_SHAPES)
def test_the_straps_stay_inside_the_tile(shape):
    tile = GirihTile(shape=shape, size=50.0)
    corners = tile.corners()
    for path in tile.build().paths[1:]:
        for point in path.points[1:-1]:
            assert inside(corners, point)


def test_two_tiles_that_share_an_edge_hand_the_strap_straight_across():
    # The whole reason the pattern hides its own tiling: both tiles meet the
    # shared midpoint at the same angle from opposite sides, so two of the
    # four lines there are exactly opposite and read as one straight strap.
    decagon, bowtie = _decagon_cell(1.0)
    here = _rays(decagon, GIRIH_CONTACT)
    there = _rays(bowtie, GIRIH_CONTACT)
    shared = [
        (a, b)
        for origin_a, a in here
        for origin_b, b in there
        if math.dist(origin_a, origin_b) < 1e-9
    ]
    assert shared, "the decagon and the bowtie of one cell share an edge"
    opposite = [1 for a, b in shared if math.dist(a, (-b[0], -b[1])) < 1e-9]
    assert len(opposite) == len(shared) // 2


def test_a_steeper_contact_angle_drives_the_decagon_star_deeper_in():
    # Measured on the decagon alone: its middle is inside the tile, so "how
    # far in the straps reach" means something there. On the bowtie the
    # middle sits in the waist and the same measurement says nothing.
    def depth(contact):
        tile = GirihTile(size=40.0, contact=contact, outline=False)
        return min(math.dist((0.0, 0.0), p) for path in tile.build().paths for p in path.points)

    assert depth(math.radians(80.0)) < depth(math.radians(54.0)) < depth(math.radians(30.0))


def test_the_tile_can_be_drawn_without_its_straps_or_without_itself():
    assert len(GirihTile(strapwork=False).build().paths) == 1
    assert all(not path.closed for path in GirihTile(outline=False).build().paths)


def test_a_tile_that_would_draw_nothing_is_refused():
    with pytest.raises(ValueError, match="draw nothing"):
        GirihTile(strapwork=False, outline=False)


def test_turning_a_tile_turns_its_straps_with_it():
    upright = GirihTile(shape="pentagon", size=30.0).build()
    turned = GirihTile(shape="pentagon", size=30.0, rotation=math.pi / 2.0).build()
    for first, second in zip(upright.paths, turned.paths, strict=True):
        for (x, y), (u, v) in zip(first.points, second.points, strict=True):
            assert (u, v) == pytest.approx((-y, x))


# --- the tenfold tiling -----------------------------------------------------


def test_the_decagon_and_the_bowtie_fill_their_lattice_cell():
    # Areas adding to the determinant is what says the gap between decagons
    # is a bowtie and not merely bowtie-shaped.
    motif = TenfoldGirih(size=20.0, region=REGION)
    (ux, uy), (vx, vy) = motif.basis()
    tiles = math.fsum(area(path.points) for path in motif.cell().paths)
    assert tiles == pytest.approx(abs(ux * vy - uy * vx))


def test_the_tenfold_cell_is_one_decagon_and_one_bowtie():
    decagon, bowtie = _decagon_cell(7.0)
    assert len(decagon) == 10
    assert len(bowtie) == 6
    for shape in (decagon, bowtie):
        assert sides(shape) == pytest.approx([7.0] * len(shape))
    assert sorted(round(a) for a in corner_angles(bowtie)) == [72, 72, 72, 72, 216, 216]


def test_the_tenfold_tiling_covers_every_point_exactly_once():
    assert set(covers_once(TenfoldGirih(size=20.0, region=REGION))) == {1}


def test_the_decagons_touch_along_four_of_their_ten_edges():
    size = 5.0
    decagon, _ = _decagon_cell(size)
    (ux, uy), (vx, vy) = TenfoldGirih(size=size, region=REGION).basis()
    edges = [
        ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        for a, b in zip(decagon, decagon[1:] + decagon[:1], strict=True)
    ]
    shared = 0
    for dx, dy in ((ux, uy), (-ux, -uy), (vx, vy), (-vx, -vy)):
        for x, y in edges:
            shared += any(math.dist((x + dx, y + dy), m) < 1e-9 for m in edges)
    assert shared == 4
    assert len(edges) == 10


# --- the strapwork pattern --------------------------------------------------


def test_the_pattern_draws_lines_and_never_a_tile():
    design = InterlockingDecagons(size=24.0, region=REGION).build()
    assert design.paths
    assert all(not path.closed for path in design.paths)


def test_the_pattern_and_the_tiling_stand_on_the_same_lattice():
    assert (
        InterlockingDecagons(size=24.0, region=REGION).basis()
        == TenfoldGirih(size=24.0, region=REGION).basis()
    )


def test_a_contact_angle_outside_the_right_angle_is_refused():
    for bad in (0.0, math.pi / 2.0, -1.0, 3.0):
        with pytest.raises(ValueError, match="contact"):
            GirihTile(contact=bad)
        with pytest.raises(ValueError, match="contact"):
            InterlockingDecagons(contact=bad, region=REGION)


# --- the six-fold lattice ---------------------------------------------------


def test_the_stars_and_rhombi_fill_their_lattice_cell():
    motif = HexStarLattice(size=20.0, region=REGION)
    (ux, uy), (vx, vy) = motif.basis()
    tiles = math.fsum(area(path.points) for path in motif.cell().paths)
    assert tiles == pytest.approx(abs(ux * vy - uy * vx))


def test_the_cell_is_one_star_and_three_rhombi():
    paths = HexStarLattice(size=11.0, region=REGION).cell().paths
    assert len(paths) == 4
    star, *rhombi = (path.points for path in paths)
    assert len(star) == 12
    assert sides(star) == pytest.approx([11.0] * 12)
    for rhombus in rhombi:
        assert sides(rhombus) == pytest.approx([11.0] * 4)
        assert sorted(round(a) for a in corner_angles(rhombus)) == [60, 60, 120, 120]


def test_the_star_takes_two_thirds_of_the_plane():
    paths = HexStarLattice(size=9.0, region=REGION).cell().paths
    star = area(paths[0].points)
    total = math.fsum(area(path.points) for path in paths)
    assert star / total == pytest.approx(2.0 / 3.0)


def test_the_hex_star_lattice_covers_every_point_exactly_once():
    assert set(covers_once(HexStarLattice(size=20.0, region=REGION))) == {1}


# --- the rosette ------------------------------------------------------------


def test_the_nesting_ratio_of_a_pentagram_is_the_golden_ratio_squared():
    assert Rosette(points=5, sharpness=2).nesting == pytest.approx(1.0 / PHI**2)


def test_the_nesting_ratio_of_a_hexagram_is_one_over_root_three():
    assert Rosette(points=6, sharpness=2).nesting == pytest.approx(1.0 / math.sqrt(3.0))


@pytest.mark.parametrize("layers", [1, 3, 8])
def test_a_rosette_is_one_star_per_layer_plus_the_boss(layers):
    design = Rosette(layers=layers).build()
    assert len(design.paths) == layers + 1
    assert all(path.closed for path in design.paths)


def test_each_layer_reaches_exactly_the_valleys_of_the_one_outside_it():
    # The proportion the whole figure is built on, checked on the drawing.
    motif = Rosette(points=10, sharpness=3, layers=4, radius=100.0)
    for layer in range(motif.layers - 1):
        outer = motif.star(layer)
        inner = motif.star(layer + 1)
        valleys = {tuple(round(c, 6) for c in outer[i]) for i in range(1, len(outer), 2)}
        points = {tuple(round(c, 6) for c in inner[i]) for i in range(0, len(inner), 2)}
        assert points == valleys


def test_a_star_alternates_points_and_valleys():
    motif = Rosette(points=7, sharpness=3, radius=60.0)
    radii = [math.dist((0.0, 0.0), p) for p in motif.star(0)]
    assert radii[0::2] == pytest.approx([60.0] * 7)
    assert radii[1::2] == pytest.approx([60.0 * motif.nesting] * 7)


def test_the_rosette_is_the_size_it_says_and_sits_where_it_is_told():
    design = Rosette(radius=70.0, center=(20.0, -5.0)).build()
    assert max(math.dist((20.0, -5.0), p) for p in design) == pytest.approx(70.0)


def test_a_spikier_star_nests_faster():
    assert Rosette(points=12, sharpness=5).nesting < Rosette(points=12, sharpness=2).nesting


# --- rosettes on a lattice --------------------------------------------------


@pytest.mark.parametrize("lattice", ["hex", "square"])
def test_a_rosette_tiling_repeats_one_rosette(lattice):
    motif = RosetteTiling(radius=30.0, lattice=lattice, region=REGION)
    assert len(motif.cell().paths) == len(motif.unit().build().paths)


def test_neighbouring_rosettes_touch_point_to_point():
    motif = RosetteTiling(radius=30.0, region=REGION)
    (ux, uy), _ = motif.basis()
    assert math.hypot(ux, uy) == pytest.approx(60.0)


def test_the_two_lattices_differ():
    assert (
        RosetteTiling(region=REGION, lattice="hex").basis()
        != RosetteTiling(region=REGION, lattice="square").basis()
    )


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: GirihTile(size=0.0),
        lambda: GirihTile(shape="octagon"),  # type: ignore[arg-type]
        lambda: Rosette(radius=0.0),
        lambda: Rosette(points=4),
        lambda: Rosette(points=500),
        lambda: Rosette(points=8, sharpness=1),
        lambda: Rosette(points=8, sharpness=4),
        lambda: Rosette(layers=0),
        lambda: Rosette(layers=999),
        lambda: TenfoldGirih(size=-1.0, region=REGION),
        lambda: InterlockingDecagons(size=0.0, region=REGION),
        lambda: HexStarLattice(size=0.0, region=REGION),
        lambda: RosetteTiling(radius=0.0, region=REGION),
        lambda: RosetteTiling(lattice="triangular", region=REGION),  # type: ignore[arg-type]
        lambda: RosetteTiling(points=3, region=REGION),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_meta_records_the_parameters():
    design = TenfoldGirih(size=18.0, region=REGION).build()
    assert design.meta["motif"] == "girih.tenfold"
    assert design.meta["size"] == 18.0
