**What this changes, and why**

**Checklist**

- [ ] `make check` passes (ruff, ruff-format, mypy strict, pytest)
- [ ] Tests cover what is *interesting* about the change, not just its lines
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`
- [ ] `make docs-gen` was run and the result committed, if a motif was added,
      renamed or re-exampled
- [ ] The core is still zero-dependency, or the new dependency is behind an
      extra and declared with `requires=`

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the house style.
