# Evaluate Gentrex

The scripts in this folder measure Gentrex. They make the benchmark reports,
run `gentrex transcribe`, `gentrex select`, `gentrex extract` and
`gentrex normalize` on them, and score the records against the reports'
truth files. One set of scripts runs on your own machine, and one on Mount
Sinai's Minerva cluster. The notebook
[`presentation.ipynb`](../presentation.ipynb)
then shows the results.

The benchmark reports are synthetic and hold no patient data, so the
evaluation can run on any computer that can serve Gentrex's models.

| Path | What it does |
| --- | --- |
| `local/generate_reports.sh` | Makes the benchmark reports on your machine |
| `local/run_pipeline.sh` | Runs Gentrex on the reports and scores it, on your machine |
| `local/serve.sh` | Starts vLLM with one model. The two scripts above call it. |
| `minerva/prepare.sh` | Downloads what the two Minerva jobs need |
| `minerva/generate_reports.lsf` | The Minerva job that makes the benchmark reports |
| `minerva/run_pipeline.lsf` | The Minerva job that runs Gentrex on the reports and scores it |
| `minerva/submit_pipeline.sh` | Submits the seven runs of `run_pipeline.lsf` as short 1-GPU jobs |
| `minerva/serve.sh` | Starts vLLM with one model in a Minerva job. The two jobs call it. |
| `download_reference_files.sh` | Downloads ClinVar, HPO, MONDO and HGNC. The other scripts call it. |
| `settings.yaml` | The settings of the evaluation that differ from Gentrex's defaults |
| `settings-extract-26b.yaml` | The same settings with Gemma 4 26B-A4B as the extraction model, for the comparison run |
| `hpo_normalization.py` | Measures the HPO matching of `gentrex normalize` on its own, which [Evaluate HPO matching](hpo-matching.md) describes |
| `mondo_normalization.py` | Measures the MONDO matching of `gentrex normalize` on its own, which [Evaluate MONDO matching](mondo-matching.md) describes |

## Before you start

On your own machine you need:

