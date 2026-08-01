"""The documentation generator, and the committed files it is responsible for.

Two of the things it writes are committed -- `docs/catalog.md` and the images
the README leads with -- because GitHub renders a README without ever running
mkdocs. Committed and generated is exactly the combination that goes stale, so
the drift check lives here as well as in `make docs-check`: a motif added,
renamed or re-exampled without regenerating fails the suite.
"""

from __future__ import annotations

import pathlib

import pytest

import gendocs
from geomotif.core import registry

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

#: The committed catalog describes this repository's own motifs on a machine
#: that can build all of them. Without the optional extras it would gain
#: "(needs scipy)" notes, and with a plugin installed it would gain that
#: plugin's motifs -- in either case the comparison below would be measuring
#: the environment rather than the code.
_INFOS = [registry.describe(name) for name in registry.names()]
describes_this_repository = pytest.mark.skipif(
    not all(info.available and info.cls.__module__.startswith("geomotif.") for info in _INFOS),
    reason="the registry here is not the builtin catalog: an extra is missing, or a plugin is installed",
)


@describes_this_repository
def test_the_committed_catalog_is_up_to_date(tmp_path):
    fresh = tmp_path / "catalog.md"
    list(gendocs._catalog(fresh))
    assert fresh.read_text() == (DOCS / "catalog.md").read_text(), (
        "docs/catalog.md is behind the registry; run `make docs-gen`"
    )


def test_the_committed_readme_images_are_up_to_date(tmp_path):
    list(gendocs._hero(tmp_path))
    for name in gendocs.HERO:
        fresh = tmp_path / f"{name}.svg"
        assert fresh.read_text() == (DOCS / "assets" / f"{name}.svg").read_text(), (
            f"docs/assets/{name}.svg is behind the code; run `make docs-gen`"
        )


def test_every_hero_image_is_a_registered_motif():
    for name in gendocs.HERO:
        registry.describe(name)


def test_every_public_module_gets_a_reference_page(tmp_path):
    list(gendocs._reference(tmp_path))
    pages = {path.name for path in tmp_path.iterdir()}
    assert "index.md" in pages
    assert "core.sampling.md" in pages
    assert "motifs.spirals.md" in pages
    assert (tmp_path / "core.types.md").read_text() == "::: geomotif.core.types\n"


def test_private_modules_stay_out_of_the_reference():
    modules = list(gendocs._public_modules())
    assert "geomotif.motifs._common" not in modules
    assert "geomotif.__main__" not in modules
    assert "geomotif.motifs.spirals" in modules


def test_writing_the_same_content_twice_changes_nothing(tmp_path):
    target = tmp_path / "page.md"
    assert list(gendocs._write(target, "hello\n")) == [target]
    assert list(gendocs._write(target, "hello\n")) == []


def test_a_file_nothing_generates_any_more_is_pruned(tmp_path):
    stale = tmp_path / "removed-motif.svg"
    stale.write_text("<svg/>")
    kept = tmp_path / "kept.svg"
    kept.write_text("<svg/>")

    assert list(gendocs._prune(tmp_path, {"kept.svg"})) == [stale]
    assert not stale.exists()
    assert kept.exists()


def test_a_union_type_survives_a_table_cell():
    # A literal pipe would split the row into two columns, and the backslash
    # escape is taken literally inside a code span.
    assert gendocs._code("int | None") == "<code>int &#124; None</code>"


def test_rst_markup_becomes_markdown():
    assert gendocs._md("The rhodonea ``r = cos(theta)``.") == "The rhodonea `r = cos(theta)`."
    assert (
        gendocs._md("See :class:`~geomotif.PolarMotif` for more.") == "See `PolarMotif` for more."
    )


def test_a_family_page_documents_every_motif_in_the_family():
    infos = [registry.describe(name) for name in registry.names(family="spiral")]
    page = gendocs._family_page("spiral", infos)
    for info in infos:
        assert f"## `{info.name}`" in page
        assert f"geomotif render {info.name}" in page


def test_a_motif_whose_example_is_plain_data_gets_a_constructor_call():
    page = gendocs._python(registry.describe("rose"))
    assert "from geomotif.motifs import Rose" in page
    assert "motif = Rose(" in page


def test_an_unreadably_long_example_falls_back_to_the_registry():
    # voronoi.cells is parameterized by three dozen scattered points: sayable,
    # and a line of code nobody would read.
    assert gendocs._call(registry.describe("voronoi.cells")) is None


def test_a_motif_whose_example_holds_objects_falls_back_to_the_registry():
    page = gendocs._python(registry.describe("mandala"))
    assert "registry.create" in page
    assert "Mandala(" not in page


def test_a_motif_that_cannot_be_serialized_says_so_instead_of_raising():
    assert "no spec" in gendocs._spec(registry.describe("polar.expression"))


def test_a_function_default_does_not_carry_its_address():
    # A function reprs as `<function _ripple at 0x7f...>`; putting that in a
    # table would make the page differ between two runs of the same code.
    page = gendocs._family_page("string-art", [registry.describe("string-art.envelope")])
    assert "0x" not in page
    assert "a function" in page


def test_two_runs_of_the_generator_write_the_same_bytes(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    list(gendocs._catalog(first / "catalog.md"))
    list(gendocs._catalog(second / "catalog.md"))
    assert (first / "catalog.md").read_text() == (second / "catalog.md").read_text()
