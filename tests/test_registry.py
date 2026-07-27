import subprocess
import sys
from dataclasses import dataclass, field

import pytest

from geomotif import Design, Motif, Path
from geomotif.core import registry


@pytest.fixture(autouse=True)
def isolated_registry():
    """Keep test registrations out of the real registry."""
    # Force the lazy load first, so the snapshot includes the builtins and
    # restoring it cannot strip them back out for later tests.
    registry.names()
    saved = dict(registry._REGISTRY)
    yield
    registry._REGISTRY.clear()
    registry._REGISTRY.update(saved)


@dataclass(frozen=True, slots=True)
class Dot(Motif):
    """A single dot.

    The second paragraph is not part of the summary.
    """

    x: float = 0.0
    y: float = 0.0
    label: str = field(default="dot", metadata={"help": "what to call it"})

    def build(self) -> Design:
        return Design(points=((self.x, self.y),))


def test_register_and_get():
    registry.register("dot")(Dot)
    assert registry.get("dot") is Dot


def test_register_returns_the_class_unchanged():
    assert registry.register("dot")(Dot) is Dot


def test_name_is_derived_from_camel_case():
    @registry.register()
    @dataclass(frozen=True, slots=True)
    class GoldenSpiral(Motif):
        def build(self) -> Design:
            return Design((Path(((0.0, 0.0), (1.0, 1.0))),))

    assert "golden-spiral" in registry.names()


def test_names_are_sorted():
    registry.register("zebra")(Dot)
    registry.register("aardvark", family="animals")(Dot)
    listed = registry.names()
    assert listed.index("aardvark") < listed.index("zebra")


def test_names_can_filter_by_family():
    registry.register("a", family="one")(Dot)
    registry.register("b", family="two")(Dot)
    assert registry.names(family="one") == ("a",)


def test_families_lists_only_populated_families():
    registry.register("a", family="one")(Dot)
    assert "one" in registry.families()


def test_duplicate_name_rejected():
    registry.register("dot")(Dot)

    @dataclass(frozen=True, slots=True)
    class Other(Motif):
        def build(self) -> Design:
            return Design()

    with pytest.raises(ValueError):
        registry.register("dot")(Other)


def test_re_registering_the_same_class_is_allowed():
    registry.register("dot")(Dot)
    registry.register("dot")(Dot)


def test_unknown_name_raises_with_a_hint():
    registry.register("widget.large")(Dot)
    with pytest.raises(KeyError, match=r"widget\.large"):
        registry.get("widget")


def test_create_instantiates_with_parameters():
    registry.register("dot")(Dot)
    motif = registry.create("dot", x=3.0, y=4.0)
    assert isinstance(motif, Dot)
    assert motif.build().points == ((3.0, 4.0),)


def test_create_uses_defaults():
    registry.register("dot")(Dot)
    assert registry.create("dot").build().points == ((0.0, 0.0),)


def test_create_rejects_unknown_parameters():
    registry.register("dot")(Dot)
    with pytest.raises(TypeError):
        registry.create("dot", nonsense=1)


def test_describe_reports_docs_and_parameters():
    registry.register("dot", family="primitive")(Dot)
    info = registry.describe("dot")
    assert info.name == "dot"
    assert info.cls is Dot
    assert info.family == "primitive"
    assert info.summary == "A single dot."
    assert "second paragraph" in info.doc
    assert [p.name for p in info.params] == ["x", "y", "label"]


def test_describe_exposes_defaults_and_help_metadata():
    registry.register("dot")(Dot)
    label = registry.describe("dot").params[2]
    assert label.default == "dot"
    assert label.required is False
    assert label.description == "what to call it"


def test_describe_marks_parameters_without_defaults_as_required():
    @registry.register("needy")
    @dataclass(frozen=True, slots=True)
    class Needy(Motif):
        """Needs a radius."""

        radius: float

        def build(self) -> Design:
            return Design(points=((self.radius, 0.0),))

    assert registry.describe("needy").params[0].required is True


def test_describe_records_optional_dependencies():
    registry.register("dot", requires="scipy")(Dot)
    assert registry.describe("dot").requires == "scipy"


def test_a_motif_that_needs_nothing_is_always_available():
    registry.register("plain-dot")(Dot)
    assert registry.describe("plain-dot").available is True


def test_a_motif_whose_dependency_is_missing_is_reported_unavailable():
    # Listing it has to keep working -- that is the whole point of declaring
    # the dependency instead of importing it at module scope.
    registry.register("absent-dot", requires="a_package_nobody_has")(Dot)
    info = registry.describe("absent-dot")
    assert info.available is False
    assert info.summary


def test_a_dependency_whose_parent_package_is_missing_is_unavailable_too():
    # Looking this one up raises rather than returning nothing, since the
    # parent has to be imported before the child can be found.
    registry.register("nested-dot", requires="a_package_nobody_has.submodule")(Dot)
    assert registry.describe("nested-dot").available is False


