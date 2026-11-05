# Release a new version

A release gives Gentrex a version number that people can cite and come back
to. It is a git tag, such as `v0.2.0`, on a commit of `master`, and a GitHub
release with the notes from the [changelog](../CHANGELOG.md). Zenodo, a
research archive run by CERN, then keeps a copy of the code and gives the
version a DOI. JOSS, the Journal of Open Source Software, asks for such an
archived version with a DOI, and other journals increasingly do too.

## Before you start

You need:

- The right to push to the repository on GitHub, and the GitHub CLI `gh`,
  logged in. `gh auth status` says whether it is.
- Every change for the release committed and pushed to `master`, with CI
  passed on the last commit.
- The repository switched on in Zenodo. You do this once. Zenodo archives
  only the releases that you create after that. Log in to
  [Zenodo](https://zenodo.org) with your GitHub account, click the profile
  menu in the header, then **GitHub**, then **Sync now**, and switch on the
  slider of the repository.

## Step 1: Choose the version number

A version number has three parts, MAJOR.MINOR.PATCH, as in `0.2.0`. While
Gentrex is below 1.0, raise MINOR for a release with new features, or with
changes that users must act on, such as a new version of the tables of
`gentrex load`. Raise PATCH for a release that only fixes bugs.

Raise the version with uv:

```bash
uv version --bump minor
```

`--bump patch` raises PATCH instead. uv writes the new version into
`pyproject.toml` and `uv.lock`, and prints the change, as in
`gentrex 0.1.0 => 0.2.0`. `uv run gentrex --version` then prints the new
version.

The first release, 0.1.0, skips this step, because `pyproject.toml` already
has that version.

## Step 2: Update the changelog and the citation file

In `docs/CHANGELOG.md`, rename the heading `## Unreleased` to the new
version, such as `## 0.2.0`. The changes listed under it become the notes of
the release in step 5. For the first release, the heading `## 0.1.0` is
already there.

In `CITATION.cff`, in the root of the repository, set `version` to the new
version and `date-released` to the date of the release. Add `date-released`
if the file has none yet:

```yaml
version: 0.2.0
date-released: 2026-11-20
```

Zenodo takes the title, the authors, the version and the license of its
record from this file. GitHub shows the file as the **Cite this repository**
button on the repository's page.

## Step 3: Commit and push

```bash
git commit -am "[release] gentrex 0.2.0"
git push
```

`-a` commits every changed file that git already tracks, so it takes
`pyproject.toml`, `uv.lock`, the changelog and `CITATION.cff` together. Wait
until CI passes on this commit. `gh run watch` follows the run in the
terminal until it ends.

## Step 4: Tag the commit

```bash
git tag -a v0.2.0 -m "Gentrex 0.2.0"
git push origin v0.2.0
```

- `-a` makes an annotated tag, which records who made it and when, with the
  message after `-m`.
- The `v` before the number is the usual way to name a version tag on
  GitHub.

## Step 5: Create the GitHub release

Copy the notes of the version from the changelog into a file, and create the
release with them:

```bash
awk '/^## 0.2.0$/ {found = 1; next} /^## / {found = 0} found' docs/CHANGELOG.md > release-notes.md
gh release create v0.2.0 --verify-tag --title "Gentrex 0.2.0" --notes-file release-notes.md
rm release-notes.md
```

- `awk` prints the lines between the heading `## 0.2.0` and the next
  heading.
- `--verify-tag` stops if the tag of step 4 isn't on GitHub. Without it,
  `gh` would create the tag itself, on the newest commit of `master`.
- `--title` and `--notes-file` set the name and the text of the release.

## Check the result

The release appears on the **Releases** page of the repository on GitHub,
with its notes and the code to download.

Within a few minutes, Zenodo archives it. The record appears on the
**GitHub** page of your Zenodo profile, with a DOI for this version. The
record's own page also gives a DOI that stands for all versions and always
leads to the newest one. After the first release, add that DOI to
`CITATION.cff`, so that the **Cite this repository** button shows it:

```yaml
doi: 10.5281/zenodo.1234567
```

Commit and push the change. Later releases need no new DOI in
`CITATION.cff`, because this one leads to each of them.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `gh release create` stops because the tag doesn't exist on GitHub. | Push the tag, as step 4 shows, and run step 5 again. |
| Zenodo has no record of the release. | The repository wasn't switched on in Zenodo before the release. Switch it on, as [Before you start](#before-you-start) shows. Then delete the GitHub release with `gh release delete v0.2.0`, which keeps the tag, and create it again with step 5. |
| The tag is on the wrong commit, and Zenodo has no record of it. | Delete the release and the tag on GitHub with `gh release delete v0.2.0 --cleanup-tag`, and the tag in your clone with `git tag -d v0.2.0`. Then tag the right commit, from step 4. |
| A version that Zenodo has archived has a mistake. | Zenodo keeps every version it has published. Release the fix as the next version, such as 0.2.1. |
