# Evaluate Gentrex

The scripts in this folder measure Gentrex. They make the benchmark reports,
run `gentrex transcribe`, `gentrex select`, `gentrex extract` and
`gentrex normalize` on them, and score the records against the reports'
truth files. One set of scripts runs on your own machine, and one on Mount
Sinai's Minerva cluster. The notebook
[`evaluation_results/pipeline.ipynb`](../evaluation_results/pipeline.ipynb)
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
| `minerva/serve.sh` | Starts vLLM with one model in a Minerva job. The two jobs call it. |
| `download_reference_files.sh` | Downloads ClinVar, HPO, MONDO and HGNC. The other scripts call it. |
| `settings.yaml` | The settings of the evaluation that differ from Gentrex's defaults |
| `hpo_normalization.py` | Measures the HPO matching of `gentrex normalize` on its own, which [Evaluate HPO matching](hpo-matching.md) describes |

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
lab report, with a synthetic footer on every page. Then build the rest:

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
6 minutes. Then the script runs the four commands on the native PDFs of the
100 dev reports. Before each command it starts vLLM with the command's
model, and afterwards it stops it. The first start of each model downloads
its weights. The last line of the output gives the main result and the
folder with the scores:

```text
2026-11-10 11:02:11,306 report accuracy 91.0% on 100 reports; wrote results/gentrex-bench/20261110-103752
```

Each report comes in five copies. To read the scanned and faxed copies as
well, name the copies in `COPIES`. `SPLIT=test` reads the 200 test reports:

```bash
COPIES="native scan fax mixed image" SPLIT=test evaluation/local/run_pipeline.sh
```

Tune Gentrex on the dev reports, and run the test reports only for the
numbers you report
([Choose the reports](../docs/development/run-benchmark.md#step-1-choose-the-reports)).

Options after the script's name go to `gentrex-bench/run.py`. This run skips
`gentrex select`, to measure what selecting pages is worth:

```bash
evaluation/local/run_pipeline.sh --no-select
```

[Run another setup](../docs/development/run-benchmark.md#run-another-setup)
lists more.

## Run on Minerva

### Step 1: Prepare

Download everything first, in an interactive session, so that the GPU jobs
spend none of their time on downloads. Start a session on a login node:

```bash
bsub -P acc_xxx -q interactive -n 4 -W 6:00 -R "rusage[mem=4000]" -Is /bin/bash
```

`-P` names your allocation. In the session, go to the Gentrex folder and run
the script with the path of your serving folder:

```bash
SERVING=/path/to/serving evaluation/minerva/prepare.sh
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
SERVING=/path/to/serving CASES="SYN-0001 SYN-0002" \
  bsub -P acc_xxx < evaluation/minerva/generate_reports.lsf
```

LSF passes `SERVING` and `CASES` to the job. Follow the job with `bjobs` and
`tail -f generate-reports.*.log`. Each case logs `passed on attempt 1`, or
why the attempt failed. Look at the two PDFs in
`data/gentrex-bench/v1/pdf/native/`, and then build the rest with more time:

```bash
SERVING=/path/to/serving bsub -P acc_xxx -W 8:00 < evaluation/minerva/generate_reports.lsf
```

`-W 8:00` on the command line replaces the hour that the script asks for. A
case that already has a truth file is skipped, so a job that ends in
`TERM_RUNLIMIT` can be submitted again and goes on where it stopped.

### Step 3: Run the pipeline

```bash
SERVING=/path/to/serving bsub -P acc_xxx < evaluation/minerva/run_pipeline.lsf
```

The job runs the four commands on the native PDFs of the dev reports and
scores the records. It serves the three models one after another, so it
holds two GPUs for its whole time. Follow it with `bjobs` and
`tail -f run-pipeline.*.log`. The last line gives the report accuracy and
the folder with the scores, as on your own machine.

`COPIES` and `SPLIT` work as they do there. A job reads its copies one after
another, so give it more time:

```bash
SERVING=/path/to/serving COPIES="native scan fax mixed image" SPLIT=test \
  bsub -P acc_xxx -W 10:00 < evaluation/minerva/run_pipeline.lsf
```

`OPTIONS` passes options to `gentrex-bench/run.py`, as in
`OPTIONS=--no-select`.

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

The notebook reads all runs and shows them as tables and plots. It follows
one report through the four commands, and then gives the accuracy, time and
tokens of a run as a whole and for each command:

```bash
uv run --group notebook jupyter lab evaluation_results/pipeline.ipynb
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
each copy. `run.py` links the PDFs of the split into its results folder,
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
| `COPIES` | `native` | the pipeline scripts | The copies to read, of `native`, `scan`, `fax`, `mixed` and `image` |
| `SPLIT` | `dev` | the pipeline scripts | The split to read, `dev`, `test` or `all` |
| `SERVING` | none | the Minerva scripts | The serving folder |
| `CASES` | all without a truth file | `generate_reports.lsf` | The cases to build. On your own machine, name them after the script. |
| `OPTIONS` | none | `run_pipeline.lsf` | More options of `run.py`. On your own machine, name them after the script. |
| `PORT` | `8000` | `local/generate_reports.sh` | The port of the vLLM that the script starts |

On Minerva, options of `bsub` on the command line replace the `#BSUB` lines
of a job script, as `-W 8:00` does above.

The two `serve.sh` scripts hold vLLM's options for each model, which are
those of the commands' own pages. They give the model of `gentrex extract`
two GPUs. If yours differ, change the model's line in `serve.sh`, and tell
the scorer with `--gpus`, as in
`evaluation/local/run_pipeline.sh --gpus 1 1 1`. The three numbers are the
GPUs of the models of `gentrex transcribe`, `gentrex select` and
`gentrex extract`, and the GPU-hours in the scores come from them.

To change a setting of Gentrex for the evaluation, add it to
`evaluation/settings.yaml`
([Change the settings](../docs/user-guide/runs-and-results.md#change-the-settings)).
If you name another model there, give `serve.sh` a line for it.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `set SERVING to the serving folder` | Put `SERVING=/path/to/serving` before the command, as in the steps above. |
| `submit the job from the gentrex folder` | Run `cd /path/to/gentrex` before `bsub`. |
| `vLLM stopped; see above` or `serve.sh ended before ... was ready` | vLLM couldn't start. Its own messages are right above this line. Often the model doesn't fit on the GPU, or its download is incomplete. |
| `serve.sh has no options for ...` | A settings file names a model that `serve.sh` doesn't know. Add a line for it. |
| `module: command not found` in `prepare.sh` | Run `module load apptainer` and start the script again. |
| A job ends in `TERM_RUNLIMIT` | Give it more time with `-W` and submit it again. The job that generates reports goes on where it stopped. A pipeline run starts from the beginning, so that its times cover the whole run. |
| A case fails all attempts | The log names the values that the model didn't print. Build that case again, or leave it out. |
| Chrome names a missing library or a sandbox error on Minerva | See [When the job fails](../docs/minerva/minerva.md#when-the-job-fails). |

The pages of the steps list more:
[Generate benchmark reports](../docs/development/generate-benchmark-reports.md#when-something-goes-wrong)
and
[Run the benchmark](../docs/development/run-benchmark.md#when-something-goes-wrong).
