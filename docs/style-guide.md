# Spelling and vocabulary

The house spelling is **American English**, everywhere -- code, comments,
docstrings, help text, tests, docs. This was not always true: the project was
written by someone more comfortable with British English, and it shipped a
mix of `colour` and `color`, `centre` and `center`, `catalogue` and `catalog`.
The API was American from the start; the prose was not. 1.2.0 makes the two
agree, and this page says how to keep them that way. The agreed replacements
are enforced as part of the test suite (see
[`tests/test_spelling.py`](https://github.com/pianosuki/geomotif/blob/main/tests/test_spelling.py)),
so a regression is a test failure, not a review comment.

## The rule that matters most: public names are expensive

Most spelling in this repository is cosmetic and can be fixed in any minor
release. **The one kind that is not is a** ***public name*** -- an identifier
that is exported in a module's `__all__`, a public parameter, a CLI flag, a
registry name, a spec key, or an export-format element. Those are governed by
[`api-policy.md`](api-policy.md): renaming one is a **breaking change** that
belongs in a major release, and per the project's deprecation rule it has to
warn for a minor first.

So when you are about to name a *public* thing, stop and check the spelling
before it ships. This is the one cost you cannot quietly pay later. An
internal variable or a docstring can be Americanized at any time; a public
`colours_in` requires a `DeprecationWarning` and a major to shed. That exact
story is the reason `colors_in` is the name now and `colours_in` lingers as a
deprecated alias.

## The agreed replacements

| Use this (American) | Not this (British) |
|---|---|
| `color`, `colors` | `colour`, `colours` |
| `center`, `centered` | `centre`, `centred` |
| `labeled` | `labelled` |
| `traveled` | `travelled` |
| `honored` | `honoured` |
| `behavior` | `behaviour` |
| `recognize` | `recognise` |
| `millimeter` | `millimetre` |
| `catalog` | `catalogue` |
| `rasterize` | `rasterise` |
| `quantize`, `quantizer` | `quantise`, `quantiser` |
| `quantization` | `quantisation` |

The `‑ize`/`‑ization` and `‑er` spellings are the same message as `color` and
`center`; a word that ends in `‑ise` in the table above is the British form of
an `‑ize` verb and should be spelled with a `z`.

## The one exception

`colours_in` is deliberately allowed to keep the British spelling, because it
is a **public name that shipped in 1.1.0**. It is a deprecated alias for
`colors_in` and will be removed in a future major release. Do not copy its
spelling anywhere else; do not rename it in a minor.

## What counts as spelling for this

The spelling rule applies to prose and identifiers alike, but only where it
cannot change behaviour. Fixing it in a docstring, a comment, a help string,
a test name, or an internal (leading-underscore) identifier is always safe.
For a public name, follow the deprecation rule instead of silently renaming.
