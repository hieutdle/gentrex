# Runs and results

All Gentrex commands write their results and handle failures in the same
way.

## Run folders

Every run gets a new folder named after its start time, for example
`results/transcribe/20261014-123000/`. A second run in the same second gets
`-2` added to the name. Old runs stay, so you can compare them.

Next to its output, each run folder has two files. `run.yaml` records the
command, the Gentrex version and git commit, the run it read and the
settings, so you can always trace a result back to what made it. It says
`modified: true` when the code in `src/gentrex/` had changes that weren't
committed. `log.txt` holds everything the run printed.
`uv run gentrex --version` prints the version.

When the run ends, `run.yaml` also gets its time and its use of the model
server:

```yaml
seconds: 312.4
requests: 1204
prompt_tokens: 2381960
completion_tokens: 96212
```

`seconds` is how long the command ran. `requests` counts the answers it got
from the model server. `prompt_tokens` and `completion_tokens` are the tokens
that the server read and wrote for them, as the server reports them. Tokens
are words or pieces of words, and hosted providers charge by them. A run
with `--retry` counts only what it sent again.

`latest` in each command's folder, as in `results/transcribe/latest`, points
to the newest finished run. The next command reads it unless you name another
run with `--input`. A run that finished with some failed files still becomes
`latest`. A run that crashed doesn't.

## Change the settings

The default settings are in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml),
with a comment above each value. To change some, write a YAML file with only
those settings, laid out as in the default file. This one lets
`gentrex extract` write longer answers and wait longer for them:

```yaml
extract:
  max_tokens: 8192
  timeout_seconds: 600
```

Save it under any name, such as `my-settings.yaml`, and name it with
`--settings`:

```bash
uv run --env-file .env gentrex extract --settings my-settings.yaml
```

Every setting that the file leaves out keeps its default, and `run.yaml`
records the settings as the run used them. One file can hold the settings of
several commands, and each command reads its own part. Pass the file to
every command that it has settings for. `gentrex export phenopackets` and
`gentrex export fhir` have no settings and don't take the option.

The questions of `gentrex select` are replaced as a whole. If your file has
`select.questions`, list every question you want asked, also the default
ones you keep.

Gentrex stops with exit code 1 if the file names a setting that doesn't
exist, as in `extract.modle is not a setting of Gentrex`. Without this
check, a misspelled name would be ignored and the default would stay in
place.

You can also edit the default file itself. A file of your own stays as it is
when you update Gentrex, and you can keep one file per setup.

## Failed requests

When a request to the model server fails or times out, Gentrex tries it again
after 5, 20 and 60 seconds. After the fourth failure it records the error for
that page or report and moves on to the next. A wrong API key or model name
stops the run straight away, since every request would fail. A traceback that
ends in `openai.AuthenticationError` means the API key in `.env` is wrong.
`openai.NotFoundError` means the server runs a different model than
settings.yaml names, or the address in `.env` doesn't end in `/v1`.

## Exit codes

The exit code, which `echo $?` prints right after a run, tells you how it
went. 0 means every file went through. 1 means some files failed, the input
was missing or the run crashed, and the last lines of the output say which. 2
means a value the command needs from `.env` isn't set, or the command line
has a mistake. Each command's page lists what to do.

## Redo failed files

If some pages or reports fail in `gentrex transcribe`, `gentrex select` or
`gentrex extract`, or a job hits its time limit, run the command again with
`--retry` and the earlier run's folder:

```bash
uv run --env-file .env gentrex extract --retry results/extract/latest
```

Every record that came through without an error is reused, and only the rest
go to the model. The log tells you how many, as in
`reusing 497 of 500 reports from results/extract/latest`. The new run still
writes a complete set of records, and its `run.yaml` names the earlier run
under `retry`.

A record is reused only if its input hasn't changed. This lets retries build
on each other. Once `gentrex transcribe --retry` has read a page that failed,
`gentrex select --retry` and `gentrex extract --retry` send just that report
to the model again. For a PDF, unchanged means the same pages, each scanned
or native as before, with the same text on the native ones.

The settings have to match the earlier run, except for `timeout_seconds`,
`concurrency` and `max_tokens`. Raising those is how most failures get fixed.
After any other change, such as a different model, run without `--retry`.

A run that crashed, like a job that hit its time limit, never becomes
`latest`. Name its folder instead, as in
`--retry results/extract/20261019-030000`.

Gentrex refuses the earlier run, with exit code 1, if the folder isn't a run
of the same command, if that run used other settings, or if the input it read
no longer exists. The message says which. In the last two cases, run the
command without `--retry`.
