import json
import math
from typing import Any

import pytest

from geomotif import Bounds, from_spec, load_spec, save_spec, to_spec
from geomotif.core import registry
from geomotif.core.types import Design, Path
from geomotif.io import spec as spec_module
from geomotif.motifs import Rose, SquareTiling, Star


def example(name: str):
    """The motif a registered example describes."""
    return registry.create(name, **registry.describe(name).example)


def spec_of(name: str) -> Any:
    """The spec of a motif built from its registered example."""
    return to_spec(example(name))


def rebuilt(name: str) -> Any:
    """A motif taken through a spec and back."""
    return from_spec(spec_of(name))


def test_a_spec_names_the_motif_and_nests_its_parameters():
    blob: Any = to_spec(Star(points=7))
    assert blob["motif"] == "star"
    assert blob["params"]["points"] == 7


def test_a_spec_records_the_writing_version():
    from geomotif import __version__

    assert to_spec(Star())["geomotif"] == __version__


def test_a_spec_is_json():
    # The whole point is that it survives a file; a value json cannot write
    # would only fail at the last moment.
    json.dumps(to_spec(Star(points=7)))


def test_a_motif_survives_the_round_trip(tmp_path):
    star = Star(points=9, radius=42.0)
    assert load_spec(save_spec(star, tmp_path / "s.json")) == star


def test_a_design_can_be_asked_for_its_own_recipe():
    design = Star(points=6).build()
    assert to_spec(design) == to_spec(Star(points=6))


def test_the_file_is_small_beside_the_points_it_stands_for(tmp_path):
    from geomotif import save_design

    motif = example("mandala")
    recipe = save_spec(motif, tmp_path / "recipe.json").stat().st_size
    points = save_design(motif.build(), tmp_path / "points.json").stat().st_size
    assert recipe * 50 < points


def test_a_parameter_that_is_itself_a_motif_nests_as_a_spec():
    blob = spec_of("kaleidoscope")
    assert blob["params"]["unit"]["motif"] == "rose"
    assert rebuilt("kaleidoscope").unit == Rose(n=5, d=2, size=150.0)


def test_a_value_dataclass_parameter_names_its_type():
    blob = spec_of("tiling.square")
    assert blob["params"]["region"]["$type"] == "geomotif.core.types.Bounds"
    assert isinstance(rebuilt("tiling.square").region, Bounds)


def test_a_value_dataclass_nested_inside_another_survives():
    # mandala's rings are Rings, and each Ring holds a motif of its own.
    assert rebuilt("mandala").build().paths == example("mandala").build().paths


def test_lists_come_back_as_tuples():
    # JSON has one sequence type, and every sequence parameter here is a
    # tuple -- several of them get hashed.
    assert isinstance(rebuilt("tiling.ammann-beenker").offsets, tuple)
    assert isinstance(rebuilt("star").center, tuple)


def test_the_version_stamp_is_recorded_not_enforced():
    blob = to_spec(Star())
    blob["geomotif"] = "0.0.1-from-the-future"
    assert from_spec(blob) == Star()


def test_a_missing_version_stamp_is_no_obstacle():
    blob = to_spec(Star())
    del blob["geomotif"]
    assert from_spec(blob) == Star()


def test_a_motif_parameterized_by_a_function_says_so():
    with pytest.raises(TypeError, match=r"polar\.expression\.formula"):
        to_spec(example("polar.expression"))


def test_an_unregistered_nested_motif_is_refused():
    class Anonymous(Rose):
        __slots__ = ()

    with pytest.raises(TypeError, match=r"not .* registered"):
        to_spec(registry.create("kaleidoscope", unit=Anonymous()))


def test_a_non_finite_parameter_is_refused():
    # json.dumps would write Infinity, which nothing else can read back.
    with pytest.raises(ValueError, match="not a JSON number"):
        to_spec(Star(radius=math.inf))


def test_a_design_with_no_motif_recorded_has_no_spec():
    loose = Design(paths=(Path(((0.0, 0.0), (1.0, 1.0))),), meta={"note": "mine"})
    with pytest.raises(ValueError, match="does not record which motif"):
        to_spec(loose)


def test_a_spec_without_a_motif_name_is_refused():
    with pytest.raises(ValueError, match="expected a 'motif' key"):
        from_spec({"params": {"points": 5}})


def test_a_spec_whose_params_are_not_an_object_is_refused():
    with pytest.raises(ValueError, match="'params' must be an object"):
        from_spec({"motif": "star", "params": [1, 2, 3]})


def test_a_spec_with_no_params_builds_the_defaults():
    assert from_spec({"motif": "star"}) == Star()


def test_an_unknown_motif_name_is_refused():
    with pytest.raises(KeyError):
        from_spec({"motif": "no-such-motif", "params": {}})


def test_a_file_that_is_not_an_object_is_refused(tmp_path):
    target = tmp_path / "points.json"
    target.write_text("[[0, 0], [1, 1]]")
    with pytest.raises(ValueError, match="not a spec file"):
        load_spec(target)


def test_a_spec_may_not_name_a_value_type_outside_the_library():
    # A spec is data, and data does not get to choose what this process
    # imports. Without the guard, loading a file would run module-level code.
    with pytest.raises(ValueError, match="refusing to import"):
        from_spec(
            {
                "motif": "tiling.square",
                "params": {"region": {"$type": "os.system", "x": 1}},
            }
        )


def test_a_value_type_that_is_not_a_dataclass_is_refused():
    with pytest.raises(ValueError, match="not a value type"):
        from_spec(
            {
                "motif": "tiling.square",
                "params": {"region": {"$type": "geomotif.core.registry.register"}},
            }
        )


def test_a_value_type_that_does_not_exist_is_refused():
    with pytest.raises(ValueError, match="no value type"):
        from_spec(
            {
                "motif": "tiling.square",
                "params": {"region": {"$type": "geomotif.core.types.Nonesuch"}},
            }
        )


def test_a_plugin_package_may_name_its_own_value_types(monkeypatch):
    class FakeEntryPoint:
        value = "my_plugin.motifs:register_all"

    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_: [FakeEntryPoint()])
    assert spec_module._importable_packages() == frozenset({"geomotif", "my_plugin"})


def test_a_plain_mapping_parameter_survives():
    # No builtin motif takes one, but a third-party motif may, and dropping
    # it silently would be worse than carrying it.
    encoded = spec_module._encode({"a": {"b": (1, 2)}}, where="p")
    assert encoded == {"a": {"b": [1, 2]}}
    assert spec_module._decode(encoded, frozenset(), where="p") == {"a": {"b": (1, 2)}}


def test_the_region_a_tiling_was_given_comes_back_the_same(tmp_path):
    tiling = SquareTiling(region=Bounds(-40.0, -20.0, 40.0, 20.0), size=10.0)
    loaded = load_spec(save_spec(tiling, tmp_path / "t.json"))
    assert isinstance(loaded, SquareTiling)
    assert loaded.region == tiling.region


def test_the_file_is_indented_for_a_human_to_edit(tmp_path):
    text = save_spec(Star(), tmp_path / "s.json").read_text()
    assert "\n  " in text
    assert text.endswith("\n")


def test_indent_can_be_turned_off(tmp_path):
    text = save_spec(Star(), tmp_path / "s.json", indent=None).read_text()
    assert text.count("\n") == 1
