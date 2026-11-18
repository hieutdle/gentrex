# Evaluate Gentrex on Minerva

This page makes the synthetic benchmark reports on Minerva, runs Gentrex on
them and scores its records. You start with an empty folder and end with the
report accuracy of a run, with every wrong value listed.

A language model writes the text of 300 reports whose true content is known.
`gentrex transcribe`, `gentrex select`, `gentrex extract` and
`gentrex normalize` then read the reports, and a scorer compares the records
with the truth. Three scripts in `evaluation/minerva/` do the work, one in an
interactive session and two as batch jobs. The reports hold no patient data.

## Before you start

You need:

- A Minerva account and an allocation. Allocation names start with `acc_`,
  and `mybalance` on a login node lists yours.
- A serving folder with about 215 GB free, for vLLM and four models. Pick a
  folder in your work directory.
- About 2 GB more for the reference files and the reports, in the Gentrex
  folder.
- A [Hugging Face](https://huggingface.co) account that has accepted
  Google's terms on the pages of
  [Gemma 4 26B-A4B](https://huggingface.co/google/gemma-4-26B-A4B-it) and
  [Gemma 4 31B](https://huggingface.co/google/gemma-4-31B-it).

If you're off campus, connect to the Mount Sinai VPN. Then log in to a
Minerva login node with `ssh`.

Name your allocation and your serving folder once, in place of `acc_xxx`
and `/path/to/serving`. Every command of this page reads the two names:

```bash
export LSB_DEFAULTPROJECT=acc_xxx
export SERVING=/path/to/serving
```

`bsub` charges a job to `LSB_DEFAULTPROJECT` when the command has no `-P`.
The names last until you log out. Add the two lines to `~/.bashrc` to have
them in every session.

## Step 1: Install Gentrex

Install [uv](https://docs.astral.sh/uv/), which installs Python and the
packages, and clone Gentrex:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/hieutdle/gentrex.git
cd gentrex
```

Skip this step if you have the folder already. Run `git pull` in it instead,
so that the scripts are the newest ones.

## Step 2: Download everything

The downloads take a while, so do them in an interactive session. The GPU
jobs then spend none of their time on them. Start the session on a login
node:

```bash
bsub -q interactive -n 4 -W 6:00 -R "rusage[mem=4000]" -Is /bin/bash
```

In the session, log in to Hugging Face, go to the Gentrex folder and run the
script:

```bash
uvx --from huggingface_hub hf auth login
cd /path/to/gentrex
evaluation/minerva/prepare.sh
```

The script gets these, and keeps what is already there:

| What | Where |
| --- | --- |
| Gentrex's packages, with those of `gentrex normalize` | `.venv/` |
| ClinVar, HPO, MONDO and HGNC, and the HPO index | `data/clinvar/`, `data/ontology/` |
| The 300 cases, each with the truth of one report | `data/gentrex-bench/v1/cases/` |
| vLLM, as the container image `vllm.sif` | the serving folder |
| The three models of Gentrex and the writing model, Muse Glimmer 30B | `models/` in the serving folder |
| Chrome, which prints the reports to PDF | the serving folder |

It ends with `Minerva is ready for generate_reports.lsf and
run_pipeline.lsf`. If the session ends early, start a new one and run the
script again.

The cases come from a fixed seed, so they are the same on every machine. The
writing model needs vLLM 0.28 or newer. If the serving folder already holds
an older `vllm.sif`, delete it before you run the script, which then pulls
the newest one.

## Step 3: Generate two reports

Leave the session and submit the job from the Gentrex folder, on a login
node. Build two reports first:

```bash
cd /path/to/gentrex
CASES="SYN-0001 SYN-0002" bsub < evaluation/minerva/generate_reports.lsf
```

The two reports test the setup before the job builds all 300. To build all
of them right away, leave `CASES` out of the command. The job then works as
this step describes, and [step 4](#step-4-generate-all-reports) describes
how it ends.

The job asks for one H100 GPU and one hour. It serves the writing model, has
it write the text of each report, prints the report with Chrome and checks
that the PDF holds every value of the truth. A report that fails the check
is written again, up to three times.

Follow the job with `bjobs` and its log:

```bash
tail -f generate-reports.*.log
```

Each case logs a line like this, or why an attempt failed:

```
2026-11-10 09:14:52,118 SYN-0001 passed on attempt 1 (1482 output tokens)
```

Look at the two PDFs in `data/gentrex-bench/v1/pdf/native/` before you go
on. Copy them to your own computer with `scp` to open them.

## Step 4: Generate all reports

```bash
bsub < evaluation/minerva/generate_reports.lsf
```

The hour that the job asks for is enough for the 300 reports. Without
`CASES`, the job builds every case that has no truth file yet, so it keeps
the two reports of step 3. If the job ends in `TERM_RUNLIMIT`, submit it
again and it goes on where it stopped.

The log ends with a count:

```
2026-11-10 14:31:07,902 300 of 300 cases have a truth file; failed: none
```

If cases failed, submit the job once more. It builds only those.

`data/gentrex-bench/v1/` then holds the benchmark:

| Folder | Holds |
| --- | --- |
| `truth/` | One truth file per report |
| `pdf/native/` | The reports as Chrome printed them |
| `pdf/scan/`, `pdf/fax/` | The same reports as an office scan and as a fax |
| `pdf/mixed/` | The reports with some pages scanned |
| `pdf/image/` | The reports as page images with one line of text |
| `cases/`, `responses/`, `html/` | The cases, the model's answers and the filled templates |
| `manifest.json` | The settings and the checksums of the reference files |

Generate the reports once and keep them. The model writes other text in
every run, and scores compare only on the same reports.

## Step 5: Run Gentrex on the dev reports

```bash
bsub < evaluation/minerva/run_pipeline.lsf
```

The job asks for two H100 GPUs and six hours. This one job makes every run
of the 100 dev reports that the results compare, one after another:

| Run | Reads | Shows |
| --- | --- | --- |
| 1 | The native PDFs | The pipeline on PDFs with a text layer, where nothing goes to OCR |
| 2 to 5 | The scan, fax, mixed and image copies | What OCR loses on scanned and faxed pages |
| 6 | The native PDFs again, without `gentrex select` | What selecting pages is worth |

A run is the four commands and the scoring. The three models are served one
after another, so the job holds both GPUs for its whole time.

Follow it with `bjobs` and `tail -f run-pipeline.*.log`. Each run ends with
a line that gives its report accuracy and the folder with its scores:

```
2026-11-10 11:02:11,306 report accuracy 91.0% on 100 reports; wrote results/gentrex-bench/20261110-103752
```

The log ends with every scored run, one line each:

```
20261110-103752  dev   native                     100 reports  report accuracy  91.0%  value F1  97.1%
```

`.venv/bin/python gentrex-bench/scorer/score.py --list` prints the same
list at any time.

Use the dev reports to decide on prompts and settings. Run one such job at a
time in a Gentrex folder, because the job finds each command's run through
the command's `latest` link, which a second job would move.

To make fewer runs, name the copies in `COPIES`, and in `NO_SELECT` the
copies to read once more without `gentrex select`. This makes only the first
run:

```bash
COPIES=native NO_SELECT= bsub < evaluation/minerva/run_pipeline.lsf
```

## Step 6: Run Gentrex on the test reports

Score the 200 test reports only with the settings that you decided on, and
only for the numbers that you report. `SPLIT` names the split, and the job
makes the same six runs:

```bash
SPLIT=test bsub -W 10:00 < evaluation/minerva/run_pipeline.lsf
```

To show how much runs differ, submit the same job three times, each after
the one before it has ended.

## Check the result

A run's folder, such as `results/gentrex-bench/20261110-103752/`, holds
three files:

| File | Holds |
| --- | --- |
| `scores.md` | The scores as tables. Report accuracy and variant F1 with their 95% intervals, the accuracy of every field, the errors that each command caused, and the time and tokens of each command. |
| `scores.json` | Every number, with the settings, models and versions of the run |
| `errors.jsonl` | Every value that isn't right, with the truth and what Gentrex wrote |

Read the tables on Minerva:

```bash
less results/gentrex-bench/20261110-103752/scores.md
```

Two notebooks show the runs as tables and plots. Open them in the Gentrex
folder on Minerva, or copy `results/` and `data/gentrex-bench/v1/` into a
clone of Gentrex on your own computer first:

```bash
uv run --group notebook jupyter lab evaluation_results/analysis.ipynb
```

| Notebook | Shows |
| --- | --- |
| `analysis.ipynb` | The tables and figures of the results: the accuracy of each copy, what scanning and faxing cost, where values are lost, the pipeline with and without `gentrex select`, every field and kind of report, and time and cost. It also writes them as files to `evaluation_results/paper/`. |
| `walkthrough.ipynb` | One report through the four commands, with what each command read and wrote |

All of this is synthetic. Results of real reports must stay on Minerva.

## Run another setup

`OPTIONS` passes options to every run of `gentrex-bench/run.py`. These runs
leave the clinical features without HPO terms:

```bash
OPTIONS=--no-hpo bsub < evaluation/minerva/run_pipeline.lsf
```

To compare another setup, such as a prompt or a model, give its runs a
label. The notebook then shows them as a setup of their own next to the
default one:

```bash
OPTIONS="--label new-prompt" COPIES=native NO_SELECT= bsub < evaluation/minerva/run_pipeline.lsf
```

To change a setting of Gentrex, add it to `evaluation/settings.yaml`, which
the job passes to every command. If you name another model there, add a
line for it to `evaluation/minerva/serve.sh` and to the list of models in
`evaluation/minerva/prepare.sh`, and run `prepare.sh` again. The jobs serve
only the models in the serving folder.

## Update Gentrex

After a change to Gentrex, get it with `git pull` in the Gentrex folder. If
the change fixed the truth of the benchmark, renew the truth files. The
reports stay as they are, and no GPU is needed:

```bash
.venv/bin/python gentrex-bench/generator/generate.py --version v1 recheck
```

It takes about a minute and ends with a count:

```
2026-11-18 09:31:07,412 renewed the truth of 13 reports; reports that don't print their new case: none
```

If the change was to the scorer or the truth, score an earlier run again
to compare it with later ones under the same rules. Name the run folder of
`gentrex normalize`, which `scores.json` of the earlier run gives under
`runs`:

```bash
.venv/bin/python gentrex-bench/scorer/score.py --split dev --gpus 1 1 2 \
  --run results/normalize/20261117-203542
```

The scores go to a new folder under `results/gentrex-bench/`.

## How it works

`prepare.sh` runs `gentrex-bench/generator/generate.py sample`, which draws
the truth of each case from ClinVar, HPO, MONDO and HGNC.
`generate_reports.lsf` runs `generate.py build`, which has the model write
the free text around that truth.

`run_pipeline.lsf` runs `gentrex-bench/run.py` once for each copy, and once
more with `--no-select` for each copy in `NO_SELECT`. `run.py`
links the PDFs of the split into its results folder, runs the four commands
on them and scores the records of the last one. Before each command it
calls `evaluation/minerva/serve.sh` with the model's name and a free port,
waits until vLLM answers, and stops vLLM after the command.

Both jobs take their settings from environment variables:

| Variable | Default | Read by | What it sets |
| --- | --- | --- | --- |
| `SERVING` | none | all three scripts | The serving folder |
| `LSB_DEFAULTPROJECT` | none | `bsub` | The allocation that a job is charged to |
| `VERSION` | `v1` | all three scripts | The benchmark version, a folder under `data/gentrex-bench/` |
| `CASES` | all without a truth file | `generate_reports.lsf` | The cases to build |
| `COPIES` | all five | `run_pipeline.lsf` | The copies to read, of `native`, `scan`, `fax`, `mixed` and `image` |
| `NO_SELECT` | `native` | `run_pipeline.lsf` | The copies to read once more without `gentrex select`. `NO_SELECT=` reads none. |
| `SPLIT` | `dev` | `run_pipeline.lsf` | The split to read, `dev`, `test` or `all` |
| `OPTIONS` | none | `run_pipeline.lsf` | More options of `run.py`, for every run |

Options of `bsub` on the command line replace the `#BSUB` lines of a job
script, as `-W 10:00` does above. The scripts have no `-P` line, so `bsub`
takes the allocation from `LSB_DEFAULTPROJECT`, or from `-P acc_xxx` on the
command line.

The GPU-hours in the scores count one GPU for the models of
`gentrex transcribe` and `gentrex select` and two for the model of
`gentrex extract`. They leave out the time that each server takes to load
its model, which `scores.json` gives as `server_start_seconds`.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `set SERVING to the serving folder` | Run `export SERVING=/path/to/serving` again. A new login has lost it, unless the line is in `~/.bashrc`. |
| `bsub` asks for a project or an allocation | Run `export LSB_DEFAULTPROJECT=acc_xxx` again, or add `-P acc_xxx` after `bsub`. |
| `submit the job from the gentrex folder` | Run `cd /path/to/gentrex` before `bsub`. |
| `module: command not found` in `prepare.sh` | Run `module load apptainer` and start the script again. |
| Hugging Face refuses a download | Accept Google's terms on the model's page, run `uvx --from huggingface_hub hf auth login` and start `prepare.sh` again. |
| `vLLM stopped; see above` or `serve.sh ended before ... was ready` | vLLM couldn't start, and its own messages are right above this line. Often the model's download is incomplete, or the job didn't get a GPU with 80 GB. If vLLM doesn't know `muse_glimmer`, `vllm.sif` is older than vLLM 0.28. |
| `serve.sh has no options for ...` | A settings file names a model that `serve.sh` doesn't know. Add a line for it. |
| Chrome names a missing library, such as `libnss3.so` | The node lacks a library that Chrome needs. Ask Minerva's support to install it. |
| `No usable sandbox!` in the log of `generate_reports.lsf` | Start Chrome without its sandbox. Save `exec /path/to/serving/chrome-headless-shell-linux64/chrome-headless-shell --no-sandbox "$@"` after a `#!/bin/bash` line in `chrome.sh`, run `chmod +x chrome.sh`, and give the path of `chrome.sh` to `--chrome` in `generate_reports.lsf`. |
| A case fails all attempts | The log names the values that the model didn't print. Submit the job again, which builds only the cases without a truth file. |
| A job ends in `TERM_RUNLIMIT` | Give it more time with `-W` and submit it again. The job that generates reports goes on where it stopped. |
| The pipeline job stopped after some commands had finished | Name the run folder of the last finished command, as in `OPTIONS="--from-run results/select/20261110-103801"`, and submit the job again. It starts with the command after it. |
| The pipeline job ends as failed although it wrote scores | A command had failed files. `scores.json` gives the `exit_status` and `failed_files` of each command under `performance`, and the command's `log.txt` names the files. |
