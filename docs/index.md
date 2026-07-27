# geomotif

A library for generating and plotting geometric designs, with true arc-length
point placement and pluggable spacing curves.

These docs are scaffolding. The full site — MkDocs Material, an API reference
generated from the docstrings, and an auto-generated motif gallery — is built
in Phase 5 of the refactor. Until then, [the README](../README.md) is the
current reference.

## Planned pages

| Page | Contents |
|---|---|
| `extending.md` | Writing your own motif: choosing a base from `geomotif.bases` (in particular when a shape is *measured* rather than *listed*), the conformance contract every registered motif must meet, and how to publish one as a plugin |
| `api-policy.md` | The public-vs-internal boundary, and what `__all__` does and does not promise |
| `gallery/` | Every registered motif, rendered to SVG with its source snippet (generated; not committed) |
