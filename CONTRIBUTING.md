# Contributing to geomotif

Bug reports, new motifs and documentation fixes are all welcome. This page is
what you need to know before opening a pull request.

## Getting set up

```bash
git clone https://github.com/pianosuki/geomotif && cd geomotif
make install                    # uv sync --group dev --group plotter
make check                      # ruff, ruff-format, mypy strict, pytest
```

Without `uv`, `pip install -e . --group dev --group plotter` is the same thing.
The `plotter` group is only `vpype`, which four tests compare this library's
pen-up optimizer against — they skip themselves without it, and a skipped test
reads as a passing one.

`make check` is exactly what CI runs. It must pass before a pull request is
reviewed, and `make fix` applies everything ruff can fix on its own.

| Target | What it does |
|---|---|
| `make check` | lint, format check, type check, test — the whole gate |
| `make fix` | auto-fix lint and formatting in place |
| `make test-cov` | the suite with a coverage report |
| `make docs-serve` | the documentation site, with live reload |
| `make docs-gen` | regenerate the derived documentation |
| `make docs-check` | fail if the committed generated docs have drifted |

## Adding a motif

This is the most common contribution, and most of it is decided for you.

**1. Pick the base that matches how the shape is *defined*.** Not what it looks
like — how it is defined. A radius as a function of angle is a `PolarMotif`; a
shape defined by where its corners are is a `PolygonMotif`; a grammar drawn with
a turtle is an `LSystemMotif`. The full list is in
[docs/extending.md](docs/extending.md), and the choice that is easiest to get
wrong is `ParametricMotif` versus `PolygonMotif`: measuring a pentagon at 512
evenly spaced parameters rounds all five of its corners off, and listing them
costs five points.

**2. Write it as a frozen slotted dataclass.**

```python
@register("my-shape", family="curve", example={"k": 9.0})
@dataclass(frozen=True, slots=True)
class MyShape(PolarMotif):
    """One line saying what it is, then the prose that only prose can carry."""

    k: float = 7.0

    def radius(self, theta: float) -> float: ...
```

The field declaration is the constructor, the `describe()` output, the
generated `--flags`, the spec format and the documentation's parameter table,
all at once. Nothing about a motif is written twice, and a field is the way to
keep it that way.

**3. Choose `example=` carefully.** It is the picture everyone sees of your
motif, the parameters `geomotif render` starts from, and what the conformance
suite exercises. Prefer parameters that show the shape's character over
parameters that are round numbers.

**4. Put it in the right module.** `geomotif/motifs/<family>.py`, exported from
`geomotif/motifs/__init__.py`. The flat namespace is the published surface; the
file it lives in is not.

**5. Run the suite.** Every registered motif is parametrized into
`tests/test_conformance.py` automatically, so yours is tested the moment it is
registered — no test to opt into. It has to build a non-empty design with
finite coordinates and real extent, return exactly the count `generate(n)` asks
for, build identically twice, survive every export format, and round-trip
through a spec file. Add motif-specific tests for whatever is *interesting*
about yours: the property that makes it that shape rather than a similar one.

**6. Regenerate the documentation.** `make docs-gen`, and commit
`docs/catalog.md` and any changed image. `make docs-check` and the test suite
both fail if you forget.

If the motif is yours rather than classical, consider
[publishing it as a plugin](docs/extending.md#shipping-it-as-a-plugin) instead —
one entry point, and it is indistinguishable from a builtin.

## The house style

The codebase has a particular character, and matching it matters more than any
individual rule:

- **Comments explain *why*, never *what*.** If a line needs a comment saying
  what it does, rewrite the line. If a decision looks arbitrary, the comment
  saying why it is not is the valuable one.
- **Docstrings are NumPy-style**, and the first line is a sentence. Motif
  docstrings should say what the shape *is*, including the part everyone gets
  wrong about it if there is one.
- **Modern Python, 3.12-safe.** PEP 695 `type` aliases, `@override`, `match`
  where it genuinely reads better. ruff is pinned to the 3.12 floor so a
  newer idiom cannot slip in unnoticed.
- **Keyword-only past the obvious positionals.** A call site should not have
  three bare numbers in it.
- **Errors are specific and actionable.** Say what was given, what was expected,
  and what to do — `f"count must be >= 2, got {count}"`, not `"bad count"`.
- **No `# type: ignore` without a code**, and none at all without a comment
  saying why the checker is wrong.
- **The core stays zero-dependency.** A motif that needs a package declares
  `requires=` and is listable without it. CI installs the package with no
  extras at all and runs the suite, so this is checked rather than asserted.

## Tests

Test names are sentences: `test_generate_returns_exactly_the_requested_count`.
They do not need docstrings — the name is the docstring.

Test what is *true about the thing*, not what the implementation currently
does. A test that would still pass after a rewrite is a good test; a test that
pins an incidental coordinate is a maintenance cost.

## Commits and pull requests

Keep a commit to one idea, and write the message to whoever has to understand
the change in a year — what it does, and why that was the right way. Reference
an issue if there is one.

Every user-visible change needs a `CHANGELOG.md` entry under `[Unreleased]`,
in the Keep a Changelog category it belongs to.

## Releasing

Maintainers only:

1. Move `[Unreleased]` to the new version with today's date.
2. Bump `__version__` in `src/geomotif/__init__.py`.
3. `make check && make docs-check`.
4. Tag `vX.Y.Z` and push it. The publish workflow builds, checks that the tag
   and `__version__` agree, and uploads to PyPI through trusted publishing.

What the version number promises is written down in
[docs/api-policy.md](docs/api-policy.md).