- Gentrex installed
  ([Transcribe PDF pages](../docs/user-guide/transcribe.md#step-1-install)).
- [vLLM](https://docs.vllm.ai) 0.28 or newer, and two NVIDIA GPUs with 80 GB
  each for the model of `gentrex extract`.
- Google Chrome or Chromium, which prints the reports to PDF.
- About 185 GB of free disk for the four models, 600 MB for the reference
  files and 1.2 GB for the reports.

On Minerva you need:

- An account, an allocation and the Gentrex folder, from
  [Log in](../docs/minerva/minerva.md#log-in) and
  [Install Gentrex](../docs/minerva/minerva.md#install-gentrex).
- A serving folder with about 215 GB free, for vLLM and the four models. The
  scripts read its path from `SERVING`. If the folder already holds a
  `vllm.sif` older than vLLM 0.28, delete it, and `prepare.sh` pulls the
  newest one.

You don't have to make the reports yourself. To check published numbers, put
the published `pdf/` and `truth/` folders into `data/gentrex-bench/v1/` and
skip the step that generates the reports. A language model writes the text
of the reports, so reports that you generate differ from the published ones,
and scores compare only on the same reports.

## Run on your own machine

Run the scripts from the Gentrex folder.

### Step 1: Generate the reports

Build two reports first:

```bash
evaluation/local/generate_reports.sh SYN-0001 SYN-0002
```

The script downloads the reference files, about 600 MB, and samples the 300
cases of the benchmark. Then it starts vLLM with the writing model,
Muse Glimmer 30B, builds the two reports and stops vLLM. The first start
downloads the model's weights, about 60 GB.

Open `data/gentrex-bench/v1/pdf/native/SYN-0001.pdf`. It should read like a
lab report, with a synthetic footer on every page. Then build the rest. To
build all reports right away, skip the two and run only this command:

```bash
evaluation/local/generate_reports.sh
```

Without case IDs, the script builds every case that has no truth file yet.
You can stop it with Ctrl-C and run it again later.

To have a hosted provider write the reports, put its address and your key in
`.env` and its name for the model in
`gentrex-bench/generator/settings.yaml`, as
[Generate benchmark reports](../docs/development/generate-benchmark-reports.md#step-4-tell-the-generator-where-the-server-is)
describes. Then run the script with the `.env` file, and it starts no vLLM:

```bash
uv run --env-file .env evaluation/local/generate_reports.sh
```

### Step 2: Run the pipeline

```bash
evaluation/local/run_pipeline.sh
```

The first run builds the HPO index of `gentrex normalize`, which takes about
6 minutes. Then the script makes four runs of the 300 benchmark reports, one after
another. Each report comes in three copies, and each copy gets a run: the
native PDFs, and the scanned and faxed copies, which go
through OCR. The fourth run reads the native PDFs again without
`gentrex select`, to measure what selecting pages is worth.

A run is the four commands and the scoring. Before each command the script
starts vLLM with the command's model, and afterwards it stops it. The first
start of each model downloads its weights. Each run ends with a line that
gives its main result and the folder with its scores:

```text
2026-11-10 11:02:11,306 report accuracy 91.0% on 300 reports; wrote results/gentrex-bench/20261110-103752
```

`COPIES` names the copies to read, and `NO_SELECT` the copies to read once
more without `gentrex select`. The run of each copy in `SELECT_METHODS` also
chooses the pages in two other ways, to compare `gentrex select` with them
([Compare ways to choose pages](../docs/development/run-benchmark.md#compare-ways-to-choose-pages)).
This makes only the run of the native PDFs, without that comparison:

```bash
COPIES=native NO_SELECT= SELECT_METHODS= evaluation/local/run_pipeline.sh
```

Options after the script's name go to every run of `gentrex-bench/run.py`,
as `--no-hpo` does here:

```bash
evaluation/local/run_pipeline.sh --no-hpo
```

[Run another setup](../docs/development/run-benchmark.md#run-another-setup)
lists more.

## Run on Minerva

[Evaluate Gentrex on Minerva](../docs/minerva/evaluate.md) has these steps
on one page, from the installation to the scores.

### Step 1: Prepare

Name your allocation and your serving folder once, on a login node. The
commands below read the two names, and `~/.bashrc` keeps them for later
sessions:

```bash
export LSB_DEFAULTPROJECT=acc_xxx
export SERVING=/path/to/serving
```

Download everything first, in an interactive session, so that the GPU jobs
spend none of their time on downloads. Start a session on a login node:

```bash
bsub -q interactive -n 4 -W 6:00 -R "rusage[mem=4000]" -Is /bin/bash
```

In the session, go to the Gentrex folder and run the script:

```bash
evaluation/minerva/prepare.sh
```

It installs the packages of `gentrex normalize`, downloads the reference
files, builds the HPO index and samples the cases. Into the serving folder
it puts vLLM, Gentrex's three models, the writing model and Chrome. What is
already there is kept, so you can run the script again if the session ends
early. It ends with `Minerva is ready for generate_reports.lsf and
run_pipeline.lsf`.

The two Gemma models need Google's terms accepted. If Hugging Face refuses a
download, accept the terms on the model's page, log in with
`uvx --from huggingface_hub hf auth login` and run the script again.

### Step 2: Generate the reports

Submit the job from the Gentrex folder, on a login node. Build two reports
first:

```bash
cd /path/to/gentrex
CASES="SYN-0001 SYN-0002" bsub < evaluation/minerva/generate_reports.lsf
```

LSF passes `SERVING` and `CASES` to the job. Follow the job with `bjobs` and
`tail -f generate-reports.*.log`. Each case logs `passed on attempt 1`, or
why the attempt failed. Look at the two PDFs in
`data/gentrex-bench/v1/pdf/native/`, and then build the rest. To build all
reports right away, skip the two and submit only this command:

```bash
bsub < evaluation/minerva/generate_reports.lsf
```

The hour that the job asks for is enough for the 300 reports. A case that
already has a truth file is skipped, so a job that ends in `TERM_RUNLIMIT`
can be submitted again and goes on where it stopped.

### Step 3: Run the pipeline

```bash
bsub < evaluation/minerva/run_pipeline.lsf
```

The job makes seven runs of the 300 reports in eight hours, on one H100 NVL
GPU. It reads `native` three times, the first also with `--select-methods`,
then `scan`, `fax`, `native` with `--no-select`, and `native` with Gemma 4
26B-A4B as the extraction model. The three models of a run are served one
after another, each stopped before the next starts. To wait less in the
queue and run them concurrently on separate GPUs, run
`evaluation/minerva/submit_pipeline.sh` to submit seven short 1-GPU jobs
(2 to 3 hours each). Follow jobs with `bjobs` and
`tail -f run-pipeline.*.log`. Each run ends with a line that gives its
report accuracy and the folder with its scores.

`COPIES`, `NO_SELECT`, `SELECT_METHODS`, and `REPEATS` work as they do on your own
machine (`REPEATS` defaults to `3` on Minerva and `1` locally). To give a job more time, pass `-W` to `bsub`, as in
`bsub -W 10:00 < evaluation/minerva/run_pipeline.lsf`.
`EXTRACT_26B=` leaves out the run with the 26B extraction model.

`OPTIONS` passes options to every run of `gentrex-bench/run.py`, as in
`OPTIONS=--no-hpo`.

Run one such job at a time in a Gentrex folder. `run.py` finds the run that
a command just made through the command's `latest` link, which a second job
would move.

## Check the result

Each run of the pipeline writes a folder such as
`results/gentrex-bench/20261110-103752/`, with the scores as tables in
`scores.md`, every number in `scores.json` and every wrong value in
`errors.jsonl`.
[Run the benchmark](../docs/development/run-benchmark.md#check-the-result)
explains them.

The notebook `presentation.ipynb` holds the text, tables and figures of the
paper, written from the scores:

```bash
uv run --group notebook jupyter lab presentation.ipynb
```

`--group notebook` installs JupyterLab, pandas and matplotlib on the first
run.

To read the notebook on your own computer after a run on Minerva, copy the
run's folder under `results/gentrex-bench/` there. The part that follows one
report also needs the run folders of the four commands, which `scores.json`
names under `runs`, and the benchmark version in `data/gentrex-bench/`. All
of these hold only synthetic reports. Results of real reports must stay on
Minerva.

## How it works

`generate_reports.sh` and `generate_reports.lsf` run
`gentrex-bench/generator/generate.py`, first `sample` and then `build`.
[Generate benchmark reports](../docs/development/generate-benchmark-reports.md)
goes through the same steps by hand, and
[How the benchmark generator works](../docs/development/benchmark-generator.md)
explains what happens inside.

`run_pipeline.sh` and `run_pipeline.lsf` run `gentrex-bench/run.py` once for
each copy, with `--select-methods` for each copy in `SELECT_METHODS`, and
once more with `--no-select` for each copy in `NO_SELECT`. `run.py` links
the benchmark PDFs into its results folder,
runs the four commands on them and scores the last one's records. It calls
`serve.sh` with a model's name and a free port, waits until the server
answers and stops it after the command.
[Run the benchmark](../docs/development/run-benchmark.md#how-it-works)
explains the scoring.

Both pipeline scripts pass `evaluation/settings.yaml` to every command. It
turns on the lookup of ClinVar IDs in `gentrex normalize`, so that the
scorer can score them.

## Settings

The scripts read these environment variables:

| Variable | Default | Read by | What it sets |
| --- | --- | --- | --- |
| `VERSION` | `v1` | the scripts of the steps | The benchmark version, a folder under `data/gentrex-bench/` |
| `COPIES` | all three | the pipeline scripts | The copies to read, of `native`, `scan` and `fax` |
| `NO_SELECT` | `native` | the pipeline scripts | The copies to read once more without `gentrex select`. `NO_SELECT=` reads none. |
| `SELECT_METHODS` | `native` | the pipeline scripts | The copies whose pages are also chosen in two other ways. `SELECT_METHODS=` compares none. |
| `REPEATS` | `1` local, `3` Minerva | the pipeline scripts | Total runs of `REPEAT_COPY` (`native` by default) to measure run-to-run repeatability. |
| `SERVING` | none | the Minerva scripts | The serving folder |
| `CASES` | all without a truth file | `generate_reports.lsf` | The cases to build. On your own machine, name them after the script. |
| `OPTIONS` | none | `run_pipeline.lsf` | More options of `run.py`, for every run. On your own machine, name them after the script. |
| `PORT` | `8000` | `local/generate_reports.sh` | The port of the vLLM that the script starts |

On Minerva, options of `bsub` on the command line replace the `#BSUB` lines
of a job script, as `-W 10:00` does above.

The two `serve.sh` scripts hold vLLM's options for each model, which are
those of the commands' own pages. The local one gives the model of
`gentrex extract` two GPUs, and Minerva's gives it one H100 NVL. If yours
differ, change the model's line in `serve.sh`, and tell
the scorer with `--gpus`, as in
`evaluation/local/run_pipeline.sh --gpus 1 1 1`. The three numbers are the
GPUs of the models of `gentrex transcribe`, `gentrex select` and
`gentrex extract`, and the GPU-hours in the scores come from them.

To change a setting of Gentrex for the evaluation, add it to
`evaluation/settings.yaml`
([Change the settings](../docs/user-guide/runs-and-results.md#change-the-settings)).
If you name another model there, give `serve.sh` a line for it. On Minerva,
also add the model to the list in `minerva/prepare.sh` and run the script
again, because the jobs serve only the models in the serving folder.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `set SERVING to the serving folder` | Run `export SERVING=/path/to/serving` again, as in step 1. |
| `submit the job from the gentrex folder` | Run `cd /path/to/gentrex` before `bsub`. |
| `vLLM stopped; see above` or `serve.sh ended before ... was ready` | vLLM couldn't start. Its own messages are right above this line. Often the model doesn't fit on the GPU, or its download is incomplete. |
| `serve.sh has no options for ...` | A settings file names a model that `serve.sh` doesn't know. Add a line for it. |
| `module: command not found` in `prepare.sh` | Run `module load apptainer` and start the script again. |
| A job ends in `TERM_RUNLIMIT` | Give it more time with `-W` and submit it again. The job that generates reports goes on where it stopped. A pipeline run starts from the beginning, unless you name the run folder of its last finished command with `--from-run` ([Go on after a run that stopped](../docs/development/run-benchmark.md#go-on-after-a-run-that-stopped)). |
| A case fails all attempts | The log names the values that the model didn't print. Build that case again, or leave it out. |
| Chrome names a missing library or a sandbox error on Minerva | See [When the job fails](../docs/minerva/minerva.md#when-the-job-fails). |

The pages of the steps list more:
[Generate benchmark reports](../docs/development/generate-benchmark-reports.md#when-something-goes-wrong)
and
[Run the benchmark](../docs/development/run-benchmark.md#when-something-goes-wrong).
