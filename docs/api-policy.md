# What is public, and what changes

geomotif follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
This page says precisely what the version number is a promise *about*.

## The boundary

**Public** is anything reachable by a name that does not begin with an
underscore, exported from a module's `__all__`, and documented in [the
reference](reference/index.md). Concretely:

- `geomotif` — the core model, the motif bases, the spacing curves, the
  transform layer, the registry and the I/O functions.
- `geomotif.motifs` and `geomotif.compose` — the motif catalogue, as a flat
  namespace each.
- `geomotif.bases`, `geomotif.core.*`, `geomotif.io.*`, `geomotif.plotting`,
  `geomotif.cli`.
- The `geomotif` command and its options.
- The `geomotif.motifs` entry-point group.
- The spec file format.

**Internal** is everything else, including:

- any name beginning with `_`, at any depth — `geomotif.motifs._common`,
  `geomotif.io.points._rounder`, a motif's private helpers;
- the *module* a motif class happens to be defined in. Import `GoldenSpiral`
  from `geomotif.motifs`, not from `geomotif.motifs.spirals`; the flat
  namespace is the published surface and the file layout is not;
- the exact point count `build()` returns for a curve, and the exact vertex
  positions along it. What is promised is a polyline that is smooth at
  plotting resolution and correct where it is *defined* — its corners, its
  endpoints, its closure;
- the formatting of anything written for a human: `geomotif list` output,
  error message wording, docstring prose.

`__all__` is curated in every module rather than generated. If a name is in it,
it is meant for you.

## What a major version protects

Within a major version, none of these breaks:

- **Import paths.** A public name keeps working from where it worked.
- **Call signatures.** Parameters are not removed, reordered or renamed.
  Keyword-only arguments may be *added* with defaults that preserve behaviour.
- **Registry names.** `spiral.golden` stays `spiral.golden`, and a motif is not
  removed.
- **Spec files.** A spec written by 1.x loads in every later 1.x. The
  `"geomotif"` key records the writing version for information; nothing is
  refused on a mismatch.
- **Export formats.** A file that parsed keeps parsing. Precision defaults and
  whitespace may change; structure does not.
- **The extension contract.** A motif that satisfies the conformance suite in
  1.x still does in 1.y.

A new motif, a new spacing curve, a new keyword argument with a
behaviour-preserving default, and a new export format are all **minor**
releases. Anything that would make correct 1.x code stop working is **major**.

## What deliberately is not protected

Floating-point output is not bit-stable across versions. A fix to a sampling
or clipping edge case can move a coordinate in the last few decimals. If you
need a byte-identical file from one version to the next, pin the version — that
is what pinning is for. What *is* stable within a run and across machines is
reproducibility: building the same motif twice gives identical output, and a
resolved random seed is recorded in the design's `meta`.

Optional extras (`plot`, `scipy`) can change their minimum versions in a minor
release. The core's dependency list is empty and stays that way — that is a
promise, and CI checks it on every push by installing the package with no
extras and running the suite.

## Deprecation

A public name that is going away is deprecated for at least one minor release
before it is removed, with a `DeprecationWarning` that names the replacement.
Removals happen in major releases only, and the changelog lists every one.

## Python versions

The floor is **3.12**, and 3.12, 3.13 and 3.14 are tested on Linux, macOS and
Windows on every push. Raising the floor is a minor release, not a major one:
dropping an interpreter that is out of support does not break code, only
installations, and pip resolves that correctly on its own.
