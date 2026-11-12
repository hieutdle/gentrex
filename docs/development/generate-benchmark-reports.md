# Generate benchmark reports

This page shows how to make the synthetic benchmark reports, from the
reference files to the finished PDFs and truth files. Two commands do the
work:

- `sample` picks the cases and their truth. It takes about half a minute.
- `build` makes each report and checks it against its truth. A language model
  writes each report's text, so `build` needs a model server.

For the 300 cases of a version you get 1,500 PDFs, five versions of each
report, and 300 truth files.
[How the benchmark generator works](benchmark-generator.md) explains what
happens inside.

The reports hold no patient data, so you can make them on any computer. On
Mount Sinai's Minerva cluster, `build` runs as a batch job, which
[Generate benchmark reports on Minerva](../minerva/minerva.md#generate-benchmark-reports)
describes.

`evaluation/local/generate_reports.sh` does the steps of this page with one
command ([Evaluate Gentrex](../../evaluation/README.md)). The steps below do
the same by hand and explain each part.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](../user-guide/transcribe.md#step-1-install)).
- Google Chrome or Chromium, which prints the reports to PDF.
- A model server, either vLLM on an NVIDIA GPU with 80 GB of memory or a
  hosted provider. The next section explains both.
- About 600 MB of disk for the reference files, and about 4 MB per case for
  the reports, so 1.2 GB for 300 cases.

### Choose a model server

A model server runs a language model and answers requests over the network.
The generator works with any server that accepts requests in OpenAI's format,
which most servers and providers do. There are two ways to get one:

- **On your own GPU.** vLLM 0.28 or newer serves the default model, Muse
  Glimmer 30B, on one NVIDIA GPU with 80 GB of memory. Step 3 shows how.
- **From a hosted provider.** A company runs the model for you and charges
  by the token. Tokens are words or pieces of words, the unit in which models
  read and write. One report's text is about 1,500 tokens, plus the model's
  thinking if it thinks before it answers. You need the provider's address,
  an API key and its name for the model.

Any model works except a Gemma model. Gentrex extracts with Gemma and
would then read text that its own model family wrote.

## Step 1: Download the reference files

The cases come from five public files: ClinVar's variants, HPO's features
and their annotations of diseases, MONDO's diseases, and HGNC's gene symbols.
From the folder where you installed Gentrex, run:

```bash
mkdir -p data/clinvar data/ontology
curl -f -L -o data/clinvar/variant_summary_2026-11.txt.gz \
  https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/variant_summary_2026-11.txt.gz
curl -f -L -o data/ontology/phenotype-v2026-09-01.hpoa \
  https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/phenotype.hpoa
curl -f -L -o data/ontology/hp-base.json \
  https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/hp-base.json
curl -f -L -o data/ontology/mondo-base.json \
  https://github.com/monarch-initiative/mondo/releases/download/v2026-11-03/mondo-base.json
curl -f -o data/ontology/hgnc_complete_set_2026-10-06.txt \
  https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/hgnc_complete_set_2026-10-06.txt
```

If you have already run `gentrex normalize`, the last three files are in
`data/ontology/` and you can skip them.

## Step 2: Sample the cases

```bash
uv run python gentrex-bench/generator/generate.py --version v1 sample
```

This writes 300 cases to `data/gentrex-bench/v1/cases/`, one JSON file per
case:

- SYN-0001 to SYN-0100 are dev cases, for tuning Gentrex.
- SYN-0101 to SYN-0300 are test cases, for scoring Gentrex.

`--version` names the folder. The same settings and reference files always
give the same cases, so `v1` is the same on every computer.

## Step 3: Start the model server

Skip this step if you use a hosted provider.

If vLLM isn't installed yet, its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
shows how. Start it in a second terminal and leave it running while the
reports are built:

```bash
vllm serve meta-models/Muse-Glimmer-30B --max-model-len 20480 \
  --reasoning-parser muse_glimmer
```

The first start downloads the model's weights, about 60 GB, into
`~/.cache/huggingface/`. `--max-model-len` is the most tokens that one
request and its answer may hold. 20480 leaves room for the instructions, the
case and an answer of up to 16,384 tokens.

Muse Glimmer writes out its reasoning before the answer. A reasoning parser
separates the two, and `--reasoning-parser muse_glimmer` names the one for
this model. Without it the reasoning lands in the answer, and the generator
finds no JSON there.

vLLM is ready when `curl http://localhost:8000/v1/models` lists
`meta-models/Muse-Glimmer-30B`.

## Step 4: Tell the generator where the server is

The generator reads the server's address and key from the file `.env` in the
Gentrex folder. For vLLM on your own computer, `.env` needs these two lines:

```bash
GENTREX_BENCH_BASE_URL=http://localhost:8000/v1
GENTREX_BENCH_API_KEY=EMPTY
```

If you don't have a `.env` file yet, create it from the example file, which
already holds them:

```bash
cp .env.example .env
```

If you already have a `.env` file from running Gentrex, add the two lines to
it.

For a hosted provider, put its address, which usually ends in `/v1`, and your
key in these lines instead. Then put its name for the model in `build.model`
in `gentrex-bench/generator/settings.yaml`.

## Step 5: Build one report

Build the first case on its own, to see that everything works:

```bash
uv run --env-file .env python gentrex-bench/generator/generate.py --version v1 \
  build SYN-0001
```

`--env-file .env` hands the server's address to the command. When the
report is done, the log says:

```text
2026-11-09 18:02:11,412 SYN-0001 passed on attempt 1 (1532 output tokens)
2026-11-09 18:02:11,415 1 of 300 cases have a truth file; failed: none
```

Open `data/gentrex-bench/v1/pdf/native/SYN-0001.pdf` and read it. It should
read like a lab report, with a synthetic footer on every page.

## Step 6: Build the rest

Run the same command without a case ID:

```bash
uv run --env-file .env python gentrex-bench/generator/generate.py --version v1 build
```

`build` makes every case that has no truth file yet, eight at a time. The
time depends mostly on the model server. Printing, checking and copying take
about 2 seconds per report.

A report that fails the check gets its text written again, up to three
times. You can stop the build with Ctrl-C and run the command again later. It
skips the cases that already have a truth file.

## Check the result

The last line of the log counts the cases with a truth file and names the
cases that failed:

```text
2026-11-09 19:41:52,087 300 of 300 cases have a truth file; failed: none
```

`data/gentrex-bench/v1/` then holds:

| Path | Contents |
| --- | --- |
| `manifest.json` | The settings of `sample`, and the name and checksum of each reference file |
| `cases/<case>.json` | The sampled case, with its truth and the card that the model got |
| `responses/<case>-<attempt>.json` | The model's text for the report, with the model's name and token counts |
| `html/<case>.html` | The report's template, filled with the case and the model's text |
| `pdf/native/<case>.pdf` | The report with its text layer |
| `pdf/scan/<case>.pdf` | Page images, as from an office scanner |
| `pdf/fax/<case>.pdf` | Page images, as from a fax |
| `pdf/mixed/<case>.pdf` | The native PDF with about a third of its pages scanned |
| `pdf/image/<case>.pdf` | Clean page images whose only text is a document code |
| `truth/<case>.json` | The truth of a report that passed the check |

A truth file has five keys:

| Key | Holds |
| --- | --- |
| `case` | The split, template, test, result, challenge tags and writing model |
| `record` | What `gentrex extract` should write, with the page of each variant |
| `normalized` | What `gentrex normalize` should add, such as ISO dates and HGNC, MONDO and HPO IDs |
| `pages` | The text of each page of the native PDF |
| `distractors` | Values the report prints that must not be extracted |

The JSON and HTML files also hold a canary string, in the JSON files under
`canary`. It is a fixed sentence with a random ID that appears nowhere else.
Model makers can search their training data for it and leave the benchmark's
files out, so that no model is tested on reports it was trained on. The
native and image PDFs carry the string in their title, which no page shows.
The scanned and faxed copies have no text and carry none.

[Run the benchmark](run-benchmark.md) shows how to run Gentrex on the
reports and score its records against the truth files.

## Settings

The settings are in `gentrex-bench/generator/settings.yaml`, with a comment
on each:

| Setting | Default | What it does |
| --- | --- | --- |
| `sample.seed` | `gentrex-synthetic-1` | Starts the random stream that picks the cases. Another seed gives other cases. |
| `sample.dev` | `100` | The number of dev cases |
| `sample.test` | `200` | The number of test cases |
| `sample.clinvar`, `hpo`, `hpoa`, `mondo`, `hgnc` | the paths of step 1 | Where the reference files are |
| `build.model` | `meta-models/Muse-Glimmer-30B` | The model that writes the text, as the server names it |
| `build.max_tokens` | `16384` | The longest answer, in tokens. A longer answer counts as a failed attempt. |
| `build.timeout_seconds` | `900` | How long one answer may take |
| `build.attempts` | `3` | How often a failed report gets its text written again |
| `build.concurrency` | `8` | How many reports are written at the same time |

Change the settings before you sample a new version, and not during a build,
so that all reports of a version are made the same way.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `GENTREX_BENCH_BASE_URL is not set` | Add it to `.env` (step 4), and run with `uv run --env-file .env`. |
| `the model server refused the request` | The key is wrong, or the server has no model by that name. Compare `build.model` with the names at `GENTREX_BENCH_BASE_URL/models`. |
| `stopped with length` | The answer was longer than `build.max_tokens`. Raise it, and the server's `--max-model-len` with it. |
| `the answer isn't JSON` or `2 variant details for 1 variants` | The model's text doesn't fit the case, and the next attempt asks again. If every case fails this way, vLLM may run without `--reasoning-parser muse_glimmer` (step 3), or the server may not support JSON schemas in `response_format`. |
| `Chrome or Chromium is not installed; pass --chrome` | Install Chrome, or give the path of its program with `--chrome`, after `build`. |
| `... already has cases; choose another --version` | `sample` never overwrites a version. Use a new name, or delete the old folder. |
| A case fails all attempts | The log says why, such as a DNA change in the model's text that the case doesn't have. Run `build` again with that case ID, or leave the case out. |
