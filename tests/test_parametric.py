import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import pytest

from geomotif import Curve, MultiCurveMotif, ParametricMotif, Point, PolarMotif


@dataclass(frozen=True, slots=True)
class Circle(ParametricMotif):
    domain = (0.0, math.tau)
    closed = True

    radius: float = 10.0

    def position(self, u: float) -> Point:
        return (self.radius * math.cos(u), self.radius * math.sin(u))


@dataclass(frozen=True, slots=True)
class Ramp(ParametricMotif):
    """An open curve whose x coordinate is its own parameter."""

    domain = (2.0, 5.0)

    def position(self, u: float) -> Point:
        return (u, 0.0)


@dataclass(frozen=True, slots=True)
class Rose(PolarMotif):
    closed = True

    k: float = 5.0

    def radius(self, theta: float) -> float:
        return math.cos(self.k * theta)


@dataclass(frozen=True, slots=True)
class Rails(MultiCurveMotif):
    gap: float = 1.0

    def curves(self) -> Iterable[Curve]:
        yield Curve(lambda u: (u, 0.0))
        yield Curve(lambda u: (u, self.gap))


def test_circle_has_the_analytic_circumference():
    # 512 chords cut the corners very slightly, hence the loose tolerance.
    assert Circle().build().paths[0].length == pytest.approx(math.tau * 10.0, rel=1e-4)


def test_closed_curves_do_not_repeat_the_seam():
    path = Circle().build().paths[0]
    assert path.closed is True
    assert path.points[0] != path.points[-1]
    assert math.dist(path.points[0], path.points[-1]) == pytest.approx(
        math.dist(path.points[0], path.points[1])
    )


def test_open_curves_keep_both_endpoints():
    path = Ramp().build().paths[0]
    assert path.closed is False
    assert path.points[0] == (2.0, 0.0)
    assert path.points[-1] == (5.0, 0.0)


def test_domain_is_respected():
    xs = [x for x, _ in Ramp().build()]
    assert min(xs) == 2.0
    assert max(xs) == 5.0


def test_resolution_sets_the_sample_count():
    assert len(Ramp(resolution=10).build().paths[0]) == 11
    # A closed curve loses the duplicated seam sample.
    assert len(Circle(resolution=10).build().paths[0]) == 10


def test_resolution_must_be_positive():
    with pytest.raises(ValueError):
        Ramp(resolution=0).build()


def test_sweep_turns_drives_the_default_density():
    @dataclass(frozen=True, slots=True)
    class Coiled(Ramp):
        def sweep_turns(self) -> float:
            return 8.0

    assert len(Coiled().build().paths[0]) > len(Ramp().build().paths[0])


def test_generate_resamples_a_parametric_motif():
    assert len(Circle().generate(64)) == 64


def test_meta_records_the_class_and_its_parameters():
    meta = Circle(radius=3.0).build().meta
    assert meta["motif"] == "Circle"
    assert meta["radius"] == 3.0
    assert meta["resolution"] is None


def test_a_subclass_may_declare_required_positional_parameters():
    # Every field on a base is keyword-only precisely so that this is legal:
    # a plain `radius: float` here would otherwise follow a defaulted field.
    @dataclass(frozen=True, slots=True)
    class Needy(ParametricMotif):
        size: float

        def position(self, u: float) -> Point:
            return (u * self.size, 0.0)

    assert Needy(4.0).build().bounds.max_x == 4.0


def test_motifs_are_frozen():
    with pytest.raises(AttributeError):
        Circle().radius = 5.0  # type: ignore[misc]


def test_polar_center_offsets_the_whole_curve():
    centered = Rose(center=(100.0, 50.0)).build().bounds.center
    assert centered == pytest.approx(
        tuple(a + b for a, b in zip(Rose().build().bounds.center, (100.0, 50.0), strict=True))
    )


def test_polar_negative_radius_reflects_through_the_origin():
    @dataclass(frozen=True, slots=True)
    class Backwards(PolarMotif):
        theta_span: float = field(default=0.0, kw_only=True)

        def radius(self, theta: float) -> float:
            return -1.0

    # theta stays at 0, where a radius of -1 must land on the negative x-axis
    # rather than being clipped away.
    assert Backwards().build().paths[0].points[0] == pytest.approx((-1.0, 0.0))


def test_polar_theta_range_selects_an_arc():
    @dataclass(frozen=True, slots=True)
    class UnitArc(PolarMotif):
        theta_start: float = field(default=0.0, kw_only=True)
        theta_span: float = field(default=math.pi / 2, kw_only=True)

        def radius(self, theta: float) -> float:
            return 1.0

    points = UnitArc().build().paths[0].points
    assert points[0] == pytest.approx((1.0, 0.0))
    assert points[-1] == pytest.approx((0.0, 1.0))
    assert all(y >= -1e-9 for _, y in points)


def test_polar_sweep_turns_follows_the_span():
    assert Rose().sweep_turns() == pytest.approx(1.0)
    assert Rose(theta_span=-4.0 * math.tau).sweep_turns() == pytest.approx(4.0)


def test_rose_stays_within_its_unit_radius():
    assert all(math.dist(p, (0.0, 0.0)) <= 1.0 + 1e-9 for p in Rose().build())


def test_multi_curve_emits_one_path_per_curve():
    design = Rails().build()
    assert len(design.paths) == 2
    assert design.bounds.max_y == 1.0


def test_multi_curve_without_curves_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Nothing(MultiCurveMotif):
        def curves(self) -> Iterable[Curve]:
            return ()

    with pytest.raises(ValueError, match="no curves"):
        Nothing().build()


def test_multi_curve_spreads_a_point_budget_across_its_paths():
    design = Rails().generate(100)
    assert len(design) == 100
    assert len(design.paths) == 2


def test_bases_are_abstract():
    for base in (MultiCurveMotif, ParametricMotif, PolarMotif):
        with pytest.raises(TypeError):
            base()  # type: ignore[abstract]


def test_motifs_carry_no_instance_dict():
    # Slotted dataclasses only take effect if every class in the MRO is
    # slotted; one that is not silently hands every instance a __dict__ back.
    assert not hasattr(Circle(), "__dict__")
