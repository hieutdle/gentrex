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
- A GPU for Gentrex's models, one after another. The larger one, the model
  of `gentrex select` and `gentrex extract`, needs an NVIDIA GPU with 80 GB
  ([Select the pages to keep](../user-guide/select.md#before-you-start)).
- [vLLM](https://docs.vllm.ai) 0.25 or newer, or another model server that
  `gentrex select` works with.

Scores compare only within one benchmark version. A language model writes the
text of the reports, so a version that you generate has other texts than a
version that someone else generates, even from the same cases. To reproduce
published numbers, use the PDFs and truth files that were published with
them.

## Step 1: Choose the reports

A benchmark version holds three copies of every report, and each run reads
one of them:

| `--copy` | The reports as |
| --- | --- |
| `native` | PDFs with their text layer |
| `scan` | Page images, as from an office scanner |
| `fax` | Page images, as from a fax |

## Step 2: Check the script that starts the model servers

`gentrex transcribe` uses one model, and `gentrex select` and
`gentrex extract` share another. The two rarely fit on a GPU together.
`run.py` therefore
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
    options=(--max-model-len 32768) ;;
  ...
esac

exec vllm serve "$1" --port "$2" "${options[@]}"
```

The names are the models in `transcribe.ocr.model`, `select.model` and
`extract.model` in settings.yaml, and the last two name the same model. The options are those of each command's own
page, which explains them
([transcribe](../user-guide/transcribe.md#step-3-start-the-ocr-server),
[select](../user-guide/select.md#step-1-start-the-model-server),
[extract](../user-guide/extract.md#step-1-start-the-model-server)). If you
benchmark another model, add a line for it
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
  --version v1 --copy native --gpus 1 1 1 \
  --serve evaluation/local/serve.sh
```

`--gpus 1 1 1` tells the scorer how many GPUs the servers of
`gentrex transcribe`, `gentrex select` and `gentrex extract` run on, in that
order. With it, the scores include GPU-hours. Without `--serve`, add
`--env-file .env` after `uv run`.

The four commands log as they always do. Before each model, the log says
which server `run.py` is waiting for, and the last line gives the main
result:

```text
2026-11-10 10:37:52,623 waiting for lightonai/LightOnOCR-3-4B at http://localhost:50945/v1
...
2026-11-10 11:02:11,306 report accuracy 91.0% on 300 reports; wrote results/gentrex-bench/20261110-103752
```

To score another copy, run the command again with another `--copy`.

A command that ends with failed files doesn't stop the run. The reports
without a record count as wrong, so a setup that often fails can't look good
by leaving reports out. `run.py` then writes the scores and ends with exit
code 1, so that a script or a batch job notices. `scores.json` gives each
command's `exit_status` and `failed_files` under `performance`. Before you
use such scores, check in the command's `log.txt` whether the model failed
on these files or its server stopped.

### Go on after a run that stopped

If a run stops in a later command, the commands before it don't have to run
again. Each command logs its run folder in a line such as
`writing results/select/20261110-103801`. Give the folder of the last
command that finished to `--from-run`:

```bash
uv run --extra hpo python gentrex-bench/run.py \
  --version v1 --gpus 1 1 1 --serve evaluation/local/serve.sh \
  --from-run results/select/20261110-103801
```

The run then starts with `gentrex extract`. The scores still give the time
of every command, because each run folder records its own. Keep `--version` as it was. `--copy` isn't needed, because the run folder
already holds the pages.

## Check the result

Each run of `run.py` gets a folder named after its start time, such as
`results/gentrex-bench/20261110-103752/`:

| Path | Contents |
| --- | --- |
| `scores.md` | The scores as tables, to read |
| `scores.json` | The same numbers and the result of every report, for the notebook and your own scripts |
| `errors.jsonl` | Every value that isn't right, one per line |
| `native/` | Links to the PDFs that the run read, named after `--copy` |
| `select-methods/` | With `--select-methods`, the pages that each other way of choosing pages kept ([Compare ways to choose pages](#compare-ways-to-choose-pages)) |

The four commands write their own run folders under `results/`, as in any
other run, and `scores.json` names them.

`scores.md` starts with the main numbers. The numbers below only show the
layout:

```text
| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 91.0% | 85.0% to 96.0% |
| Reports with every value right | 42.0% | 32.0% to 52.0% |
| MRN and date of birth both right | 98.0% | 95.0% to 100.0% |
| Value F1 | 97.1% | 96.4% to 97.7% |
| Variant F1 | 94.7% | 91.2% to 97.6% |
```

- **Report accuracy** is the share of reports with nothing clinically wrong.
  The result category and the karyotype are right, every variant is found
  with its gene, DNA change, copy number, classification and zygosity, and
  no variant is extra.
- **Reports with every value right** is the share of reports whose whole
  record is right, with the identifiers, the dates and the standard values.
- **MRN and date of birth both right** is the share of reports that would be
  filed under the right patient.
- **Value F1** counts every value that a report states and every value that
  a record holds. Recall is the share of the stated values that are right in
  the record, and precision the share of the record's values that are right.
  A field that a report doesn't state and the record leaves empty counts
  nowhere.
- **Variant F1** is the same for whole variants.

The 95% interval says how far a number could be off because the benchmark
has only so many reports. A difference between two runs that is smaller than
their intervals may be chance.

The tables below the main numbers answer what to fix:

| Table | What it shows |
| --- | --- |
| Variants and clinical features | How many were found, missed and extra. Missed ones are split by the command that lost them. Extra ones are split into distractors, which the report prints, and hallucinations, which it doesn't. |
| Where errors come from | The missed, wrong and extra values of each command |
| Checks | For each check of Gentrex, how many values it flagged, how many of those were wrong, and what share of the wrong values it flagged. Then how many reports a person would look at, and how many of the wrong reports are among them. |
| Pages | The pages that went to OCR and the pages that `gentrex select` kept. The share of the words of the scanned pages that OCR wrote, against the truth files. How many stated values each command lost. |
| Fields | The accuracy and the F1 of every field of the record |
| Groups | Report accuracy by laboratory, template, test, result, challenge, number of variants and page count |
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
This file, saved as `larger-model.yaml`, makes `gentrex extract` use a larger
model than `gentrex select`:

```yaml
extract:
  model: google/gemma-4-31B-it
```

```bash
uv run --extra hpo python gentrex-bench/run.py \
  --version v1 --gpus 1 1 2 --serve evaluation/local/serve.sh \
  --settings larger-model.yaml
```

`serve.sh` doesn't know this model yet, so add a line with its name and
vLLM's options to the script. This one needs two GPUs with 80 GB, which
`--tensor-parallel-size 2` splits it across, and `--gpus 1 1 2` tells the
scorer.

`--no-select` skips `gentrex select`, so that `gentrex extract` reads every
page of a report. Compared with a normal run, it shows what selecting pages
is worth. A long report can then exceed the context length that the server
of `gentrex extract` allows. Its request fails, and the report counts as
wrong. `--gpus` still takes three numbers, and the second one isn't used.

With `normalize.clinvar_path` in the settings file, `gentrex normalize` looks
up ClinVar IDs, and the scorer scores them
([Normalize report data](../user-guide/normalize.md#step-4-download-clinvar)).

The notebook gives the difference between two runs with its interval.

## Compare ways to choose pages

`gentrex select` asks three yes/no questions about each page and reads the
answers from the probabilities of the first token
([Select the pages to keep](../user-guide/select.md#how-it-works)).
`--select-methods` shows what that is worth. After `gentrex select`, it
chooses the pages of the same reports in two other ways, while the server of
`select.model` is still running:

| Way | How it chooses |
| --- | --- |
| `one_question` | It asks one general question about each page, whether the page is important for a record of the patient's test. The answer is read from the first token, as in `gentrex select`. |
| `page_extract` | The model fills the extraction schema from each page alone. The page is kept if its record has a result, a karyotype, a variant, a clinical feature, a reason for testing or the date of the collection, the receipt or the report. |

```bash
uv run --extra hpo python gentrex-bench/run.py \
  --version v1 --copy native --gpus 1 1 1 \
  --serve evaluation/local/serve.sh --select-methods
```

The run then goes on with `gentrex extract`, which reads the pages that
`gentrex select` kept. The other two ways only choose pages, so the scores
of the records don't change. `scores.md` gets a table with the three ways
under Pages, and `scores.json` has the numbers under `select_methods`. Each
way has the needed pages that it kept, the time, requests and tokens that it
took, and under `failed` the pages that it kept because a request failed.
`questions` is `gentrex select` itself.

`page_extract` writes a whole record for every page, so it takes the
longest of the three. `--select-methods` does nothing in a run with
`--no-select`, and in a run that `--from-run` starts after `gentrex select`.

## Compare runs in the notebook

`presentation.ipynb`, in the Gentrex folder, reads every `scores.json` under
`results/gentrex-bench/` and shows the newest run of each setup in the
tables and figures of the paper:

```bash
uv run --group notebook jupyter lab presentation.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run. A setup is a copy of the reports with or without `gentrex select`.
[The presentation](../../evaluation_results/README.md#read-the-presentation)
says more.

Some tables quote values from the reports. After a run on real reports,
clear a notebook's outputs before you save or share it.

## Score a run you made yourself

`run.py` scores with `gentrex-bench/scorer/score.py`, which you can also run
on its own. Use it when you ran the commands by hand, or when you have truth
files for your own reports:

```bash
uv run python gentrex-bench/scorer/score.py \
  --truth data/gentrex-bench/v1/truth --run results/normalize/latest
```

`--run` is a run folder of `gentrex normalize`. Its `run.yaml` names the run
of `gentrex extract` that it read, and so on back to the PDFs, so the scorer
finds the output of every command. The scores go to a new folder under
`results/gentrex-bench/`.

The scorer pairs each truth file with the PDF of the same name, so
`SYN-0001.json` is the truth of `SYN-0001.pdf`. A truth file for a report of
your own has the keys that
[Generate benchmark reports](generate-benchmark-reports.md#check-the-result)
lists, without `pages`. The scorer scores every truth file in the folder.

## How it works

`run.py` links the benchmark PDFs into its results folder and runs
`gentrex transcribe` on that folder. Each later command reads the run folder
of the command before it, through `--input`. Nothing else differs from a run
on your own reports, so the benchmark measures the Gentrex that you use.

### Matching

The scorer counts every value as correct, missed, extra or wrong. Text
matches if it is the same apart from case, spacing and trailing punctuation.
A c. or m. change also matches with its reference sequence in front, so
`NC_012920.1:m.3243A>G` matches `m.3243A>G`. A c. change matches with the
bases after `del` or `dup` as well, so `NM_007294.4:c.5266dupC` matches
`c.5266dup`. A protein change matches with or without its parentheses. The Fields table
gives the share of exact matches next to the accuracy.

Variants are matched one to one by gene and DNA change before their other
fields are compared. The gene matches as the report prints it or as its
approved HGNC symbol, so `MLH1` matches a printed `COCA2`. A variant whose
truth has no DNA change, such as an SMN1 copy number, matches on its gene. Clinical features are matched by their text, and after
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

### Checks

Gentrex flags values for a person to look at, and the scorer counts how
useful each flag is. Of the values that a check flagged, precision is the
share that were wrong or extra. Of the wrong or extra values that it looked
at, recall is the share that it flagged.

| Check | Flags | Looks at |
| --- | --- | --- |
| `not_in_pages` | A copied value that `gentrex extract` didn't find in the pages' text ([Extract report data](../user-guide/extract.md#how-it-works)) | Every copied value that it wrote. A missed value can't be checked. |
| `hgvs_invalid` | A variant whose c. or p. change `gentrex normalize` marked `invalid` | Every variant that it found or added |
| `result_conflict` | A result whose wording and classifications disagree (`overall_result_conflict`) | The result of every report with a record |
| `hpo_models_disagree` | A clinical feature whose two embedding models chose different HPO terms | Every feature that was found |

A report is flagged if a check flagged one of its values. `scores.json`
gives the flags of each report, and under `review` how many reports each
check flags and how many of the wrong reports are among them.

### Kinds of error

A wrong or extra text value is put in one of four kinds, so that the fix is
clear:

| Kind | The value is |
| --- | --- |
| `partial` | Part of the true value, or the true value with more around it |
| `other_value` | A value that the report prints for another field, or a distractor |
| `not_in_pages` | Text that the pages that `gentrex extract` read don't have |
| `other_text` | Other text of those pages |

`errors.jsonl` gives the kind of each value under `cause`, and `scores.json`
counts the kinds of each field under `kinds`. A wrong category or number
counts as `category`. `confusions` in `scores.json` counts, for each field
with a fixed list of categories, how often each true category was written as
each category.

### Each command on its own

Besides the end-to-end numbers, the scorer measures each command on what
the command before gave it, so that a loss upstream doesn't count against
it. `scores.json` has these under:

| Key | What it holds |
| --- | --- |
| `pages` | The pages that went to OCR, and the share of the true words of those pages that OCR wrote, whatever their order |
| `select` | The pages that `gentrex select` kept and dropped, split into needed pages, which are the only page to print a stated value, and the others. `sweep` gives the same at other values of `select.keep_threshold`, from the probabilities of "yes" in `decisions.jsonl`. `only_by` counts the pages that only one question kept. |
| `select_methods` | With `--select-methods`, the same counts as `select` for each way of choosing pages, with the time, requests and tokens that it took |
| `funnel` | Of the values that reached `gentrex extract`, the share that it got right (`extract_recall`). `fields` gives the same for each field as `recall_given_input`. |
| `normalize` | Each standard value, end to end and given a right source, with the HGNC IDs split by whether the report prints the approved symbol |
| `hpo` | For the clinical features whose text was found: the share whose term is right, whose true term is the first candidate or among the five, and that got no term, also split by whether the two embedding models agreed |

The benchmark prints each clinical feature as an HPO label or synonym and
each condition as its MONDO label, so its HPO and MONDO numbers are close to
an upper bound. The evaluations on real wording are in
[`evaluation_results/hpo-matching.md`](../../evaluation_results/hpo-matching.md)
and
[`evaluation_results/mondo-matching.md`](../../evaluation_results/mondo-matching.md).

### Kinds of variant

Each variant also has a kind, from how the report gives it: a sequence
variant, an exon deletion or duplication, a mitochondrial variant, a
copy-number change, the copy number of a gene, a repeat expansion or a
uniparental disomy. `variant_kinds` in `scores.json` scores each kind.

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

With `--serve`, `scores.json` also has the seconds that each model server
took to start, as `server_start_seconds` of each command under
`performance`, and `scores.md` gives their sum. They don't count in the
GPU-hours, because a server starts once however many PDFs a run reads.

[Benchmark design](benchmark.md#scorer) gives the reasons for these rules.

## Options

`run.py` takes these options:

| Option | Default | What it does |
| --- | --- | --- |
| `--version` | `v1` | The benchmark version, a folder under `data/gentrex-bench/` |
| `--copy` | `native` | The copy of the reports to read |
| `--gpus` | none | The GPUs of the servers of `gentrex transcribe`, `gentrex select` and `gentrex extract`, for the GPU-hours |
| `--serve` | none | The script that starts a model server. Without it, the servers in `.env` are used. |
| `--no-hpo` | off | Runs `gentrex normalize` without HPO terms, which then aren't scored |
| `--settings` | none | A settings file of your own, which every command then reads |
| `--no-select` | off | Skips `gentrex select`, so that `gentrex extract` reads every page |
| `--select-methods` | off | After `gentrex select`, chooses the pages in two other ways on the same model server, and scores all three |
| `--from-run` | none | A finished run folder of `gentrex transcribe`, `gentrex select` or `gentrex extract`. The run starts with the command after it. |

Both take `--label`, a name of the run's setup that the scores keep, as in
`--label qwen` for a run with another model. The notebook then compares the
run as a setup of its own instead of as a newer run of the same copy.

`score.py` takes `--gpus` and `--label` as well, and these:

| Option | Default | What it does |
| --- | --- | --- |
| `--truth` | `data/gentrex-bench/v1/truth` | The folder of truth files |
| `--run` | `results/normalize/latest` | The run folder of `gentrex normalize` to score |
| `--list` | off | Lists the scored runs in `results/gentrex-bench/` instead, one line each |

`scores.json` keeps the settings of every command with the scores, as the
commands used them.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `data/gentrex-bench/v1/pdf/native not found` | The version or the copy doesn't exist. Check `--version` and `--copy` against the folders in `data/gentrex-bench/`. |
| `has no truth files` | The truth folder has no JSON files. Check `--truth` or build the benchmark version first. |
| `serve.sh ended before ... was ready` | The server couldn't start. Run the script by hand, as in `evaluation/local/serve.sh google/gemma-4-26B-A4B-it 8000`, and read what the server prints. |
| The log stays at `waiting for ...` | The server runs but doesn't answer on the port it was given. Check that the script passes `$2` to the server as its port. |
| `gentrex transcribe did not finish (exit code 2)` | Without `--serve`, the command didn't find its server's address. Add `--env-file .env` after `uv run`. |
| `gentrex normalize did not finish (exit code 1)` | The lines above name a missing file. Follow steps 1 to 3 of [Normalize report data](../user-guide/normalize.md#step-1-download-the-hgnc-complete-set), or pass `--no-hpo`. |
| `is not a run folder of gentrex normalize` | Give `--run` a run folder of `gentrex normalize`, not of another command. |
