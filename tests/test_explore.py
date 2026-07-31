import re
from html.parser import HTMLParser

import pytest

from geomotif.core import registry
from geomotif.explore import save_html, sweeps_for, to_html


class Page(HTMLParser):
    """The parts of an explorer page a test needs to ask about."""

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def find(self, tag, **attrs):
        return [
            found
            for name, found in self.tags
            if name == tag and all(found.get(k) == v for k, v in attrs.items())
        ]

    @property
    def sliders(self):
        return [attrs for attrs in self.find("input") if attrs.get("type") == "range"]

    @property
    def frames(self):
        return [attrs for _, attrs in self.tags if "frame" in (attrs.get("class") or "").split()]


def page(*names, **kwargs):
    return Page(to_html(list(names), **kwargs))


# --- the sweeps -------------------------------------------------------------


def test_a_slider_is_offered_for_every_number_a_slider_can_move():
    sweeps = {sweep.parameter for sweep in sweeps_for(registry.describe("rose"), steps=5)}
    assert {"n", "d", "size"} <= sweeps


def test_a_parameter_a_slider_has_no_axis_for_is_left_alone():
    sweeps = {sweep.parameter for sweep in sweeps_for(registry.describe("rose"), steps=5)}
    assert "center" not in sweeps  # a point has two axes, and a slider has one


def test_a_number_with_no_default_gets_no_slider():
    # `resolution` defaults to None and means "work it out", so there is no
    # scale to build a range from -- and guessing gives a slider from 1 to 2.
    sweeps = {sweep.parameter for sweep in sweeps_for(registry.describe("rose"), steps=5)}
    assert "resolution" not in sweeps


def test_a_boolean_gets_the_two_values_it_has():
    sweeps = {s.parameter: s for s in sweeps_for(registry.describe("modular.multiplication"))}
    assert sweeps["merge"].values == (False, True)


def test_the_slider_starts_where_the_motif_itself_does():
    info = registry.describe("rose")
    declared = {param.name: info.example.get(param.name, param.default) for param in info.params}
    for sweep in sweeps_for(info, steps=9):
        assert sweep.values[sweep.start] == declared[sweep.parameter]


def test_a_value_the_motif_refuses_is_dropped_rather_than_reported():
    # Sweeping walks off the end of what a motif accepts routinely -- a
    # modulus of one, a polygon of two sides -- and that is data about the
    # motif, not an error in the page.
    sweeps = {s.parameter: s for s in sweeps_for(registry.describe("polygon.regular"), steps=9)}
    assert all(isinstance(value, int) and value >= 3 for value in sweeps["sides"].values)


def test_every_frame_is_an_svg_that_can_sit_in_a_page():
    for sweep in sweeps_for(registry.describe("circle"), steps=3):
        for image in sweep.images:
            assert image.startswith("<svg")
            assert "<?xml" not in image  # only legal at the very start of a file


# --- the page ---------------------------------------------------------------


def test_the_page_is_one_file_with_nothing_to_fetch():
    markup = to_html(["rose"], steps=3)
    assert markup.startswith("<!DOCTYPE html>")
    assert 'src="' not in markup
    assert "http://" not in markup.replace("http://www.w3.org/2000/svg", "")


def test_every_slider_has_a_frame_for_every_value_it_offers():
    parsed = page("rose", steps=5)
    for slider in parsed.sliders:
        parameter = slider["data-param"]
        offered = int(slider["max"]) + 1
        assert len(slider["data-values"].split(",")) == offered
        drawn = [frame for frame in parsed.frames if frame["data-param"] == parameter]
        assert len(drawn) == offered
        assert sorted(int(frame["data-index"]) for frame in drawn) == list(range(offered))


def test_exactly_one_frame_is_showing_to_begin_with():
    parsed = page("rose", "fractal.koch-snowflake", steps=3)
    showing = [frame for frame in parsed.frames if "on" in frame["class"].split()]
    assert len(showing) == 2  # one per motif, and only one motif is visible


def test_several_motifs_get_a_picker_and_one_gets_none():
    assert page("rose", "circle", steps=3).find("button")
    assert not page("rose", steps=3).find("button")


def test_the_picker_names_every_motif_on_the_page():
    parsed = page("rose", "circle", steps=3)
    assert [button["data-motif"] for button in parsed.find("button")] == ["rose", "circle"]
    assert [section["id"] for section in parsed.find("section")] == ["rose", "circle"]


def test_the_page_says_which_parameters_it_is_holding_still():
    markup = to_html(["rose"], steps=3)
    assert "Held at the example" in markup
    assert "center" in markup.split("Held at the example")[1]


def test_the_script_only_reaches_for_things_the_markup_has():
    # The page is generated in two halves that have to agree about their own
    # attribute names; nothing else would catch a rename of one of them.
    markup = to_html(["rose", "circle"], steps=3)
    for attribute in re.findall(r"dataset\.(\w+)", markup):
        kebab = "data-" + re.sub(r"(?<=[a-z])(?=[A-Z])", "-", attribute).lower()
        assert kebab in markup, f"the script reads {kebab}, which nothing writes"


def test_a_motif_that_cannot_be_swept_says_so():
    # The composers take whole motifs as parameters; there is no axis in that.
    with pytest.raises(ValueError, match="slider cannot move"):
        to_html(["mandala"])


def test_exploring_nothing_is_refused():
    with pytest.raises(ValueError, match="name at least one motif"):
        to_html([])


def test_too_few_steps_to_sweep_is_refused():
    with pytest.raises(ValueError, match="steps must be >= 2"):
        to_html(["rose"], steps=1)


def test_an_unknown_motif_is_reported_by_the_registry():
    with pytest.raises(KeyError):
        to_html(["not-a-motif"])


def test_the_page_is_written(tmp_path):
    target = save_html(["rose"], tmp_path / "rose.html", steps=3)
    assert target.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_resampling_keeps_the_page_small():
    dense = len(to_html(["fractal.koch-snowflake"], steps=3))
    sparse = len(to_html(["fractal.koch-snowflake"], steps=3, samples=200))
    assert sparse < dense / 2
