# gentrex-bench

gentrex-bench tests Gentrex on fictional genetic test reports whose true
content is known. Its generator makes the reports. You give it a seed and a
number of cases, and for each case you get the report as four PDFs (native,
scanned, faxed and mixed) and a truth file with what `gentrex extract` and
`gentrex normalize` should write. A scorer that compares Gentrex's output
with the truth files comes next.
[Benchmark design](../docs/development/benchmark.md) explains the plan and
what it takes from other benchmarks.

The reports hold no patient data, so the generator runs on any machine. On
Minerva it runs as a batch job, which
[Generate benchmark reports](../docs/minerva/minerva.md#generate-benchmark-reports)
describes.

## Before you start

You need:

- Gentrex installed
  ([Transcribe PDF pages](../docs/user-guide/transcribe.md#step-1-install)).
- Google Chrome or Chromium, which prints the reports to PDF.
- A model server with an OpenAI-compatible API, such as vLLM on your own
  GPUs or a hosted provider. The model must not be a Gemma model, because
  Gentrex extracts with Gemma.
- About 600 MB of disk for the reference files.

## Step 1: Download the reference files

```bash
mkdir -p data/ontology data/clinvar
curl -f -L -o data/clinvar/variant_summary_2026-11.txt.gz \
  https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/variant_summary_2026-11.txt.gz
curl -f -L -o data/ontology/phenotype-v2026-09-01.hpoa \
  https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/phenotype.hpoa
```

These are ClinVar's release of November 2026 and HPO's disease annotations.
The generator also reads `hp-base.json`, `mondo-base.json` and the HGNC
complete set. If you have run `gentrex normalize`, they are already in
`data/ontology/`. If not, download them as
[Normalize report data](../docs/user-guide/normalize.md) shows.

## Step 2: Sample the cases

```bash
uv run python gentrex-bench/generator/generate.py --version v1 sample
```

This writes 100 dev cases and 200 test cases to
`data/gentrex-bench/v1/cases/`, and takes about half a minute. The same
settings and reference files always give the same cases.

## Step 3: Start the model server

The model is `build.model` in `gentrex-bench/generator/settings.yaml`,
gpt-oss-120b unless you change it. It fits on one GPU with 80 GB:

```bash
vllm serve openai/gpt-oss-120b --max-model-len 40960
```

Then add the server to `.env`:

```bash
GENTREX_BENCH_BASE_URL=http://localhost:8000/v1
GENTREX_BENCH_API_KEY=EMPTY
```

For a hosted provider, put its URL and your key there instead, and its name
for the model in `build.model`.

## Step 4: Build the reports

Build two cases first:

```bash
uv run --env-file .env python gentrex-bench/generator/generate.py --version v1 \
  build SYN-0001 SYN-0002
```

Open their PDFs in `data/gentrex-bench/v1/pdf/native/` and read them. If
they look right, run the same command without the case IDs to build the
rest.

The log has a line for each case, either `passed on attempt 1` or the values
that the model left out. A case that fails is written again, up to three
times. A case that already has a truth file is skipped, so you can stop the
build and start it again later.

## Check the result

`data/gentrex-bench/v1/` holds:

| Path | Contents |
| --- | --- |
| `manifest.json` | The `sample` settings, and the name and checksum of each reference file |
| `cases/<case>.json` | The sampled case: its truth, and the card that the model got |
| `responses/<case>-<attempt>.json` | The model's answer, with the model's name and the token counts |
| `html/<case>.html` | The report as the model wrote it |
| `pdf/native/<case>.pdf` | The report with its text layer |
| `pdf/scan/<case>.pdf` | An image-only copy, as from an office scanner |
| `pdf/fax/<case>.pdf` | An image-only copy, as from a fax |
| `pdf/mixed/<case>.pdf` | The native PDF with about a third of its pages scanned |
| `truth/<case>.json` | The truth of a case that passed the check |

A truth file has five keys:

| Key | Holds |
| --- | --- |
| `case` | The split, lab, test, result, challenge tags and writing model, and which pages of the mixed PDF are scanned |
| `record` | What `gentrex extract` should write, with the page of each variant |
| `normalized` | What `gentrex normalize` should add, such as ISO dates and HGNC, MONDO and HPO IDs |
| `pages` | The text of each page of the native PDF |
| `distractors` | Values the report prints that must not be extracted |

To run Gentrex on the reports, give `gentrex transcribe` one of the PDF
folders as its input, such as `pdf/fax/`.

## How it works

Each case starts with one of eight fictional labs, in
`gentrex-bench/generator/labs.py`, and a test and a result. Each lab has its
own layout and wording. Labs E and H appear only in the test cases. The test
is a panel, an exome, a single gene, a carrier screen or the mitochondrial
genome, and the result is positive, negative, uncertain, mixed, carrier, or
negative with a secondary finding.

The variants are ClinVar variants of genes from the test's clinical area. A
variant qualifies when ClinVar classifies it as pathogenic, likely pathogenic
or of uncertain significance, with criteria and without conflicts, and when
HPO annotates its condition. The condition gives the mode of inheritance and
the patient's features, and the zygosity follows from the inheritance and
the patient's sex.

Each case also gets one to three challenge tags, which make the report
harder in a known way. `legacy_gene_symbol` prints a gene's previous HGNC
symbol, for example, and `gene_list_distractor` adds a list of genes without
findings. Each tag appears about equally often.

The model gets the case as a card with the values to print, the lab's
layout, the number of pages and the instructions of the tags.
`gentrex-bench/generator/prompt.md` tells it how to write the report as
HTML. It makes up the rest, such as the clinicians' names and the narrative.
Chrome prints the HTML to PDF, because Gentrex reads PDFs.

The check reads the PDF's text with pdfplumber, as `gentrex transcribe`
does, and looks for every true value, every distractor and the synthetic
footer of each page. A value that wraps inside a table cell is found line by
line and logged as a warning.

The scanned and faxed copies are made with Pillow and numpy, from a random
stream seeded with the case ID, so the same PDF always gives the same copy.
A scan gets a slight skew, blur, noise and JPEG compression. A fax loses half
its vertical resolution, gets a larger skew, turns black and white, and gets
speckles and streaks.

## Settings

The settings are in
[`gentrex-bench/generator/settings.yaml`](generator/settings.yaml), with a
comment on each. `sample` has the seed, the numbers of cases and the paths of
the reference files. `build` has the writing model, its longest answer, its
time limit, the number of attempts and how many reports are written at the
same time. The model server's address and key come from `.env`.

Change the settings before you sample a new version, not during a build, so
that every report of a version is made the same way.

## When something goes wrong

| Problem | What to do |
| --- | --- |
| `GENTREX_BENCH_BASE_URL is not set` | Add it to `.env` (step 3) and run with `uv run --env-file .env`. |
| `the model server refused the request` | The key is wrong, or the server has no model by that name. Compare `build.model` with the names at `GENTREX_BENCH_BASE_URL/models`. |
| `stopped with length` | The answer was longer than `build.max_tokens`. Raise it, and the server's `--max-model-len` with it. |
| `Chrome or Chromium is not installed; pass --chrome` | Install Chrome, or give the path of its executable with `--chrome`. |
| `... already has cases; choose another --version` | `sample` never overwrites a version. Use a new name, or delete the old folder. |
| A case fails all attempts | The log names the values the model didn't print. Run `build` again with that case ID, or leave the case out. |
