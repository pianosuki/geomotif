import itertools
import math

import pytest

from spiralgen import PowerSpacing, generate_spiral


def gaps(points):
    return [math.dist(a, b) for a, b in itertools.pairwise(points)]


def test_endpoints_exact():
    points = generate_spiral((200, 0), (20, 0), 120, turns=3)
    assert points[0] == pytest.approx((200, 0))
    assert points[-1] == pytest.approx((20, 0))


def test_point_count():
    points = generate_spiral((200, 0), (20, 0), 57, turns=2)
    assert len(points) == 57


def test_default_center_is_origin():
    points = generate_spiral((100, 0), (50, 0), 20, turns=1)
    radii = [math.dist(p, (0, 0)) for p in points]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_equal_spacing_is_equal_real_distance():
    points = generate_spiral((200, 0), (20, 0), 120, turns=3)
    g = gaps(points)
    # Chord lengths vary slightly from arc lengths in the tight center;
    # they must still be equal to within a few percent.
    assert max(g) / min(g) < 1.05


def test_radial_line_gaps_exact():
    points = generate_spiral((0, 0), (200, 0), 11)
    for gap in gaps(points):
        assert gap == pytest.approx(20.0, abs=1e-6)


def test_power_spacing_increases_gaps():
    points = generate_spiral((200, 0), (20, 0), 40, turns=2, spacing=PowerSpacing(2))
    g = gaps(points)
    assert g[0] < g[len(g) // 2] < g[-1]


def test_power_out_decreases_gaps():
    points = generate_spiral((200, 0), (20, 0), 40, turns=2, spacing=PowerSpacing(2, mode="out"))
    g = gaps(points)
    assert g[0] > g[len(g) // 2] > g[-1]


def test_clockwise_vs_counterclockwise():
    # Math convention, y-up: counter-clockwise initially moves +y from
    # a point right of center; clockwise moves -y.
    ccw = generate_spiral((100, 0), (0, 100), 50, clockwise=False)
    cw = generate_spiral((100, 0), (0, -100), 50, clockwise=True)
    assert ccw[1][1] > 0
    assert cw[1][1] < 0


def test_y_down_flips_visual_direction():
    # In y-down (screen) coordinates, on-screen clockwise from a point
    # right of center initially moves toward +y (down the screen), which
    # is the math counter-clockwise sweep.
    up = generate_spiral((100, 0), (0, -100), 50, clockwise=True)
    down = generate_spiral((100, 0), (0, 100), 50, clockwise=True, y_down=True)
    assert up[1][1] < 0
    assert down[1][1] > 0


def test_y_down_equivalent_to_opposite_direction():
    a = generate_spiral((100, 0), (0, 100), 50, clockwise=True, y_down=True)
    b = generate_spiral((100, 0), (0, 100), 50, clockwise=False)
    for pa, pb in zip(a, b, strict=True):
        assert pa == pytest.approx(pb)


def test_turns_add_full_revolutions():
    points = generate_spiral((100, 0), (100, 0), 500, turns=2, clockwise=False)
    assert math.dist(points[0], points[-1]) < 1e-9
    total_length = sum(gaps(points))
    # Two full circles of radius 100, minus polyline shortfall.
    assert total_length == pytest.approx(2 * 2 * math.pi * 100, rel=1e-3)


def test_start_at_center_degenerates_to_radial_line():
    points = generate_spiral((0, 0), (200, 0), 10)
    assert points[0] == pytest.approx((0, 0))
    assert points[-1] == pytest.approx((200, 0))


def test_start_equals_end_no_sweep():
    points = generate_spiral((50, 50), (50, 50), 5)
    assert all(p == pytest.approx((50, 50)) for p in points)


def test_parametric_mode_compresses_toward_center():
    points = generate_spiral((200, 0), (20, 0), 120, turns=3, arc_length=False)
    g = gaps(points)
    assert max(g) / min(g) > 3  # visibly unequal, unlike arc-length mode


def test_custom_callable_spacing():
    points = generate_spiral((200, 0), (20, 0), 30, turns=1, spacing=lambda t: t * t)
    assert len(points) == 30
    assert points[0] == pytest.approx((200, 0))


def test_custom_center():
    points = generate_spiral((400, 150), (350, 150), 20, center=(300, 150), turns=1)
    radii = [math.dist(p, (300, 150)) for p in points]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_invalid_args_rejected():
    with pytest.raises(ValueError):
        generate_spiral((0, 0), (1, 1), 1)
    with pytest.raises(ValueError):
        generate_spiral((0, 0), (1, 1), 10, turns=-1)
    with pytest.raises(TypeError):
        generate_spiral((0, 0), (1, 1), 10, spacing="linear")  # type: ignore[arg-type]
