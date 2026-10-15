# Stage 3: Extract report data

Stage 3 turns each report into one record: the patient's identifiers, the
specimen, the test, the overall result, the patient's clinical features and
every variant reported. It sends the pages that stage 2 kept for a report to a
language model in one request, and the model answers with the record as JSON.
These records are Gentrex's final output.

Stage 3 reads `pages.jsonl` from a stage 2 run and writes `extractions.jsonl`,
with one line per report, to `results/extract/`. The model, Gemma 4 31B, runs
on two GPUs with 80 GB each, or on one GPU with more memory, such as a B200.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 2 run, in `results/pagedecide/`.
- Two NVIDIA GPUs with 80 GB each, or one B200, and
  [vLLM](https://docs.vllm.ai) 0.19.1 or newer.
- A [Hugging Face](https://huggingface.co) account, if the model download asks
  you to log in.

On Mount Sinai's Minerva cluster, follow
[Stage 3 on Minerva](minerva.md#stage-3-extract-report-data) instead of the
steps below. Then come back to [Check the result](#check-the-result).

## Step 1: Start the model server

If the stage 2 server is still running, stop it with Ctrl-C in its terminal.
Every stage's server uses port 8000, and this model needs the GPUs' memory.

If vLLM isn't installed yet, install it as its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
describes. Then start it in a second terminal, and leave it running while
Gentrex works. On two GPUs:

```bash
vllm serve google/gemma-4-31B-it \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.95
```

- `google/gemma-4-31B-it` is the model's name on Hugging Face, and the name
  Gentrex asks for (`extract.model` in settings.yaml). The first start
  downloads the model's [weights](../README.md#terms), about 62 GB, into
  `~/.cache/huggingface/`.
- `--tensor-parallel-size 2` splits the model across two GPUs
  ([tensor parallelism](../README.md#terms)), so each GPU holds half of the
  weights. Leave it out on a single B200.
- `--max-model-len 32768` sets the [context length](../README.md#terms), the
  most tokens one request can hold. Tokens are words or pieces of words. The
  instruction and the schema take about 2,000 tokens, and the answer up to
  4,096 (`extract.max_tokens` in settings.yaml). That leaves about 26,000
  tokens for the report's pages. A longer report fails, as
  [When something goes wrong](#when-something-goes-wrong) describes.
- `--gpu-memory-utilization 0.95` lets vLLM use 95% of each GPU's memory. The
  model's weights take 62 GB. The rest becomes the
  [KV cache](../README.md#terms), the memory that holds the reports vLLM is
  processing. On one 80 GB GPU, too little is left for a 32,768-token request,
  so vLLM stops at startup.

vLLM's [Gemma 4 guide](https://recipes.vllm.ai/Google/gemma-4-31B-it) adds
`--reasoning-parser gemma4` to some of its commands. Leave it out. A reasoning
parser separates the model's reasoning from its answer, and Gentrex turns
[thinking](../README.md#terms) off, so there is no reasoning to separate.
With thinking off, the parser can also stop vLLM from enforcing the schema
([vLLM issue 39130](https://github.com/vllm-project/vllm/issues/39130)).

If the download stops with an error that access to the model is restricted,
accept Google's terms on the
[model's page](https://huggingface.co/google/gemma-4-31B-it) and log in, as
for the [stage 2 model](stage2.md#step-1-start-the-model-server). Then start
vLLM again.

vLLM is ready when `curl http://localhost:8000/v1/models` lists
`google/gemma-4-31B-it`. Gentrex sends the text of every report to this
server, so run it on a machine approved for patient data.

## Step 2: Point Gentrex at the model server

Stage 3 reads the same two values in `.env` as stage 2,
`GENTREX_LLM_BASE_URL` and `GENTREX_LLM_API_KEY`. If you set them for stage 2,
there is nothing to change. Otherwise, do
[stage 2, step 2](stage2.md#step-2-point-gentrex-at-the-model-server).

## Step 3: Run

```bash
uv run --env-file .env gentrex stage3
```

Gentrex reads the newest finished stage 2 run, `results/pagedecide/latest`,
and writes a new folder named after the time the run started, such as
`results/extract/20261014-150000/`. To read another stage 2 run:

```bash
uv run --env-file .env gentrex stage3 --input results/pagedecide/20261014-131500
```

While it runs, Gentrex prints one line per report. The last line counts the
reports and the failed reports, and gives the speed in reports per minute.

## Check the result

The run folder holds three files:

| File | Contents |
| --- | --- |
| `extractions.jsonl` | One record per report. |
| `run.yaml` | The command, the stage 2 run that was read, and the settings, including the instruction and the schema. |
| `log.txt` | What Gentrex printed during the run. |

`results/extract/latest` points to the newest finished run.
[Runs and results](../README.md#runs-and-results) explains run folders and
`latest`.

`extractions.jsonl` has one line per report, in the order of the input. Each
line is a JSON object, shown here with most of `data` left out:

```json
{"file": "report-01.pdf", "pages": [1, 2], "data": {"mrn": "SYN-MRN-0001", "test_name": "Developmental Disorders Panel", "variants": [{"page": 1, "gene_symbol": "SCN2A", "hgvs_c": "c.2815G>A", "classification_raw": "VUS", "classification": "uncertain_significance"}]}, "error": null}
{"file": "report-02.pdf", "pages": [1, 3], "data": {"mrn": null, "test_name": "Inherited Arrhythmia Panel", "variants": []}, "error": "page 2: stage 1: APITimeoutError: Request timed out."}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `pages` | The pages sent to the model. |
| `data` | The record, with one entry per field of the schema. `null` if the report got no answer. |
| `error` | The pages left out because of a stage 1 error, and why the request failed. `null` when nothing went wrong. |

`data` and `error` together tell you how complete a record is:

| `data` | `error` | Meaning |
| --- | --- | --- |
| set | `null` | Complete. The model read every kept page. |
| set | set | Pages are missing. What is stated only on them is not in the record. |
| `null` | set | Nothing was extracted. |

A record can miss pages, or be missing altogether, for three reasons:

- A page with a stage 1 error has no text. Gentrex leaves it out of the
  request, and the record's `error` names it.
- A report whose kept pages all have stage 1 errors gets no request, so its
  `data` is `null`.
- Stage 2 passes on only the pages it keeps, so a report with no kept page gets
  no record at all.

To read one record with one field per line:

```bash
head -n 1 results/extract/latest/extractions.jsonl | uv run python -m json.tool
```

To count the reports that got no data:

```bash
grep -c '"data": null' results/extract/latest/extractions.jsonl
```

To list the records with an error:

```bash
grep -v '"error": null' results/extract/latest/extractions.jsonl
```

To load the records in Python with pandas, with one row per variant:

```python
import pandas as pd

records = pd.read_json("results/extract/latest/extractions.jsonl", lines=True)
variants = pd.json_normalize(
    records.dropna(subset=["data"]).to_dict("records"),
    record_path=["data", "variants"],
    meta=["file"],
)
```

In R, `jsonlite` reads the file into a data frame with one row per report:

```r
records <- jsonlite::stream_in(file("results/extract/latest/extractions.jsonl"))
```

The model can fill in a value that the report doesn't state. It may take the
value from its own knowledge of a gene or variant, or copy the example from a
field's description in the schema. Before you rely on the records, compare
some of them with their PDFs, field by field, including the fields that came
back `null`.

## How it works

Gentrex sends all kept pages of a report in one request, in page order. Each
page starts with a line such as `--- PAGE 2 ---`, so the model can tell which
page a variant is on. The model answers with one JSON object for the whole
report.

The fields of that object are defined in the extraction schema,
[`schema.yaml`](../src/gentrex/defaults/schema.yaml). Gentrex uses the schema
in two ways. The model reads it to learn what each field means, because
Gentrex sends it as JSON after the instruction (`extract.instruction` in
settings.yaml). And vLLM enforces it as the answer format, which is called
[structured output](../README.md#terms). The model can then write only JSON
that follows the schema and has every field.

A field the report doesn't state comes back `null`, and a report without
variants gets an empty `variants` list.

Four fields take one value from a fixed list: `classification`, `zygosity`,
`parental_origin` and `mode_of_inheritance`. Each comes right after a `_raw`
field that holds the report's own wording. The model writes the fields in
schema order, so it first copies the wording and then picks the closest
allowed value. A report that says "Pathogenic (Class 5)" gets
`"classification_raw": "Pathogenic (Class 5)"` and then
`"classification": "pathogenic"`. `test_type`, such as `exome`, follows
`test_name` in the same way.

Gemma 4 has a thinking mode, in which it writes out its reasoning before the
answer. Gentrex turns it off, so the answer is the record and nothing else.

## Settings

The fields to extract are in
[`src/gentrex/defaults/schema.yaml`](../src/gentrex/defaults/schema.yaml).
The instruction, the model and the other stage 3 settings are under `extract`
in [`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml).
A comment above each value explains it.

The schema is a [JSON Schema](https://json-schema.org/). The report-level
fields are under `properties`, and the fields of each variant are under
`variants.items.properties`. Each field is one block:

```yaml
  test_name:
    description: >-
      Name of the test, panel or assay (e.g. Inherited Arrhythmia Panel,
      Proband Exome with Secondary Findings).
    type: [string, "null"]
```

- To add a field, add a block. To remove one, delete its block.
- Keep `"null"` in the `type` of every field a report may not state, with the
  quotes. Without quotes, YAML reads `null` as "no value" instead of the JSON
  Schema type named "null". Without the type, the model must make up a value
  when the report states none.
- Write the description for the model, which reads it. Say what the field
  holds and when to fill it. An example value shows the format, but the model
  may copy it into a record whose report doesn't state the field.
- For a field with a fixed list of values, add an `enum` that ends with `null`
  without quotes, so that the allowed value is null itself and not the text
  "null". Put a `_raw` field for the report's own wording right before it, as
  `classification_raw` and `classification` do.

`run.yaml` records the instruction and the schema of every run. To see what
changed between two runs:

```bash
diff results/extract/20261014-150000/run.yaml results/extract/20261015-090000/run.yaml
```

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report has a complete record. | Nothing. |
| 1 | No finished stage 2 run was found (`pages.jsonl not found; run stage 2 first`), some reports have an error, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 2. |

A report is listed as failed in two cases:

- **One of its pages has a stage 1 error.** The record is written from the
  other pages, and `error` starts with `page N: stage 1:`. Run stage 1 again,
  then stages 2 and 3.
- **The request failed.** `data` is `null`, and `error` says why. If the error
  is a connection error, the server was down or busy, even after Gentrex's
  [retries](../README.md#runs-and-results). Check that the server is running,
  then run stage 3 again.

Three errors come from the report rather than the server:

- `ValueError: answer cut off at max_tokens (4096)` means that the record was
  longer than `extract.max_tokens` allows. Raise `max_tokens` in
  settings.yaml, and raise `timeout_seconds` by the same factor, because a
  longer answer takes longer to write. Then run again. If the report lists
  few variants, the model was more likely stuck repeating itself, for example
  writing spaces without end. Then also start vLLM with
  `--structured-outputs-config '{"disable_any_whitespace": true}'`, which
  leaves no room for spaces between the parts of the JSON.
- `APITimeoutError: Request timed out.` means that the answer took longer
  than `extract.timeout_seconds` to write, on all four tries. Raise
  `timeout_seconds` in settings.yaml and run again.
- `BadRequestError: Error code: 400`, with a message about the maximum context
  length, means that the report is longer than `--max-model-len` allows.
  Start vLLM with a higher `--max-model-len` and run again. vLLM refuses to
  start if the GPUs lack the memory for it.

If every report fails with the same error, the cause is the server. Check that
it runs `google/gemma-4-31B-it` with the model's own chat template, and that it
supports structured output with a JSON schema (`response_format`), as vLLM
does.

A traceback means the run stopped early.
[Runs and results](../README.md#runs-and-results) explains the common causes.
