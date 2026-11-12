# Run the benchmark

`gentrex-bench/run.py` runs Gentrex on benchmark reports and compares its
records with the reports' truth files. It reads the PDFs and truth files of a
benchmark version. It writes the share of reports that Gentrex got right, the
accuracy of every field, the command that lost each wrong value, and the time
and tokens that each command took.

Run it after you change a prompt, a model or a setting, to see whether
Gentrex got better. Run it also to check someone's published numbers on your
own machines.

The reports hold no patient data, so the benchmark can run on any computer
that can serve Gentrex's models. On Mount Sinai's Minerva cluster it runs as
a batch job, which
[Run the benchmark on Minerva](../minerva/minerva.md#run-the-benchmark)
describes.

`evaluation/local/run_pipeline.sh` does the steps of this page with one
command, and downloads what `gentrex normalize` needs first
([Evaluate Gentrex](../../evaluation/README.md)). This page explains what it
runs, and how to read and change it.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](../user-guide/transcribe.md#step-1-install)).
- The reference files and the HPO index of `gentrex normalize`, from steps 1
  to 3 of [Normalize report data](../user-guide/normalize.md#step-1-download-the-hgnc-complete-set).
- A benchmark version in `data/gentrex-bench/`, such as `v1`, with its `pdf/`
  and `truth/` folders. [Generate benchmark reports](generate-benchmark-reports.md)
  makes one.
- GPUs for Gentrex's three models, one after another. The largest, the model
  of `gentrex extract`, needs two NVIDIA GPUs with 80 GB each
  ([Extract report data](../user-guide/extract.md#before-you-start)).
- [vLLM](https://docs.vllm.ai) 0.25 or newer, or another model server that
  `gentrex select` works with.

Scores compare only within one benchmark version. A language model writes the
text of the reports, so a version that you generate has other texts than a
version that someone else generates, even from the same cases. To reproduce
published numbers, use the PDFs and truth files that were published with
them.

## Step 1: Choose the reports

A benchmark version holds five copies of every report, and each run reads
one of them:

| `--copy` | The reports as |
| --- | --- |
| `native` | PDFs with their text layer |
| `scan` | Page images, as from an office scanner |
| `fax` | Page images, as from a fax |
| `mixed` | PDFs with about a third of their pages scanned |
| `image` | Clean page images whose only text is a document code |

`--split` picks the dev or the test reports. Tune Gentrex on `dev`, which is
the default. Run `test` only for the numbers you report, with the settings
you have already decided on. Otherwise you tune on the test reports without
noticing, and the test numbers come out too high.

## Step 2: Check the script that starts the model servers

`gentrex transcribe`, `gentrex select` and `gentrex extract` each use their
own model, and the three rarely fit on the GPUs together. `run.py` therefore
starts the model server of each command before the command and stops it
afterwards. It does so with a script, which it calls with the model's name
and a free port.

`evaluation/local/serve.sh` is that script for vLLM:

```bash
case "$1" in
  lightonai/LightOnOCR-3-4B)
    options=(--max-model-len 18000
      --default-chat-template-kwargs '{"enable_thinking": false}') ;;
  google/gemma-4-26B-A4B-it)
    options=(--max-model-len 16384) ;;
  google/gemma-4-31B-it)
    options=(--tensor-parallel-size 2 --max-model-len 32768
      --gpu-memory-utilization 0.95) ;;
  ...
esac

exec vllm serve "$1" --port "$2" "${options[@]}"
```

The three names are the models in `transcribe.ocr.model`, `select.model` and
`extract.model` in settings.yaml. The options are those of each command's own
page, which explains them
([transcribe](../user-guide/transcribe.md#step-3-start-the-ocr-server),
[select](../user-guide/select.md#step-1-start-the-model-server),
[extract](../user-guide/extract.md#step-1-start-the-model-server)). The model
of `gentrex extract` gets two GPUs. On one GPU with more memory, remove
`--tensor-parallel-size 2`. If you benchmark another model, add a line for it
to the script ([Run another setup](#run-another-setup)).

A script of your own for another model server works too. It must serve the
model at the port it is given and keep running for as long as the server
does, which `exec` takes care of. `run.py` waits until the server lists its
models at `http://localhost:<port>/v1/models`, runs the command and then
stops the script.

If your model servers are already running, skip this step and leave out
`--serve` in step 3. `run.py` then uses the addresses in `.env`, as the
commands do. `gentrex select` and `gentrex extract` read the same address,
`GENTREX_LLM_BASE_URL`, so that server has to serve both of their models.

## Step 3: Run

```bash
uv run --extra hpo python gentrex-bench/run.py \
  --version v1 --copy native --split dev --gpus 1 1 2 \
  --serve evaluation/local/serve.sh
```

`--gpus 1 1 2` tells the scorer how many GPUs the servers of
`gentrex transcribe`, `gentrex select` and `gentrex extract` run on, in that
order. With it, the scores include GPU-hours. Without `--serve`, add
`--env-file .env` after `uv run`.

The four commands log as they always do. Before each model, the log says
which server `run.py` is waiting for, and the last line gives the main
result:

```text
2026-11-10 10:37:52,623 waiting for lightonai/LightOnOCR-3-4B at http://localhost:50945/v1
...
2026-11-10 11:02:11,306 report accuracy 91.0% on 100 reports; wrote results/gentrex-bench/20261110-103752
```

To score another copy, run the command again with another `--copy`.

A command that ends with failed files doesn't stop the run. The reports
without a record count as wrong, so a setup that often fails can't look good
by leaving reports out.

## Check the result

Each run of `run.py` gets a folder named after its start time, such as
`results/gentrex-bench/20261110-103752/`:

| Path | Contents |
| --- | --- |
| `scores.md` | The scores as tables, to read |
| `scores.json` | The same numbers and the result of every report, for the notebook and your own scripts |
| `errors.jsonl` | Every value that isn't right, one per line |
| `native/` | Links to the PDFs that the run read, named after `--copy` |

The four commands write their own run folders under `results/`, as in any
other run, and `scores.json` names them.

`scores.md` starts with the main numbers. The numbers below only show the
layout:

```text
| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 91.0% | 85.0% to 96.0% |
| MRN and date of birth both right | 98.0% | 95.0% to 100.0% |
| Variant F1 | 94.7% | 91.2% to 97.6% |
```

- **Report accuracy** is the share of reports with nothing clinically wrong.
  The result category and the karyotype are right, every variant is found
  with its gene, DNA change, copy number, classification and zygosity, and
  no variant is extra.
- **MRN and date of birth both right** is the share of reports that would be
  filed under the right patient.
- **Variant F1** combines the share of true variants that Gentrex found with
  the share of Gentrex's variants that are true.

The 95% interval says how far a number could be off because the benchmark
has only so many reports. A difference between two runs that is smaller than
their intervals may be chance.

The tables below the main numbers answer what to fix:

| Table | What it shows |
| --- | --- |
| Variants and clinical features | How many were found, missed and extra. Missed ones are split by the command that lost them. Extra ones are split into distractors, which the report prints, and hallucinations, which it doesn't. |
| Where errors come from | The missed, wrong and extra values of each command |
| Values not in the pages | How many copied values `gentrex extract` named in `not_in_pages`, how many of those were wrong or extra, and what share of all wrong or extra copied values it named |
| Fields | The accuracy of every field of the record |
| Groups | Report accuracy by template, test, result, challenge tag and number of variants, and for the templates that the dev set doesn't have |
| Speed and cost | The time, requests and tokens of each command |

To see the errors themselves, open `errors.jsonl`. Each line names the
report, the field, the true value, Gentrex's value and the command charged:

```json
{"report": "SYN-0118", "field": "variants.hgvs_p", "result": "wrong", "truth": "p.(Arg412Trp)", "found": "p.(Arg421Trp)", "command": "extract", "cause": null, "flagged": true}
```

`flagged` is `true` if `gentrex extract` had named the value in
`not_in_pages`, and `null` for a value that it doesn't check.

## Run another setup

To measure what a model, a prompt or a command is worth, run the benchmark
again with one thing changed, and compare the two runs.

`--settings` runs every command with a
[settings file of your own](../user-guide/runs-and-results.md#change-the-settings).
This file, saved as `one-model.yaml`, makes `gentrex extract` use the smaller
model of `gentrex select`:

```yaml
extract:
  model: google/gemma-4-26B-A4B-it
```

```bash
uv run --extra hpo python gentrex-bench/run.py \
  --version v1 --split dev --gpus 1 1 1 --serve evaluation/local/serve.sh \
  --settings one-model.yaml
```

`serve.sh` starts this model with the options that `gentrex select` needs.
For `gentrex extract`, raise its `--max-model-len` to 32768, so that the
kept pages of a long report fit. For a model that `serve.sh` doesn't know
yet, add a line to the script.

`--no-select` skips `gentrex select`, so that `gentrex extract` reads every
page of a report. Compared with a normal run, it shows what selecting pages
is worth. A long report can then exceed the context length that the server
of `gentrex extract` allows. Its request fails, and the report counts as
wrong. `--gpus` still takes three numbers, and the second one isn't used.

With `normalize.clinvar_path` in the settings file, `gentrex normalize` looks
up ClinVar IDs, and the scorer scores them
([Normalize report data](../user-guide/normalize.md#step-4-download-clinvar)).

The notebook gives the difference between two runs with its interval.

## Compare runs in the notebook

`evaluation_results/pipeline.ipynb` reads every `scores.json` under
`results/gentrex-bench/` and shows the runs side by side:

```bash
uv run --group notebook jupyter lab evaluation_results/pipeline.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run. The notebook first follows one report of a run through the four
commands. Then it has the main numbers of that run, the errors, time and
tokens of each command, the accuracy of every field and of every kind of
report, the difference between two runs with its interval, and a plot of
accuracy against GPU-hours. It computes no scores itself, so its numbers are
those of `scores.md`.

Some tables quote values from the reports. After a run on real reports,
clear the notebook's outputs before you save or share it.

## Score a run you made yourself

`run.py` scores with `gentrex-bench/scorer/score.py`, which you can also run
on its own. Use it when you ran the commands by hand, or when you have truth
files for your own reports:

```bash
uv run python gentrex-bench/scorer/score.py \
  --truth data/gentrex-bench/v1/truth --run results/normalize/latest --split dev
```

`--run` is a run folder of `gentrex normalize`. Its `run.yaml` names the run
of `gentrex extract` that it read, and so on back to the PDFs, so the scorer
finds the output of every command. The scores go to a new folder under
`results/gentrex-bench/`.

The scorer pairs each truth file with the PDF of the same name, so
`SYN-0001.json` is the truth of `SYN-0001.pdf`. A truth file for a report of
your own has the keys that
[Generate benchmark reports](generate-benchmark-reports.md#check-the-result)
lists, without `pages`. Score such files with `--split all`, which scores
every truth file in the folder.

## How it works

`run.py` links the PDFs of the split into its results folder and runs
`gentrex transcribe` on that folder. Each later command reads the run folder
of the command before it, through `--input`. Nothing else differs from a run
on your own reports, so the benchmark measures the Gentrex that you use.

### Matching

The scorer counts every value as correct, missed, extra or wrong. Text
matches if it is the same apart from case, spacing and trailing punctuation.
A c. change also matches with its transcript in front or with the bases
after `del` or `dup`, so `NM_007294.4:c.5266dupC` matches `c.5266dup`. A
protein change matches with or without its parentheses. The Fields table
gives the share of exact matches next to the accuracy.

Variants are matched one to one by gene and DNA change before their other
fields are compared. Clinical features are matched by their text, and after
`gentrex normalize` by their HPO ID. The overall result is compared through
its category, because the copied statement has no single right place to end.
The ClinVar ID of a variant with a c. change is compared if
`gentrex normalize` ran with ClinVar's file.

### Charging errors

Each missed or wrong value is charged to the first command that lost it:

| The value is | Charged to |
| --- | --- |
| missing from the transcribed text | `gentrex transcribe` |
| on a page that wasn't kept | `gentrex select` |
| wrong or missing in the record | `gentrex extract` |
| right in the record, with a wrong date, category or ID | `gentrex normalize` |

An extra value is charged to the command that wrote it. A normalized value
that is wrong because its record value was already wrong isn't charged a
second time.

### Values not in the pages

`gentrex extract` names the copied values that it didn't find in the pages'
text ([Extract report data](../user-guide/extract.md#how-it-works)). The
scorer counts how useful that is. Of the values it named, the first share
says how many were wrong or extra. The second share says how many of all
wrong or extra copied values it named. Missed values don't count, because a
value that wasn't written can't be checked.

### Intervals

The 95% intervals come from a bootstrap. The scorer draws the reports 2,000
times at random, with repeats, and takes the range that holds the middle 95%
of the results. It draws whole reports, because the fields of one report
aren't independent.

### Time and tokens

Every run folder's `run.yaml` records how long the command took and how many
requests and tokens it exchanged with its model server
([Run folders](../user-guide/runs-and-results.md#run-folders)). The scorer
reads them from there. The time is that of the command alone, without the
minutes a server takes to load its model. GPU-hours are each command's time
multiplied by its GPUs from `--gpus`, per 1,000 PDFs.

[Benchmark design](benchmark.md#scorer) gives the reasons for these rules.

## Options

`run.py` takes these options:

| Option | Default | What it does |
| --- | --- | --- |
| `--version` | `v1` | The benchmark version, a folder under `data/gentrex-bench/` |
| `--copy` | `native` | The copy of the reports to read |
| `--split` | `dev` | The split to run and score, `dev`, `test` or `all` |
| `--gpus` | none | The GPUs of the servers of `gentrex transcribe`, `gentrex select` and `gentrex extract`, for the GPU-hours |
| `--serve` | none | The script that starts a model server. Without it, the servers in `.env` are used. |
| `--no-hpo` | off | Runs `gentrex normalize` without HPO terms, which then aren't scored |
| `--settings` | none | A settings file of your own, which every command then reads |
| `--no-select` | off | Skips `gentrex select`, so that `gentrex extract` reads every page |

`score.py` takes `--split` and `--gpus` as well, and these two:

| Option | Default | What it does |
| --- | --- | --- |
| `--truth` | `data/gentrex-bench/v1/truth` | The folder of truth files |
| `--run` | `results/normalize/latest` | The run folder of `gentrex normalize` to score |

`scores.json` keeps the settings of every command with the scores, as the
commands used them.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `data/gentrex-bench/v1/pdf/native not found` | The version or the copy doesn't exist. Check `--version` and `--copy` against the folders in `data/gentrex-bench/`. |
| `has no truth files of the split` | No truth file names that split. Generated versions have `dev` and `test`. For your own truth files, use `--split all`. |
| `serve.sh ended before ... was ready` | The server couldn't start. Run the script by hand, as in `evaluation/local/serve.sh google/gemma-4-31B-it 8000`, and read what the server prints. |
| The log stays at `waiting for ...` | The server runs but doesn't answer on the port it was given. Check that the script passes `$2` to the server as its port. |
| `gentrex transcribe did not finish (exit code 2)` | Without `--serve`, the command didn't find its server's address. Add `--env-file .env` after `uv run`. |
| `gentrex normalize did not finish (exit code 1)` | The lines above name a missing file. Follow steps 1 to 3 of [Normalize report data](../user-guide/normalize.md#step-1-download-the-hgnc-complete-set), or pass `--no-hpo`. |
| `is not a run folder of gentrex normalize` | Give `--run` a run folder of `gentrex normalize`, not of another command. |
