# Release a new version

A release gives Gentrex a version number that people can cite and come back
to. It is a git tag, such as `v0.2.0`, on a commit of `master`, and a GitHub
release with the notes from the [changelog](../CHANGELOG.md). Zenodo, CERN's
research archive, then keeps a copy of the code and gives the version a DOI.
The Journal of Open Source Software (JOSS) asks for an archived version with
a DOI, and other journals increasingly do too.

## Before you start

You need:

- Push access to the repository on GitHub, and the GitHub CLI `gh`, logged
  in. `gh auth status` tells you whether it is.
- Every change for the release committed and pushed to `master`, with CI
  passed on the last commit.
- The repository switched on in Zenodo. You do this once. Zenodo archives
  only the releases you create after that. Log in to
  [Zenodo](https://zenodo.org) with your GitHub account, open the profile
  menu in the header, click **GitHub** and then **Sync now**, and switch on
  the repository's slider.

## Step 1: Choose the version number

A version number has three parts, MAJOR.MINOR.PATCH, as in `0.2.0`. While
Gentrex is below 1.0, raise MINOR for new features or for changes that users
must act on, like a new version of the `gentrex load` tables. Raise PATCH for
a release that only fixes bugs.

Raise the version with uv:

```bash
uv version --bump minor
```

For a bug-fix release, use `--bump patch`. uv writes the new version into
`pyproject.toml` and `uv.lock` and prints the change, as in
`gentrex 0.1.0 => 0.2.0`. `uv run gentrex --version` then prints the new
version.

Skip this step for the first release, 0.1.0, because `pyproject.toml`
already has that version.

## Step 2: Update the changelog and the citation file

In `docs/CHANGELOG.md`, rename the heading `## Unreleased` to the new
version, such as `## 0.2.0`. The changes under it become the release notes in
step 5. For the first release, the heading `## 0.1.0` is already there.

In `CITATION.cff` in the root of the repository, set `version` to the new
version and `date-released` to the release date. Add `date-released` if the
file doesn't have it yet:

```yaml
version: 0.2.0
date-released: 2026-11-20
```

Zenodo takes the title, authors, version and license of its record from this
file. GitHub shows it as the **Cite this repository** button on the
repository's page.

## Step 3: Commit and push

```bash
git commit -am "[release] gentrex 0.2.0"
git push
```

`-a` commits every changed file that git already tracks, which here means
`pyproject.toml`, `uv.lock`, the changelog and `CITATION.cff`. Wait until CI
passes on this commit. `gh run watch` follows the run in the terminal until
it ends.

## Step 4: Tag the commit

```bash
git tag -a v0.2.0 -m "Gentrex 0.2.0"
git push origin v0.2.0
```

`-a` makes an annotated tag, which records who made it and when, along with
the message after `-m`.

## Step 5: Create the GitHub release

Copy the version's notes from the changelog into a file, and create the
release with them:

```bash
awk '/^## 0.2.0$/ {found = 1; next} /^## / {found = 0} found' docs/CHANGELOG.md > release-notes.md
gh release create v0.2.0 --verify-tag --title "Gentrex 0.2.0" --notes-file release-notes.md
rm release-notes.md
```

`awk` writes the lines between the heading `## 0.2.0` and the next heading
into `release-notes.md`. `--verify-tag` makes `gh` stop if the tag from step 4
isn't on GitHub. Without it, `gh` would create the tag itself, on the newest
commit of `master`.

## Check the result

The release appears on the repository's **Releases** page on GitHub, with
its notes and the code to download.

Within a few minutes, Zenodo archives it. The record appears on the
**GitHub** page of your Zenodo profile, with a DOI for this version. The
record's own page also has a DOI for all versions, which always leads to the
newest one. After the first release, add that DOI to `CITATION.cff`, so the
**Cite this repository** button shows it:

```yaml
doi: 10.5281/zenodo.1234567
```

Commit and push the change. Later releases don't need a new DOI in
`CITATION.cff`, because this one leads to each of them.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `gh release create` stops because the tag doesn't exist on GitHub. | Push the tag (step 4) and run step 5 again. |
| Zenodo has no record of the release. | The repository wasn't switched on in Zenodo before the release. Switch it on ([Before you start](#before-you-start)). Then delete the GitHub release with `gh release delete v0.2.0`, which keeps the tag, and create it again with step 5. |
| The tag is on the wrong commit, and Zenodo has no record of it. | Delete the release and the tag on GitHub with `gh release delete v0.2.0 --cleanup-tag`, and the tag in your clone with `git tag -d v0.2.0`. Then go back to step 4 and tag the right commit. |
| A version that Zenodo has archived has a mistake. | Zenodo keeps every version it has published. Release the fix as the next version, such as 0.2.1. |
