# Extract report data

`gentrex extract` turns each report into one record with the patient's
identifiers, the specimen, the test, the overall result, the patient's clinical
features and every reported variant. It writes the records to
`extractions.jsonl` in `results/extract/`, one line per report.
[`gentrex normalize`](normalize.md) then adds standard values to them.

A language model, Gemma 4 31B, reads the pages that `gentrex select` kept for a
report and answers with the record as JSON.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex select`, in `results/select/`.
- Two NVIDIA GPUs with 80 GB each, or one with more memory, such as a B200,
  and [vLLM](https://docs.vllm.ai) 0.19.1 or newer.
- A [Hugging Face](https://huggingface.co) account, if the model download asks
  you to log in.

On Mount Sinai's Minerva cluster, follow
[Extract report data on Minerva](../minerva/minerva.md#extract-report-data) instead of the
steps below. Then come back to [Check the result](#check-the-result).

## Step 1: Start the model server

If the server for `gentrex select` is still running, stop it with Ctrl-C in its
terminal. Every model server uses port 8000, and this model needs the GPUs'
memory.

If vLLM isn't installed yet, its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
shows how. Gentrex sends the text of every report to the server, so use a
machine approved for patient data. Start vLLM in a second terminal and leave it
running while Gentrex works. On two GPUs:

```bash
vllm serve google/gemma-4-31B-it \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.95
```

The first start downloads the model's weights, about 62 GB, into
`~/.cache/huggingface/`. Gentrex asks for the model by its Hugging Face name
(`extract.model` in settings.yaml). `--tensor-parallel-size 2` splits the
model across the two GPUs, so each GPU stores half of the weights. Leave it out
on a single B200.

`--max-model-len 32768` sets the context length, the most tokens one request
can hold. Tokens are words or pieces of words. The instruction and the schema
take about 2,000 tokens and the answer up to 4,096 (`extract.max_tokens` in
settings.yaml). That leaves about 26,000 tokens for the report's pages. A
longer report fails ([When something goes wrong](#when-something-goes-wrong)).

`--gpu-memory-utilization 0.95` lets vLLM use 95% of each GPU's memory. The
weights take 62 GB, and the rest becomes the KV cache, where vLLM keeps the
reports it is working on. On one 80 GB GPU, too little is left for a
32,768-token request, so vLLM stops at startup.

vLLM's [Gemma 4 guide](https://recipes.vllm.ai/Google/gemma-4-31B-it) adds
`--reasoning-parser gemma4` to some of its commands. Leave it out. A reasoning
parser separates the model's reasoning from its answer, and Gentrex turns
thinking off, which leaves nothing to separate. When thinking is off, the
parser can also stop vLLM from enforcing the schema
([vLLM issue 39130](https://github.com/vllm-project/vllm/issues/39130)).

If the download stops with an error that access to the model is restricted,
accept Google's terms on the
[model's page](https://huggingface.co/google/gemma-4-31B-it), log in
([Select the pages to keep](select.md#step-1-start-the-model-server)) and
start vLLM again.

vLLM is ready when `curl http://localhost:8000/v1/models` lists
`google/gemma-4-31B-it`.

## Step 2: Point Gentrex at the model server

