from dataclasses import dataclass

import pytest

from geomotif import Design, Motif, Path, PowerSpacing, SupportsBuild


@dataclass(frozen=True, slots=True)
class Line(Motif):
    """A straight line from the origin, for exercising the base class."""

    length: float = 100.0

    def build(self) -> Design:
        return Design((Path(((0.0, 0.0), (self.length, 0.0))),))


class DuckTyped:
    """Builds a design without inheriting from anything."""

    def build(self) -> Design:
        return Design((Path(((0.0, 0.0), (1.0, 1.0))),))


def test_motif_is_abstract():
    with pytest.raises(TypeError):
        Motif()  # type: ignore[abstract]


def test_build_returns_native_resolution():
    assert len(Line().build().paths[0]) == 2


def test_generate_resamples_to_the_requested_count():
    assert len(Line().generate(50)) == 50


def test_generate_defaults_to_equal_spacing():
    design = Line().generate(11)
    xs = [x for x, _ in design]
    assert xs == pytest.approx([i * 10.0 for i in range(11)])


def test_generate_accepts_a_spacing_curve():
    design = Line().generate(11, spacing=PowerSpacing(2))
    xs = [x for x, _ in design]
    assert xs[1] < 10.0  # front-loaded, unlike equal spacing


def test_generate_accepts_a_plain_callable():
    design = Line().generate(11, spacing=lambda t: t * t)
    assert len(design) == 11


def test_generate_supports_step_mode():
    design = Line().generate(step=25.0)
    assert len(design) == 5


def test_generate_passes_placement_through():
    assert len(Line().generate(20, by="parameter")) == 20


def test_duck_typed_builder_satisfies_the_protocol():
    assert isinstance(DuckTyped(), SupportsBuild)
    assert isinstance(Line(), SupportsBuild)


def test_non_builder_does_not_satisfy_the_protocol():
    assert not isinstance(object(), SupportsBuild)


def test_motifs_are_comparable_and_reprable():
    # Frozen dataclasses give equality and repr for free, which is what makes
    # a design spec round-trippable.
    assert Line(10.0) == Line(10.0)
    assert Line(10.0) != Line(20.0)
    assert "length=10.0" in repr(Line(10.0))
