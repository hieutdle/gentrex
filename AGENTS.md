# Agent Instructions for gentrex

> These instructions apply to **all** AI-assisted contributions to `gentrex`.

## 1. Development Workflow

- **Never use system `python3` or bare `pip`/`pip install`.** All Python commands must go through `uv` and `.venv/bin/python`.

### Environment setup

```bash
# Install `uv` if you don't have it already:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Always use `uv` for Python environment management:
uv venv --python 3.12
source .venv/bin/activate
```

### Tests
- **Design before you write.** Answer four questions first: what is the module
  for, what is its I/O contract, what failure am I guarding against, and what is
  the cheapest level that catches it (unit over integration over e2e)?
- **Reuse before create.** Extend existing test files, `conftest.py` fixtures, and
  helpers; add a new file only when no nearby suite fits.
- **Test behavior with intent.** Assert observable outcomes through public APIs;
  state why in the name or docstring. Skip trivial wiring; flaky tests are worse
  than no tests.
- **Keep it minimal.** One behavior per test and the smallest setup that
  triggers it; if the test diff dwarfs the code change, cut scope.

### Documentation

Readers are bioinformaticians and clinical researchers. They know genetics, a
shell and some Python or R. Most have never run a model server or sized GPU
memory. Write so they can run Gentrex and read its output without asking
anyone.

Good docs = what the reader needs for the task − what they already know.

#### Know the Reader

**Explain what they don't know. Skip what they do.**

- Define a computing term only if the reader won't know it, once per page,
  in a few plain words. Don't explain everyday shell tools and their flags,
  such as `curl -f -L -o` or `mkdir -p`.
- Use the standard term, then explain it. Never replace it with a made-up
  everyday phrase, such as "first words" for tokens. Readers can't search for
  the phrase or match it to an error message.
- Don't explain genetics. HGVS, VUS, zygosity and ACMG classes need no
  definition.
- Name things exactly: the file and key (`extract.max_tokens` in
  settings.yaml), not "the settings". Use one name per thing. A command's
  name, page title, page file, results folder and settings key share a word,
  as `gentrex extract`, "Extract report data", docs/user-guide/extract.md,
  results/extract/ and the settings key `extract` do. Commands have no
  numbers, so that adding or removing a command renumbers nothing. A new
  export format becomes `gentrex export <format>`, with the page
  docs/user-guide/export-<format>.md and the results folder
  results/export/<format>/.
- Put each page in the folder for its use. Pages that explain how Gentrex
  works and how to run each command go in docs/user-guide/, pages about
  running Gentrex on Minerva in docs/minerva/, and pages about working on
  Gentrex itself, such as contributing and releasing, in docs/development/.
  CHANGELOG.md stays directly in docs/, because users read it too.
  .github/CONTRIBUTING.md only points to docs/development/contributing.md,
  because GitHub links contributors to a guide only in the repository's
  root, docs/ or .github/.

#### Big Picture First

**What it does and why, before how it works.**

- Open each page with what goes in, what comes out, and why to run it.
- Order a command's page: before you start, steps, check the result, how it
  works, settings, when something goes wrong. Internals (token probabilities,
  schema order, GPU memory) go in "How it works", after the steps.
- Title pages and sections by what the reader does or gets, verb first
  ("Extract report data"), not with a slogan ("One record per report").
- Describe behavior shared by all commands once, in README.md, and link to it.

#### Explain, Don't Compress

**Full sentences, without a reason attached to each one.**

- Short sentences are good. Clipped ones are not. Give a "because" or "so"
  only where the reader needs the reason to decide something or to avoid a
  mistake. Most sentences need none.
- Don't join two statements with a colon, semicolon or dash. Use "because" or
  start a new sentence.
- One idea per sentence. If a sentence needs a second read, split it.
- Explain a flag, setting or number when the reader couldn't guess what it
  does, or when its value matters to them. Do it in one sentence, next to it,
  not as a list of bullets after every command.
- Give a concrete example (a command, an output line, a number) before the
  general rule.

#### Cut AI Tells

**Write about the subject, plainly.**

- No "This guide covers...", "In this section..." or recap of what was just
  said.
- No disclaimers, reassurances or sales words ("robust", "seamless"). Warn
  only where the reader must act, at the step it applies to.
- No warnings against things the reader had no reason to do, and no "not X
  but Y" against a claim nobody made.
- Group items in threes only when there are three. Bold only what readers
  scan for, and don't use emoji.
- Use "such as" at most once in a paragraph. Don't chain definitions, as in
  "Phenopackets, the GA4GH format for ..., and FHIR, HL7's standard for
  ...".
- Link to another page plainly. Don't end sentence after sentence with "as
  [page] shows".
- Say each fact once per page, where the reader needs it.
- Vary the length of sentences and their subject. Don't start every sentence
  with the command's name or "Gentrex".

#### Check Before You Finish

**Check only what you changed.**

- Check each command, flag, path and default you added or changed against the
  code.
- Examples use synthetic values (`SYN-MRN-0001`), never text from real reports.
- After renaming a heading, update the links to its anchor.

### Coding style guidelines

The line length limit for Python code is 88 characters. If you are not sure, use pre-commit to check.

Use Google-style docstrings (Args:/Returns:/Raises: sections), not reStructuredText/Sphinx fields (:param:, :return:, :rtype:).

- Follow Google Python Style Guide
- Minimize use of comments. Eliminate comments which are redundant, preferring legible and self-documenting code. When used, keep docstrings and comments brief and direct.

#### Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

#### Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

#### Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

#### Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
