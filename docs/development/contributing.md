# Contributing to Gentrex

## Report a problem

Open an issue on GitHub with the command you ran, what you expected and what
happened. Copy the error from `log.txt` in the run folder, and replace
anything in it that comes from a report, like a file name, with a synthetic
value.

Never attach a report, a record, a log or a screenshot from a real patient,
because they contain patient data. Describe the problem with synthetic
values like `SYN-MRN-0001` instead.

## Change Gentrex

1. Set up Gentrex and run the checks in [Development](development.md). CI
   runs the same checks for every push to `master` and every pull request.
2. Follow the rules in [AGENTS.md](../../AGENTS.md) for tests, Python style
   and documentation. The Python style is the Google Python Style Guide, with
   lines of at most 88 characters and Google-style docstrings.
3. Add or change a test for each change in behavior, and update the page in
   `docs/` that describes it.
4. Describe the change in [CHANGELOG.md](../CHANGELOG.md), under a heading
   `## Unreleased` at the top.
5. Open a pull request against `master`.

Reports and results never go into the repository. Git ignores `data/` and
`results/`, and the tests use synthetic values only.

To publish a new version, follow [Release a new version](release.md).