`gentrex extract` uses the same two values in `.env` as `gentrex select`,
`GENTREX_LLM_BASE_URL` and `GENTREX_LLM_API_KEY`. If you haven't set them yet,
follow step 2 of
[Select the pages to keep](select.md#step-2-point-gentrex-at-the-model-server).

## Step 3: Run

```bash
uv run --env-file .env gentrex extract
```

The command reads the newest finished run of `gentrex select`,
`results/select/latest`, and writes a new folder like
`results/extract/20261014-150000/`. To read another run of `gentrex select`:

```bash
uv run --env-file .env gentrex extract --input results/select/20261014-131500
```

To extract again only the reports that failed in an earlier run, name that run
with `--retry` ([Redo failed files](runs-and-results.md#redo-failed-files)):

```bash
uv run --env-file .env gentrex extract --retry results/extract/latest
```

Gentrex prints one line per report as it goes. The last line counts the
reports and the failed reports, and shows the speed in reports per minute.

## Check the result

The run folder has three files:

| File | Contents |
| --- | --- |
| `extractions.jsonl` | One record per report. |
| `run.yaml` | The command, the run of `gentrex select` that was read, and the settings, including the instruction and the schema. |
| `log.txt` | What Gentrex printed during the run. |

Each line of `extractions.jsonl` is one report's JSON object, in input order,
shown here with most of `data` left out:

```json
{"file": "report-01.pdf", "pages": [1, 2], "data": {"mrn": "SYN-MRN-0001", "test_name": "Developmental Disorders Panel", "variants": [{"page": 1, "gene_symbol": "SCN2A", "hgvs_c": "c.2815G>A", "classification_raw": "VUS", "classification": "uncertain_significance"}]}, "error": null}
{"file": "report-02.pdf", "pages": [1, 3], "data": {"mrn": null, "test_name": "Inherited Arrhythmia Panel", "variants": []}, "error": "page 2: transcribe: APITimeoutError: Request timed out."}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `pages` | The pages sent to the model. |
| `data` | The record, with one entry per field of the schema. `null` if the report got no answer. |
| `error` | The pages left out because of an error from `gentrex transcribe`, and why the request failed. `null` when nothing went wrong. |

`data` and `error` together tell you how complete a record is:

| `data` | `error` | Meaning |
| --- | --- | --- |
| set | `null` | Complete. The model read every kept page. |
| set | set | Pages are missing. What is stated only on them is not in the record. |
| `null` | set | Nothing was extracted. |

A report whose kept pages all have errors from `gentrex transcribe` gets no
request, and its `data` is `null`. A report with no kept page gets no record at
all, because `gentrex select` passes on only the pages it keeps.

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

To read the records in Python with pandas, with one row per variant:

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

The model can fill in a value that the report doesn't state, from its own
knowledge of a gene or variant or by copying the example in a field's
description. Before you rely on the records, compare some of them with their
PDFs field by field, including the fields that came back `null`.

## How it works

Gentrex sends all kept pages of a report in one request, in page order. Each
page starts with a line like `--- PAGE 2 ---`, so the model can tell which page
a variant is on.

The fields of the record are defined in the extraction schema,
[`schema.yaml`](../../src/gentrex/defaults/schema.yaml). Gentrex sends it as
JSON after the instruction (`extract.instruction` in settings.yaml), and the
model reads it to learn what each field means. vLLM also enforces it as the
answer format, which is called structured output. The model can then write
only JSON that follows the schema and has every field. A field the report
doesn't state comes back `null`, and a report without variants gets an empty
`variants` list.

`classification`, `zygosity`, `parental_origin` and `mode_of_inheritance` each
take one value from a fixed list. Each comes right after a `_raw` field with
the report's own wording. The model writes the fields in schema order, so it
first copies the wording and then picks the closest allowed value. A report
that says "Pathogenic (Class 5)" gets
`"classification_raw": "Pathogenic (Class 5)"` and then
`"classification": "pathogenic"`. `test_type`, like `exome`, follows
`test_name` in the same way.

Gemma 4 has a thinking mode, in which it writes out its reasoning before the
answer. Gentrex turns it off, so the answer is the record and nothing else.

## Settings

The fields to extract are in
[`src/gentrex/defaults/schema.yaml`](../../src/gentrex/defaults/schema.yaml).
The instruction, the model and the other settings are under `extract` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml).
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
  quotes. Without them, YAML reads `null` as "no value" instead of the JSON
  Schema type "null". Without the type, the model must make up a value when
  the report states none.
- Write the description for the model, which reads it. Say what the field
  contains and when to fill it. An example value shows the format, but the
  model may copy it into a record whose report doesn't state the field.
- For a field with a fixed list of values, add an `enum` that ends with `null`
  without quotes, so the allowed value is null itself and not the text "null".
  Put a `_raw` field for the report's own wording right before it, like
  `classification_raw` before `classification`.

To see what changed between two runs, including the instruction and the schema:

```bash
diff results/extract/20261014-150000/run.yaml results/extract/20261015-090000/run.yaml
```

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report has a complete record. | Nothing. |
| 1 | No finished run of `gentrex select` was found (`pages.jsonl not found; run gentrex select first`), [`--retry`](runs-and-results.md#redo-failed-files) refused the earlier run, some reports have an error, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 2. |

A report is listed as failed in two cases:

- **One of its pages has an error from `gentrex transcribe`.** The record is
  written from the other pages, and `error` starts with `page N: transcribe:`.
  Run `gentrex transcribe`, `gentrex select` and `gentrex extract` again, each
  with `--retry`. Only this report then goes to the models again
  ([Redo failed files](runs-and-results.md#redo-failed-files)).
- **The request failed.** `data` is `null`, and `error` says why. A connection
  error means the server was down or busy, even after Gentrex's
  [retries](runs-and-results.md#failed-requests). Check that the server is
  running, then run `gentrex extract --retry results/extract/latest`.

Three errors come from the report rather than the server:

- `ValueError: answer cut off at max_tokens (4096)` means the record was longer
  than `extract.max_tokens` allows. Raise `max_tokens` in settings.yaml, and
  raise `timeout_seconds` by the same factor, because a longer answer takes
  longer to write. Then run again with `--retry`. If the report lists few
  variants, the model was more likely stuck repeating itself, for example
  writing spaces without end. In that case, also start vLLM with
  `--structured-outputs-config '{"disable_any_whitespace": true}'`, which
  leaves no room for spaces between the parts of the JSON.
- `APITimeoutError: Request timed out.` means the answer took longer than
  `extract.timeout_seconds` to write, on all four tries. Raise
  `timeout_seconds` in settings.yaml and run again with `--retry`.
- `BadRequestError: Error code: 400`, with a message about the maximum context
  length, means the report is longer than `--max-model-len` allows. Start vLLM
  with a higher `--max-model-len` and run again with `--retry`. vLLM refuses
  to start if the GPUs lack the memory for it.

If every report fails with the same error, the cause is the server. Check that
it runs `google/gemma-4-31B-it` with the model's own chat template, and that it
supports structured output with a JSON schema (`response_format`), as vLLM
does.

A traceback means the run stopped early.
[Runs and results](runs-and-results.md#failed-requests) lists the common causes.
