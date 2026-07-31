"""The README's claims about the catalogue, checked against the catalogue.

The README is hand-written, and it quotes numbers -- how many motifs, how many
families, how many in each. Those are exactly the sentences that quietly become
false, so they are asserted here rather than trusted.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from geomotif.core import registry

README = pathlib.Path(__file__).resolve().parent.parent / "README.md"

#: A row of the README's family table: one or more bolded family names, then a
#: count. ``| **polar**, **harmonic** | 7 | ...``
_ROW = re.compile(r"^\| ((?:\*\*[a-z-]+\*\*(?:, )?)+) \| +(\d+) \|", re.MULTILINE)


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def test_the_stated_totals_are_the_real_ones(readme):
    match = re.search(r"\*\*(\d+) motifs in (\d+) families\*\*", readme)
    assert match, "the README no longer states its motif and family counts"
    assert int(match.group(1)) == len(registry.names())
    assert int(match.group(2)) == len(registry.families())


def test_the_family_table_covers_every_family_exactly_once(readme):
    listed = [family for row in _ROW.findall(readme) for family in _families(row[0])]
    assert sorted(listed) == sorted(registry.families())


def test_every_family_row_states_its_real_size(readme):
    for names, count in _ROW.findall(readme):
        families = _families(names)
        actual = sum(len(registry.names(family=family)) for family in families)
        assert int(count) == actual, f"{'+'.join(families)} has {actual} motifs, not {count}"


def test_the_hero_images_the_readme_shows_are_committed(readme):
    for source in re.findall(r'<img src="(docs/assets/[^"]+)"', readme):
        assert (README.parent / source).is_file(), f"{source} is missing"


def test_the_version_in_the_spec_example_is_the_current_one(readme):
    from geomotif import __version__

    assert f'"geomotif": "{__version__}"' in readme


# --- the documentation's own front page -------------------------------------
#
# docs/index.md quotes the same numbers and is written by hand, unlike the
# catalogue beside it. Nothing was checking it, and it spent a release saying
# 146 across 18.

INDEX = README.parent / "docs" / "index.md"


@pytest.fixture(scope="module")
def index() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_the_front_page_states_the_real_totals(index):
    match = re.search(r"\[(\d+) motifs\]\(catalogue\.md\) across (\d+) families", index)
    assert match, "docs/index.md no longer states its motif and family counts"
    assert int(match.group(1)) == len(registry.names())
    assert int(match.group(2)) == len(registry.families())


def test_the_front_page_points_at_every_guide(index):
    guides = {path.name for path in (README.parent / "docs" / "guide").glob("*.md")}
    linked = set(re.findall(r"\((guide/[a-z-]+\.md)\)", index))
    assert {f"guide/{name}" for name in guides} <= linked, "a guide page nothing links to"


def _families(cell: str) -> list[str]:
    """Pull the family names out of one table cell."""
    return re.findall(r"\*\*([a-z-]+)\*\*", cell)
