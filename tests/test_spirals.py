import itertools
import math

import pytest

from geomotif import PowerSpacing
from geomotif.motifs import SpiralBetween


def gaps(points):
    return [math.dist(a, b) for a, b in itertools.pairwise(points)]


def test_endpoints_exact():
    points = list(SpiralBetween((200, 0), (20, 0), turns=3).generate(120))
    assert points[0] == pytest.approx((200, 0))
    assert points[-1] == pytest.approx((20, 0))


def test_point_count():
    assert len(SpiralBetween((200, 0), (20, 0), turns=2).generate(57)) == 57


def test_default_center_is_origin():
    points = list(SpiralBetween((100, 0), (50, 0), turns=1).generate(20))
    radii = [math.dist(p, (0, 0)) for p in points]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_equal_spacing_is_equal_real_distance():
    points = list(SpiralBetween((200, 0), (20, 0), turns=3).generate(120))
    g = gaps(points)
    # Chord lengths vary slightly from arc lengths in the tight center;
    # they must still be equal to within a few percent.
    assert max(g) / min(g) < 1.05


def test_radial_line_gaps_exact():
    points = list(SpiralBetween((0, 0), (200, 0)).generate(11))
    for gap in gaps(points):
        assert gap == pytest.approx(20.0, abs=1e-6)


def test_power_spacing_increases_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=2).generate(40, spacing=PowerSpacing(2))
    g = gaps(list(design))
    assert g[0] < g[len(g) // 2] < g[-1]


def test_power_out_decreases_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=2).generate(
        40, spacing=PowerSpacing(2, mode="out")
    )
    g = gaps(list(design))
    assert g[0] > g[len(g) // 2] > g[-1]


def test_clockwise_vs_counterclockwise():
    # Math convention, y-up: counter-clockwise initially moves +y from
    # a point right of center; clockwise moves -y.
    ccw = list(SpiralBetween((100, 0), (0, 100), clockwise=False).generate(50))
    cw = list(SpiralBetween((100, 0), (0, -100), clockwise=True).generate(50))
    assert ccw[1][1] > 0
    assert cw[1][1] < 0


def test_flipping_y_reverses_the_apparent_direction():
    # The old y_down flag is gone: mirroring the design is strictly more
    # general, and this is the identity that makes it equivalent. A spiral
    # mirrored about the x-axis is the mirrored-endpoint spiral wound the
    # other way.
    flipped = SpiralBetween((100, 0), (0, 100), turns=1, clockwise=True).build().flipped_y()
    expected = SpiralBetween((100, 0), (0, -100), turns=1, clockwise=False).build()
    for a, b in zip(flipped.paths[0].points, expected.paths[0].points, strict=True):
        assert a == pytest.approx(b, abs=1e-9)


def test_turns_add_full_revolutions():
    points = list(SpiralBetween((100, 0), (100, 0), turns=2, clockwise=False).generate(500))
    assert math.dist(points[0], points[-1]) < 1e-9
    total_length = sum(gaps(points))
    # Two full circles of radius 100, minus polyline shortfall.
    assert total_length == pytest.approx(2 * 2 * math.pi * 100, rel=1e-3)


def test_start_at_center_degenerates_to_radial_line():
    points = list(SpiralBetween((0, 0), (200, 0)).generate(10))
    assert points[0] == pytest.approx((0, 0))
    assert points[-1] == pytest.approx((200, 0))
    assert all(y == pytest.approx(0.0, abs=1e-9) for _, y in points)


def test_end_at_center_degenerates_to_radial_line():
    points = list(SpiralBetween((200, 0), (0, 0)).generate(10))
    assert all(y == pytest.approx(0.0, abs=1e-9) for _, y in points)


def test_start_equals_end_no_sweep():
    points = list(SpiralBetween((50, 50), (50, 50)).generate(5))
    assert all(p == pytest.approx((50, 50)) for p in points)


def test_both_endpoints_at_center():
    points = list(SpiralBetween((0, 0), (0, 0)).generate(4))
    assert all(p == pytest.approx((0, 0)) for p in points)


def test_parametric_mode_compresses_toward_center():
    design = SpiralBetween((200, 0), (20, 0), turns=3).generate(120, by="parameter")
    g = gaps(list(design))
    assert max(g) / min(g) > 3  # visibly unequal, unlike arc-length mode


def test_custom_callable_spacing():
    design = SpiralBetween((200, 0), (20, 0), turns=1).generate(30, spacing=lambda t: t * t)
    points = list(design)
    assert len(points) == 30
    assert points[0] == pytest.approx((200, 0))


def test_custom_center():
    design = SpiralBetween((400, 150), (350, 150), center=(300, 150), turns=1).generate(20)
    radii = [math.dist(p, (300, 150)) for p in design]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_step_mode_gives_fixed_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=3).generate(step=10.0)
    g = gaps(list(design))
    # Gaps are exactly 10 *along the curve*; measured as straight lines they
    # fall a little short wherever the spiral is winding tightly, and a
    # 10-unit step near radius 20 cuts a visible corner.
    assert all(9.8 <= gap <= 10.0 + 1e-9 for gap in g)


def test_resolution_override_changes_measurement_density():
    coarse = SpiralBetween((200, 0), (20, 0), turns=3, resolution=8).build()
    assert len(coarse.paths[0]) == 9


def test_build_records_reproducible_meta():
    meta = SpiralBetween((200, 0), (20, 0), turns=3).build().meta
    assert meta["motif"] == "spiral.between"
    assert meta["turns"] == 3
    assert meta["clockwise"] is True


def test_invalid_args_rejected():
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1), turns=-1)
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1), resolution=0)
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1)).generate(1)
    with pytest.raises(TypeError):
        SpiralBetween((0, 0), (1, 1)).generate(10, spacing="linear")  # type: ignore[arg-type]