def test_describe_skips_fields_that_are_not_constructor_parameters():
    @registry.register("derived")
    @dataclass(frozen=True, slots=True)
    class Derived(Motif):
        """Has a field the caller never passes."""

        x: float = 0.0
        computed: float = field(init=False, default=1.0)

        def build(self) -> Design:
            return Design(points=((self.x, self.computed),))

    assert [p.name for p in registry.describe("derived").params] == ["x"]


def test_describe_handles_non_dataclass_motifs():
    @registry.register("plain")
    class Plain(Motif):
        """Not a dataclass."""

        def build(self) -> Design:
            return Design()

    assert registry.describe("plain").params == ()


def test_describe_reports_an_empty_example_by_default():
    registry.register("dot")(Dot)
    assert registry.describe("dot").example == {}


def test_describe_reports_the_registered_example():
    registry.register("dot", example={"x": 1.0})(Dot)
    assert registry.describe("dot").example == {"x": 1.0}


def test_the_example_cannot_be_mutated_through_the_registry():
    example = {"x": 1.0}
    registry.register("dot", example=example)(Dot)
    example["x"] = 99.0
    assert registry.describe("dot").example == {"x": 1.0}


def test_name_for_finds_a_registered_class():
    registry.register("dot")(Dot)
    assert registry.name_for(Dot) == "dot"


def test_name_for_returns_none_for_a_stranger():
    assert registry.name_for(int) is None


def test_spec_records_the_name_and_every_parameter():
    registry.register("dot")(Dot)
    assert dict(registry.spec(Dot(x=1.0, y=2.0))) == {
        "motif": "dot",
        "x": 1.0,
        "y": 2.0,
        "label": "dot",
    }


def test_spec_falls_back_to_the_class_name_when_unregistered():
    assert registry.spec(Dot())["motif"] == "Dot"


def test_spec_is_read_only():
    with pytest.raises(TypeError):
        registry.spec(Dot())["motif"] = "other"  # type: ignore[index]


def test_spec_of_a_non_dataclass_is_just_its_name():
    class Plain(Motif):
        def build(self) -> Design:
            return Design()

    # Nothing to introspect, so the spec is the name alone -- qualified here
    # only because the class is defined inside this function.
    assert dict(registry.spec(Plain())) == {"motif": Plain.__qualname__}


def test_builtin_spiral_is_registered():
    assert "spiral.between" in registry.names()
    assert registry.describe("spiral.between").family == "spiral"


def test_builtins_register_without_importing_their_module():
    # Motifs register as an import side effect, so a lookup must import the
    # catalogue itself rather than reporting whatever the caller happened to
    # import first. Needs a fresh interpreter: within this session another
    # test has already imported geomotif.motifs, which would mask the bug.
    source = "from geomotif.core import registry; print(registry.names())"
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "spiral.between" in result.stdout


def test_composers_register_too():
    assert "mandala" in registry.names()
    assert "snowflake" in registry.describe("snowflake").name


def test_a_parameter_called_motif_is_refused():
    # It would overwrite the design's own name in Design.meta, and the spec
    # could then no longer be rebuilt -- a silent corruption worth catching
    # at import rather than at round-trip.
    with pytest.raises(ValueError, match="reserves"):

        @registry.register("collides")
        @dataclass(frozen=True)
        class Collides(Motif):
            motif: int = 0

            def build(self) -> Design:
                return Design()


def test_a_plugin_is_discovered_through_its_entry_point(monkeypatch):
    # The whole third-party contract: declare a geomotif.motifs entry point,
    # geomotif imports what it names and calls it. examples/plugin is the
    # worked version of this; here it is simulated so the suite does not have
    # to install a second package to check the mechanism.
    registered: list[str] = []

    def register_all() -> None:
        registry.register("from-a-plugin", family="plugin")(Dot)
        registered.append("called")

    class FakeEntryPoint:
        name = "example"
        value = "example.motifs:register_all"

        def load(self):
            return register_all

    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_: [FakeEntryPoint()])
    monkeypatch.setattr(registry, "_motifs_loaded", False)

    assert "from-a-plugin" in registry.names()
    assert registered == ["called"]
    assert registry.describe("from-a-plugin").family == "plugin"
    # ...and the builtins are still there, so a plugin adds rather than replaces.
    assert "spiral.between" in registry.names()


def test_a_plugin_that_fails_to_load_says_which_one(monkeypatch):
    class BrokenEntryPoint:
        name = "broken"
        value = "nowhere:register_all"

        def load(self):
            raise ImportError("no module named 'nowhere'")

    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_: [BrokenEntryPoint()])
    monkeypatch.setattr(registry, "_motifs_loaded", False)

    with pytest.raises(RuntimeError, match="broken"):
        registry.names()
