# Contributing to Gentrex

## Report a problem

Open an issue on GitHub with the command you ran, what you expected and what
happened. Copy the error from `log.txt` in the run folder.

Never attach a report, a record, a log or a screenshot from a real patient,
because they hold patient data. Describe the problem with synthetic values,
such as `SYN-MRN-0001`, instead.

## Change Gentrex

1. Set up Gentrex and run the checks as [Development](development.md)
   shows. ruff checks the lint and the format, basedpyright checks the types,
   and pytest runs the tests. CI runs the same checks on every push and pull
   request.
2. Follow the rules in [AGENTS.md](../../AGENTS.md). They cover how to write
   tests, the Python style and how to write the documentation. The Python
   style is the Google Python Style Guide, with lines of at most 88
   characters and Google-style docstrings.
3. Add or change a test for each change in behavior, and update the page in
   `docs/` that describes it.
4. Describe the change in [CHANGELOG.md](../CHANGELOG.md), under a heading
   `## Unreleased` at the top.
5. Open a pull request against `master`.

Reports and results never go into the repository. Git ignores `data/` and
`results/`, and the tests use synthetic values only.

A new version comes out as [Release a new version](release.md) describes.
