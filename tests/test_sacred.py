import itertools
import math
from itertools import combinations

import pytest

from geomotif.motifs.sacred import (
    FlowerOfLife,
    FruitOfLife,
    GoldenRectangle,
    MetatronsCube,
    SeedOfLife,
    SriYantra,
    VesicaPiscis,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0


# --- vesica -----------------------------------------------------------------


def test_each_circle_passes_through_the_other_s_middle():
    motif = VesicaPiscis(radius=90.0)
    left, right = motif.centers()
    assert math.dist(left, right) == pytest.approx(90.0)


def test_the_almond_is_root_three_times_as_tall_as_it_is_wide():
    # The one fact the whole module is built on: the vesica hands you sqrt(3)
    # without measuring anything.
    bounds = VesicaPiscis(radius=80.0, lens=True).lens_path().bounds
    assert bounds.height / bounds.width == pytest.approx(math.sqrt(3.0))
    assert bounds.width == pytest.approx(80.0)


def test_every_point_of_the_almond_lies_on_one_of_the_two_circles():
    motif = VesicaPiscis(radius=70.0, center=(5.0, -3.0), lens=True)
    left, right = motif.centers()
    for point in motif.lens_path().points:
        # On one circle or the other, not necessarily the nearer: the far
        # circle's own middle lies on this arc, at distance zero.
        assert any(math.dist(point, c) == pytest.approx(70.0) for c in (left, right))


def test_the_lens_is_off_by_default():
    assert len(VesicaPiscis().build().paths) == 2
    assert len(VesicaPiscis(lens=True).build().paths) == 3


# --- seed of life -----------------------------------------------------------


def test_the_seed_is_seven_circles_a_radius_apart():
    motif = SeedOfLife(radius=50.0)
    middle, *outer = motif.centers()
    assert len(outer) == 6
    assert all(math.dist(middle, point) == pytest.approx(50.0) for point in outer)
    # Neighbouring outer circles pass through each other's middles too.
    for a, b in zip(outer, outer[1:] + outer[:1], strict=True):
        assert math.dist(a, b) == pytest.approx(50.0)


def test_rotation_turns_the_whole_seed():
    upright = SeedOfLife(rotation=0.0).centers()
    turned = SeedOfLife(rotation=math.pi / 2.0).centers()
    for (x, y), (u, v) in zip(upright, turned, strict=True):
        assert (u, v) == pytest.approx((-y, x))


# --- flower of life ---------------------------------------------------------


@pytest.mark.parametrize(("rings", "count"), [(0, 1), (1, 7), (2, 19), (3, 37), (4, 61)])
def test_the_flower_reaches_the_centerd_hexagonal_numbers(rings, count):
    assert len(FlowerOfLife(rings=rings).centers()) == count


def test_the_first_ring_of_the_flower_is_the_seed():
    flower = {tuple(round(c, 6) for c in p) for p in FlowerOfLife(rings=1, radius=40.0).centers()}
    seed = {tuple(round(c, 6) for c in p) for p in SeedOfLife(radius=40.0, rotation=0.0).centers()}
    assert flower == seed


def test_the_boundary_just_contains_the_outermost_circles():
    rings, radius = 3, 30.0
    motif = FlowerOfLife(rings=rings, radius=radius)
    furthest = max(math.dist((0.0, 0.0), point) for point in motif.centers())
    assert furthest + radius == pytest.approx(radius * (rings + 1))
    assert motif.build().bounds.width == pytest.approx(2.0 * radius * (rings + 1))


def test_the_boundary_can_be_left_off():
    assert len(FlowerOfLife(rings=2).build().paths) == 20
    assert len(FlowerOfLife(rings=2, boundary=False).build().paths) == 19


def test_an_absurd_ring_count_is_refused_rather_than_attempted():
    with pytest.raises(ValueError, match="circles"):
        FlowerOfLife(rings=500)


# --- fruit of life ----------------------------------------------------------


def test_the_fruit_is_thirteen_circles_that_touch_without_crossing():
    motif = FruitOfLife(radius=30.0)
    centers = motif.centers()
    assert len(centers) == 13
    for a, b in combinations(centers, 2):
        assert math.dist(a, b) >= 60.0 - 1e-9


def test_the_inner_six_touch_the_middle_one():
    middle, *rest = FruitOfLife(radius=30.0).centers()
    touching = [point for point in rest if math.dist(middle, point) == pytest.approx(60.0)]
    assert len(touching) == 6


def test_the_outer_six_sit_at_root_three_times_the_spacing():
    middle, *rest = FruitOfLife(radius=30.0).centers()
    far = [point for point in rest if math.dist(middle, point) > 61.0]
    assert len(far) == 6
    assert all(math.dist(middle, p) == pytest.approx(60.0 * math.sqrt(3.0)) for p in far)


# --- Metatron's cube --------------------------------------------------------


def test_every_pair_of_middles_is_joined():
    lines = MetatronsCube(circles=False).build().paths
    assert len(lines) == 13 * 12 // 2
    assert all(len(path.points) == 2 for path in lines)


def test_the_circles_can_be_left_off():
    assert len(MetatronsCube().build().paths) == 78 + 13
    assert len(MetatronsCube(circles=False).build().paths) == 78


def test_the_cube_stands_on_the_fruit_of_life():
    assert MetatronsCube(radius=25.0).centers() == FruitOfLife(radius=25.0).centers()


def test_the_longest_chord_spans_the_outer_ring():
    motif = MetatronsCube(radius=20.0, circles=False)
    longest = max(path.length for path in motif.build().paths)
    assert longest == pytest.approx(2.0 * 40.0 * math.sqrt(3.0))


# --- Sri Yantra -------------------------------------------------------------


def test_the_yantra_is_nine_triangles_four_up_and_five_down():
    triangles = SriYantra().triangles()
    assert len(triangles) == 9
    upward = [t for t in triangles if t[2][1] > t[0][1]]
    assert len(upward) == 4
    assert len(triangles) - len(upward) == 5


def test_every_apex_sits_on_the_axis():
    for _, _, apex in SriYantra(center=(7.0, -4.0)).triangles():
        assert apex[0] == pytest.approx(7.0)


def test_every_base_is_horizontal_and_centerd():
    for left, right, _ in SriYantra(center=(7.0, -4.0)).triangles():
        assert left[1] == pytest.approx(right[1])
        assert (left[0] + right[0]) / 2.0 == pytest.approx(7.0)


def test_every_corner_stays_inside_the_enclosing_circle():
    size = 200.0
    motif = SriYantra(size=size)
    for corners in motif.triangles():
        for corner in corners:
            assert math.dist((0.0, 0.0), corner) <= size / 2.0 + 1e-9


def test_the_figure_is_the_size_it_says():
    assert SriYantra(size=200.0).build().bounds.width == pytest.approx(200.0)


def test_the_bindu_is_the_only_loose_point():
    assert SriYantra().build().points == ((0.0, 0.0),)
    assert SriYantra(bindu=False).build().points == ()


def test_the_circle_can_be_left_off():
    assert len(SriYantra().build().paths) == 10
    assert len(SriYantra(boundary=False).build().paths) == 9


# --- golden rectangle -------------------------------------------------------


def test_the_rectangle_is_golden():
    bounds = GoldenRectangle(size=200.0).build().bounds
    assert bounds.width / bounds.height == pytest.approx(PHI)


def test_cutting_a_square_off_leaves_another_golden_rectangle():
    # The theorem, checked on the drawing rather than on the arithmetic: each
    # cut leaves a rectangle whose sides are still in the golden ratio.
    motif = GoldenRectangle(size=200.0, depth=6)
    width, height = 200.0, 200.0 / PHI
    for _ in motif.squares():
        width, height = height, width - min(width, height)
        assert width / height == pytest.approx(PHI)


def test_each_cut_is_shorter_than_the_last_by_the_golden_ratio():
    cuts = [math.dist(*cut) for cut in GoldenRectangle(size=200.0, depth=7).squares()]
    for longer, shorter in itertools.pairwise(cuts):
        assert longer / shorter == pytest.approx(PHI)


def test_depth_decides_how_many_squares_come_off():
    for depth in (0, 1, 5, 12):
        assert len(GoldenRectangle(depth=depth).squares()) == depth
        assert len(GoldenRectangle(depth=depth).build().paths) == depth + 1


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: VesicaPiscis(radius=0.0),
        lambda: SeedOfLife(radius=-1.0),
        lambda: FlowerOfLife(radius=0.0),
        lambda: FlowerOfLife(rings=-1),
        lambda: FruitOfLife(radius=0.0),
        lambda: MetatronsCube(radius=0.0),
        lambda: SriYantra(size=0.0),
        lambda: GoldenRectangle(size=0.0),
        lambda: GoldenRectangle(depth=-1),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_meta_records_the_parameters():
    design = FlowerOfLife(rings=3, radius=25.0).build()
    assert design.meta["motif"] == "sacred.flower-of-life"
    assert design.meta["rings"] == 3
    assert design.meta["radius"] == 25.0


def test_an_absurd_cut_count_is_refused():
    with pytest.raises(ValueError, match=r"\[0, 64\]"):
        GoldenRectangle(depth=200)
