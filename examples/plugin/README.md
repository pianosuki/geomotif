# geomotif-superformula

A worked example of a **third-party geomotif motif**: a complete, installable
package that adds Gielis's superformula to geomotif's catalog without
geomotif knowing it exists.

Once installed, it is indistinguishable from a builtin:

```bash
geomotif list --family curve        # superformula is in the list
geomotif show superformula          # its docstring, flags and defaults
geomotif render superformula --m 7 --n1 0.2 --out star.svg
```

```python
from geomotif.core import registry

motif = registry.create("superformula", m=5.0, n1=0.3)
design = motif.generate(400)  # arc-length resampling, for free
```

## The whole contract

**One entry point.** In `pyproject.toml`:

```toml
[project.entry-points."geomotif.motifs"]
superformula = "geomotif_superformula:register_all"
```

geomotif reads that group the first time anything touches its registry,
imports what each entry names, and calls it. Discovery is lazy, so a plugin
nobody uses costs nothing to have installed.

**One decorator.** In the module:

```python
@register("superformula", family="curve", example={"m": 7.0, "n1": 0.3, ...})
@dataclass(frozen=True, slots=True)
class Superformula(PolarMotif):
    ...
```

`example=` is what the gallery renders, what the CLI starts from, and what
geomotif's conformance suite exercises. It is worth choosing a good one.

**One method.** Pick the base that matches how your shape is *defined* — a
superformula is a radius as a function of angle, so that is `PolarMotif` and
`radius(theta)`. Arc-length resampling, every spacing curve, the transform
layer, SVG/DXF/CSV/JSON export, spec serialization and CLI flags all follow
from it. See `geomotif.bases` for the others.

## What you get for free

Because the motif is a frozen dataclass, its fields drive everything at once:

- `geomotif show superformula` lists `--m`, `--n1`, `--n2`, `--n3`, `--a`,
  `--b`, `--size` with their types and defaults
- `save_spec(motif, "s.json")` writes a recipe that reloads
- `registry.describe("superformula").params` is the same data the docs use

## Installing it from this checkout

The package depends on `geomotif` the way any real plugin would. To try it
against this repository rather than a published release, install geomotif
first and then the plugin without re-resolving:

```bash
pip install -e .                            # from the repository root
pip install --no-deps ./examples/plugin
```

geomotif's conformance suite parametrizes over everything in the registry, so
once the plugin is installed it is checked alongside the builtins — finite
coordinates, reproducible builds, exact resampling counts, metadata that
round-trips, and export to every format:

```bash
pytest tests/test_conformance.py -k superformula   # 17 checks, from the repo root
```
