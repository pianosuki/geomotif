# Writing your own motif

The library is arranged so that adding a shape is nearly always *the maths and
nothing else*. Everything downstream — arc-length resampling, every spacing
curve, the transform layer, SVG/DXF/CSV/TXT/JSON export, spec serialization,
command-line flags, lookup by name, the conformance suite — comes from the base
class and the registry, not from anything you write.

## Three tiers

### Tier 1 — pick a base and write one method

This covers almost everything. Choose the base that matches how your design is
*defined*, not what it looks like:

| Base | You implement | For |
|---|---|---|
| [`PolarMotif`][geomotif.bases.PolarMotif] | `radius(theta) -> float` | a radius as a function of angle |
| [`ParametricMotif`][geomotif.bases.ParametricMotif] | `position(u) -> Point` | one curve from one parameter |
| [`MultiCurveMotif`][geomotif.bases.MultiCurveMotif] | `curves() -> Iterable[Curve]` | several strands at once |
| [`PolygonMotif`][geomotif.bases.PolygonMotif] | `outlines() -> Iterable[Sequence[Point]]` | shapes defined by their corners |
| [`SegmentMotif`][geomotif.bases.SegmentMotif] | `nodes()` and `edges()` | anything that is points joined by lines |
| [`LSystemMotif`][geomotif.bases.LSystemMotif] | `axiom`, `rules`, `angle` | a grammar drawn with a turtle |
| [`LatticeTiling`][geomotif.bases.LatticeTiling] | `cell()` and `basis()` | a cell repeated on two vectors |
| [`SubstitutionTiling`][geomotif.bases.SubstitutionTiling] | `seed()`, `subdivide()`, `outline()` | tiles that subdivide into smaller tiles |

```python
import math
from dataclasses import dataclass

from geomotif import PolarMotif, register


@register("my-flower", family="polar")
@dataclass(frozen=True, slots=True)
class MyFlower(PolarMotif):
    """A seven-lobed flower with a ripple on it."""

    k: float = 7.0

    def radius(self, theta: float) -> float:
        return math.sin(self.k * theta) + 0.4 * math.cos(17 * theta)
```

Six lines of substance. That class now resamples by arc length, takes every
spacing curve, transforms, exports to five formats, serializes to a spec, and
answers to `registry.create("my-flower", k=5)` and
`geomotif render my-flower --k 5 --out flower.svg`.

!!! important "`ParametricMotif` versus `PolygonMotif`"

    This is the one choice that is easy to get wrong. A curve is **measured**
    at evenly spaced parameters; a polygon is **listed**. Sampling a pentagon at
    512 parameters rounds all five of its corners off unless a sample happens to
    land on each one — and listing them costs five points. If your shape is
    defined by where its corners are, it is a `PolygonMotif`.

### Tier 2 — subclass `Motif` and write `build()`

When none of the bases describes what you are drawing, implement the one method
they all eventually call:

```python
from dataclasses import dataclass

from geomotif import Design, Motif, Path, register


@register("zigzag", family="primitive")
@dataclass(frozen=True, slots=True)
class Zigzag(Motif):
    """A zigzag of `teeth` triangles."""

    teeth: int = 5
    height: float = 10.0

    def build(self) -> Design:
        points = tuple((float(i), self.height if i % 2 else 0.0) for i in range(self.teeth * 2 + 1))
        return Design((Path(points),))
```

### Tier 3 — do not inherit at all

Anything with a `build() -> Design` method satisfies the
[`SupportsBuild`][geomotif.core.motif.SupportsBuild] protocol and is accepted
everywhere a motif is, including as the unit of a composer. You lose the
inherited `generate()`, and nothing else.

## Why a frozen dataclass

Registering a motif is the decorator; making it a frozen slotted dataclass is
what makes everything else possible. One field declaration becomes, at once:

- the constructor;
- `describe(name).params` — names, types, defaults;
- the generated `--flags` on the command line;
- the keys of the spec file;
- the parameter table in this documentation;
- the value's `repr`, equality and hashability.

`frozen=True` because a motif is a value, and `slots=True` because a motif is
small and you may make thousands of them. Both are worth having; note that a
single class without `__slots__` anywhere in the MRO silently hands every
instance a `__dict__` back, which is why `Motif` itself declares empty slots.

## What `@register` gives you, and asks for

```python
@register("my-flower", family="polar", requires=None, example={"k": 9.0})
```

| Argument | Meaning |
|---|---|
| `name` | Registry key. Derived from the class name in kebab-case if omitted, so `GoldenSpiral` becomes `golden-spiral`. |
| `family` | The grouping used by `geomotif list` and the gallery. |
| `requires` | The name of an optional dependency. A motif that declares one can still be listed, described and serialized without it — only building raises. |
| `example` | The parameters the gallery renders, the CLI starts from, and the conformance suite exercises. |

`example=` is worth choosing carefully. It is the picture everyone sees of your
motif and the starting point for anyone who changes one flag.

One name is reserved: a parameter called `motif` is refused at registration,
because a design's `meta` records the motif name under that key and the
parameter would overwrite it.

## The conformance contract

Every registered motif is parametrized into the same suite, which means yours is
checked the moment it appears in the registry — nothing to opt into. It asserts
that a motif:

- instantiates from its own `example`;
- builds a non-empty design with finite coordinates and actual extent;
- does not repeat the seam point on a closed path;
- returns *exactly* the requested count from `generate(n)`, and supports
  `step=`;
- builds identically twice, so it is reproducible;
- round-trips its `meta` through the registry;
- survives transform, fit, resample and overlay;
- exports to every format and comes back with the same strokes;
- round-trips through a spec file;
- has a docstring and a well-formed name.

That list is the actual promise the library makes about a motif. It is worth
reading it as a specification of what you are signing up for.

## Shipping it as a plugin

One entry point in your `pyproject.toml` is the whole contract:

```toml
[project.entry-points."geomotif.motifs"]
my_motifs = "my_package:register_all"
```

geomotif reads that group the first time anything touches its registry, imports
what each entry names, and calls it. Discovery is lazy, so a plugin nobody uses
costs nothing to have installed.

```python
# my_package/__init__.py
def register_all() -> None:
    """Entry-point hook. Importing this module is what registers the motifs."""
```

The hook is usually empty, because the `@register` decorators have already run
by the time it is called — importing the module is the whole mechanism. It
still earns its place: it is the name that forces the import, and it is where a
plugin whose motifs are spread over several modules imports the rest of them.

Once installed, your motif is indistinguishable from a builtin. `geomotif list`
shows it, `geomotif show` documents it, `geomotif render` renders it with flags
generated from your fields, it serializes to a spec, and the conformance suite
runs against it.

!!! example "A complete worked plugin"

    [`examples/plugin/`](https://github.com/pianosuki/geomotif/tree/main/examples/plugin)
    in the repository is Gielis's superformula as a real installable package —
    about forty lines, one entry point, one decorator, one method. It passes all
    17 conformance checks, and CI installs it into a clean environment on every
    push to prove the discovery half works outside the test suite.

## A note on numerical honesty

If your shape has cusps — points where the radius has infinite slope — no
sampling resolution resolves them. Raise the count and every tip lengthens
together without any of them converging. That is the shape being honest about
itself rather than a bug, and it is worth saying so in your docstring rather
than papering over it, the way the superformula example does.

More generally: `resolution` counts **segments**, not points, so a strand comes
back with one more point than that. For a shape with `m`-fold symmetry, any
multiple of `m` puts a sample on every corner at once.
