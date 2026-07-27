"""Contract every registered motif must satisfy, checked automatically.

Adding a motif costs no test-writing effort and still gets meaningful
coverage: register it and every check below starts running against it. That
is the point -- a catalogue of well over a hundred motifs cannot rely on each
author remembering to assert that their design is finite and reproducible.

Anything specific to one motif -- petal counts, known perimeters, analytic
golden values -- belongs in that motif's own test module. This file is only
for what is true of all of them.
"""

import math

import pytest

from geomotif import Design, load_design, load_spec, save_design, save_points, save_spec
from geomotif.core import registry

NAMES = registry.names()

# Counts spanning the interesting cases: the minimum, an odd small one, a
# typical plot, and more points than most motifs have vertices.
COUNTS = (2, 3, 50, 501)


def case(name: str):
    """Return ``name`` as a parameter, skipped if its optional extra is missing."""
    info = registry.describe(name)
    if info.available:
        return name
    return pytest.param(name, marks=pytest.mark.skip(reason=f"{name} needs {info.requires}"))


#: What the parametrized checks below run over. A motif behind an extra that
#: is not installed is skipped rather than failed: the whole point of
#: ``requires=`` is that such a motif is still registered and still described.
CASES = [case(name) for name in NAMES]


def build(name: str) -> tuple[registry.MotifInfo, Design]:
    """Return a motif's registry entry and the design its example builds."""
    info = registry.describe(name)
    return info, registry.create(name, **info.example).build()


def test_the_registry_is_populated():
    # Without this, an empty registry would silently turn every parametrized
    # test below into zero tests, and the suite would pass by doing nothing.
    assert NAMES


@pytest.mark.parametrize("name", CASES)
def test_the_example_instantiates(name):
    info = registry.describe(name)
    required = [param.name for param in info.params if param.required]
    missing = [param for param in required if param not in info.example]
    assert not missing, (
        f"{name} has required parameter(s) {missing} but its @register(example=...) "
        f"does not supply them, so neither the gallery nor this suite can build it"
    )
    assert isinstance(registry.create(name, **info.example), info.cls)


@pytest.mark.parametrize("name", CASES)
def test_build_returns_a_non_empty_design(name):
    _, design = build(name)
    assert isinstance(design, Design)
    assert len(design) > 0


@pytest.mark.parametrize("name", CASES)
def test_every_coordinate_is_finite(name):
    _, design = build(name)
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in design)


@pytest.mark.parametrize("name", CASES)
def test_the_design_has_extent(name):
    _, design = build(name)
    bounds = design.bounds
    assert bounds.width > 0 or bounds.height > 0


@pytest.mark.parametrize("name", CASES)
def test_closed_paths_do_not_repeat_their_seam(name):
    _, design = build(name)
    for path in design.paths:
        if path.closed and len(path.points) > 2:
            assert path.points[0] != path.points[-1]


@pytest.mark.parametrize("name", CASES)
def test_generate_returns_exactly_the_requested_count(name):
    motif = registry.create(name, **registry.describe(name).example)
    for count in COUNTS:
        design = motif.generate(count)
        if not design.paths:
            continue  # A pure point set has no curve to redistribute along.
        assert sum(len(path) for path in design.paths) == count


@pytest.mark.parametrize("name", CASES)
def test_generate_supports_a_fixed_step(name):
    motif = registry.create(name, **registry.describe(name).example)
    design = motif.build()
    longest = max((path.length for path in design.paths), default=0.0)
    if longest == 0.0:
        pytest.skip(f"{name} has no strokes to walk along")
    assert len(motif.generate(step=longest / 10.0)) > 0


@pytest.mark.parametrize("name", CASES)
def test_building_twice_gives_identical_output(name):
    # Stochastic motifs must seed their own Random, never the global one, or
    # the same spec would render differently on every run.
    first = build(name)[1]
    second = build(name)[1]
    assert [path.points for path in first.paths] == [path.points for path in second.paths]
    assert first.points == second.points


@pytest.mark.parametrize("name", CASES)
def test_meta_round_trips_through_the_registry(name):
    _, design = build(name)
    assert design.meta.get("motif") == name, (
        f"{name} should record its registered name in Design.meta; "
        f"use registry.spec(self) to build it"
    )
    rebuilt = registry.create(name, **{k: v for k, v in design.meta.items() if k != "motif"})
    assert [p.points for p in rebuilt.build().paths] == [p.points for p in design.paths]


@pytest.mark.parametrize("name", CASES)
def test_the_design_survives_the_common_operations(name):
    _, design = build(name)
    assert design.fit(100.0, 100.0).bounds.max_x <= 100.0 + 1e-9
    assert len(design.flipped_y()) == len(design)


@pytest.mark.parametrize("name", CASES)
def test_the_design_exports(name, tmp_path):
    _, design = build(name)
    out = tmp_path / "points.csv"
    save_points(design, out)
    assert out.read_text().startswith("x,y")


@pytest.mark.parametrize("name", CASES)
def test_the_design_survives_a_design_file(name, tmp_path):
    _, design = build(name)
    reloaded = load_design(save_design(design, tmp_path / "design.json", meta=False))
    assert [(p.points, p.closed) for p in reloaded.paths] == [
        (p.points, p.closed) for p in design.paths
    ]
    assert reloaded.points == design.points


@pytest.mark.parametrize("name", CASES)
def test_the_motif_survives_a_spec_file(name, tmp_path):
    motif = registry.create(name, **registry.describe(name).example)
    try:
        written = save_spec(motif, tmp_path / "spec.json")
    except TypeError as exc:
        # A motif whose parameter *is* a Python function is defined by code
        # rather than by data; there is nothing to write. Skipping rather than
        # asserting keeps the reason visible in the report.
        pytest.skip(f"{name} has no spec: {exc}")
    rebuilt = load_spec(written).build()
    original = motif.build()
    assert [p.points for p in rebuilt.paths] == [p.points for p in original.paths]
    assert rebuilt.points == original.points


@pytest.mark.parametrize("name", CASES)
def test_the_motif_is_documented(name):
    info = registry.describe(name)
    assert info.summary, f"{name} needs a docstring: it is what the CLI and gallery show"
    assert not info.summary.endswith(("...", ":"))


@pytest.mark.parametrize("name", CASES)
def test_the_name_is_well_formed(name):
    assert name == name.lower()
    assert " " not in name
    family = registry.describe(name).family
    assert family is None or (family == family.lower() and " " not in family)
