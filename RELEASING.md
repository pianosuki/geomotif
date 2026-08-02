# Releasing geomotif

This is the maintainer's checklist for cutting a release. Every step is here,
in the order it has to happen, with the exact command and what it is checking
for. Walk it top to bottom; nothing on it is optional, and nothing that is
not on it is required.

The short version lives in [CONTRIBUTING.md](CONTRIBUTING.md#releasing);
this is the long one, for the day you actually do it.

The version-number promise itself — what a major, minor or patch bump
*means* — is written down in [docs/api-policy.md](docs/api-policy.md). This
page does not restate it; it assumes the number is already decided.

## Before you start

A release is cut on a `release/X.Y.Z` branch and merged to `main`, and a
tag on the merge commit is what publishes. You should already be on the
release branch with the work for the version committed.

The four files that carry the version string, and have to agree:

| File | Where |
|---|---|
| `src/geomotif/__init__.py` | `__version__ = "X.Y.Z"` |
| `README.md` | the `"geomotif": "X.Y.Z"` line in the spec example |
| `docs/guide/export.md` | the `"geomotif": "X.Y.Z"` line in the spec example |
| `docs/guide/style.md` | the `"geomotif": "X.Y.Z"` line in the spec example |

`docs/catalog.md` carries the version too, but it is generated —
`make docs-gen` writes it from `__version__`, so do not edit it by hand.

## Phase 1 — Cut the release commit

The final commit on the release branch is the version stamp. The audit work
that preceded it is its own commit (or commits); the version bump is the
last thing that lands, so the history reads "work, then release" rather
than "release, then the work it releases".

- [ ] `__version__` in `src/geomotif/__init__.py` is the new version.
- [ ] The spec example in `README.md` (`"geomotif": "X.Y.Z"`) matches.
- [ ] The spec example in `docs/guide/export.md` matches.
- [ ] The spec example in `docs/guide/style.md` matches.
- [ ] `CHANGELOG.md` has a `## [X.Y.Z] — YYYY-MM-DD` section above the
      previous one, with a one-line summary and a `### Fixed` / `### Added`
      / `### Changed` subsection as the release warrants. The
      `[X.Y.Z]: …releases/tag/vX.Y.Z` link at the bottom of the file is
      added above the prior version's link.
- [ ] The commit message is `Cut X.Y.Z in the changelog`, with a body that
      names the files the bump touched. The last two releases' messages are
      the template:

      ```
      Cut X.Y.Z in the changelog

      Bump to X.Y.Z and stamp the new version across the committed
      documentation: the README's spec example, the export and style guides'
      spec examples, and the regenerated catalog. The X.Y.Z changelog entry
      gains its version link.
      ```

- [ ] `git add` the version-stamp files and `git commit`. The catalog is
      regenerated in Phase 2, so it is not in this commit yet.

## Phase 2 — Regenerate the catalog

`docs/catalog.md` is derived from `__version__` and the registry, so the
version stamp changes it. It is committed (GitHub renders the README
without running mkdocs, so the catalog cannot be a build artifact), which
means the regeneration is its own step before the pre-flight.

- [ ] `make docs-gen` — runs `tools/gendocs.py`, which rewrites
      `docs/catalog.md` with the new version string.
- [ ] `git add docs/catalog.md` and `git commit --amend --no-edit` to fold
      it into the "Cut X.Y.Z" commit. The catalog is part of the version
      stamp, not a separate concern; a reader of the commit should see the
      bump and the catalog move together.

## Phase 3 — The full pre-flight

This is everything the push to `main` will run, run locally first. CI runs
seven jobs (lint, test, bare, plotter, plugin, docs); the local gate is the
three commands below, plus a clean tree. The bare, plotter and plugin jobs
are not worth reproducing locally for a release-cut — they fail on a
packaging change or a sneaked-in hard dependency, neither of which a
version-stamp commit introduces — but they will run on the push, so the
version stamp and the docs are what you are checking.

- [ ] `make check` — ruff, ruff-format, mypy (strict), and the full pytest
      suite. 4525 tests at the time of writing; the count is in
      `tests/test_gendocs.py`'s registry-backed catalog, so it moves with
      the motif count. This is the gate CI's `lint` and `test` jobs run.
- [ ] `make docs-check` — re-runs `gendocs.py` and fails if
      `docs/catalog.md` or `docs/assets` differ from what is committed. If
      it fails, the catalog in Phase 2 was not regenerated or not amended
      in; go back and amend it.
- [ ] `make docs` — the strict mkdocs build. `strict: true` in
      `mkdocs.yml` means a broken link or a missing cross-reference is a
      build failure, not a warning, so a clean build is a real check. This
      is what CI's `docs` job runs (plus the `git diff` check above).

- [ ] `git status --porcelain` is empty (or only the untracked planning
      notes that live in the root). A dirty tree at this point means a
      check rewrote a file; find out which and amend or revert before
      pushing, because CI's `docs` job runs `git diff --exit-code` and will
      fail the push on drift.

- [ ] The version you are about to tag matches `__version__`. The publish
      workflow (`/.github/workflows/publish.yml`) exits the build if the
      tag and `__version__` disagree, which is the one check you cannot
      recover from after the tag is on PyPI. Confirm it now:

      ```bash
      grep '__version__' src/geomotif/__init__.py
      ```

## Phase 4 — Merge, tag, push

The convention is to merge the release branch into `main` with `--no-ff`, 
tag the merge commit, and push both. The tag push triggers 
`.github/workflows/publish.yml`; the `main` push triggers `ci.yml` and `docs.yml`.

- [ ] `git checkout main`
- [ ] `git pull --ff-only origin main` — make sure `main` has not moved
      under you; a non-ff pull means someone else landed work, and you need
      to rebase the release branch onto it and re-run Phase 3.
- [ ] `git merge --no-ff release/X.Y.Z -m "Merge branch 'release/X.Y.Z'"`
- [ ] `git tag -a vX.Y.Z -m "vX.Y.Z"` — the merge commit gets the tag.
      `publish.yml` strips the leading `v` to compare against `__version__`.
- [ ] `git push origin main` — triggers `ci.yml` (the seven jobs) and
      `docs.yml` (the Pages build).
- [ ] `git push origin vX.Y.Z` — triggers `publish.yml`. Watch it on the
      Actions tab: it builds the sdist and wheel, runs `twine check --strict`,
      and uploads to PyPI via OIDC trusted publishing (no API token; PyPI
      verifies the workflow's identity directly).
- [ ] `git push origin release/X.Y.Z` — for parity with the prior release
      branches, which are all still on the remote.

## Phase 5 — The GitHub Release

A tag is what publishes to PyPI; a *Release* is GitHub's surface for the
same version — the notes a reader sees at
`https://github.com/pianosuki/geomotif/releases/tag/vX.Y.Z`. The two are
separate: the tag exists the moment you push it, the Release is created
afterward, and `publish.yml` does not create it for you.

The `gh` CLI creates it from the changelog section. One command, with the
notes piped from `CHANGELOG.md` so the release page and the changelog cannot
drift:

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z" \
  --notes "$(
    awk '/^## \[X\.Y\.Z\]/{f=1} /^## \[/{if(f && !/X\.Y\.Z/) exit} f' CHANGELOG.md
  )"
```

The `awk` prints the `## [X.Y.Z]` section and stops at the next `## [`,
so the release notes are exactly the changelog entry, no trailing
versions. (Replace `X.Y.Z` in the `awk` pattern literally — the version
number, not a regex — and leave the inner `/X\.Y\.Z/` as the same literal
so the exit guard matches the right section.)

If this is the first release you have created, authenticate first:

- [ ] `gh auth status` — confirms the install and the login. If it
      reports not logged in:
- [ ] `gh auth login` — the web flow. Choose GitHub.com, HTTPS, and
      "Login with a web browser"; it prints a one-time code and opens the
      browser.

Then:

- [ ] `gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(...)"` (the
      command above).
- [ ] `gh release view vX.Y.Z --web` — opens the release page to confirm
      the notes rendered. The tag is already there (from Phase 4); this
      adds the title and the body.

### Attaching the wheel and sdist (optional)

`publish.yml` uploads the built artifacts to PyPI; the GitHub Release
does not need them. If you want the release page to carry the same
files, download them from the workflow run's `dist` artifact and attach:

```bash
gh run download <run-id> -n dist -D ./dist
gh release upload vX.Y.Z dist/*
```

This is optional and the prior releases do not do it; the PyPI page is
the canonical download, and the release page's job is the notes.

## Phase 6 — Verify

Three places to check, in the order they finish:

- [ ] **PyPI** — `https://pypi.org/p/geomotif` shows `X.Y.Z` as the latest
      version. The publish workflow's `publish` job has the URL in its
      summary. If it failed, the workflow log names the reason; trusted
      publishing's only common failure is a tag/`__version__` mismatch,
      which Phase 3 already caught.
- [ ] **GitHub Releases** — `https://github.com/pianosuki/geomotif/releases`
      lists `vX.Y.Z` with the changelog notes.
- [ ] **The docs site** — `https://pianosuki.github.io/geomotif/` shows
      the new version (the catalog page, the spec examples). The `docs.yml`
      workflow deploys on push to `main`; the Pages deployment takes a
      minute or two after the build goes green.

## When something goes wrong

A bad release that has not reached PyPI is recoverable: delete the tag
locally and on the remote (`git tag -d vX.Y.Z && git push origin :vX.Y.Z`),
fix the release branch, and re-tag. The merge commit on `main` stays — it
is harmless without the tag — but you can revert it if you prefer a clean
history.

A release that *has* reached PyPI cannot be undone — PyPI does not allow
re-uploading the same version, by design. If the wheel is broken, the only
move is a patch release (`X.Y.Z+1`) that fixes it, cut the same way as
above. This is why Phase 3 is a checklist and not a suggestion: the tag is
the last gate before a file you cannot replace.

## What you do not have to do

- **No version file edits beyond the four above.** `pyproject.toml` reads
  `__version__` from `src/geomotif/__init__.py` via `hatch.version`, so it
  does not carry the version itself.
- **No manual PyPI upload.** `publish.yml` does it through trusted
  publishing; there is no API token in the repository's secrets.
- **No manual Pages deploy.** `docs.yml` rebuilds the site from `main` on
  every push; the catalog and the spec examples update with it.
- **No release branch cleanup.** The `release/X.Y.Z` branches are kept on
  the remote, matching the prior ones; they are the history of each
  release's work.
