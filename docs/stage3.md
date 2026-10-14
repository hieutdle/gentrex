# Stage 3: One record per report

Stage 3 sends the pages that stage 2 kept to a text model, one report per
request, and writes one structured record per report: the patient, the
specimen, the test, the result and every variant reported.

## How it works

Gentrex sends all kept pages of a report in one request, in page order. Each
page starts with a line such as `--- PAGE 2 ---`. The model answers with one
JSON object for the whole report.

The extraction schema lists the fields of that object. Every request
carries it twice:

- After the instruction, as JSON, so the model reads what each field means.
- As the format of the answer. The server lets the model write only JSON
  that follows the schema and has every field.

A field the report does not state comes back `null`, and a report without
variants gets an empty `variants` list. For `classification` and `zygosity`,
the model picks one of the allowed values, such as `likely_pathogenic`, and
copies the report's own wording into `classification_raw` or `zygosity_raw`.

Thinking is turned off, as in stage 2, so the answer starts with the record.

Not every report can be read in full:

- A page with a stage 1 error has no text. It is left out of the request,
  and the record's `error` names it.
- A report whose pages all have stage 1 errors gets no request and no data.
- Stage 2 passes on only the pages it keeps, so a report with no kept page
  gets no record.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 2 run, in `results/pagedecide/`.
- A server that hosts the text model and speaks the OpenAI API, such as
  [vLLM](https://docs.vllm.ai) 0.25 or newer.

On Mount Sinai's Minerva cluster, follow
[Running on Minerva](minerva.md#stage-3-one-record-per-report) instead of
steps 1 and 2, then come back to [Check the result](#check-the-result).

## Step 1: Point Gentrex at the model server

Stage 3 reads the same two values in `.env` as stage 2,
`GENTREX_LLM_BASE_URL` and `GENTREX_LLM_API_KEY`. If they are not set yet,
do [stage 2, step 1](stage2.md#step-1-point-gentrex-at-the-model-server).
Every report's text is sent to this server, so use one approved for patient
data.

The server must serve the model under the name in the settings, which is
`google/gemma-4-31B-it` by default. Its weights take about 62 GB, so it
needs a GPU with 80 GB. With vLLM:

```bash
vllm serve google/gemma-4-31B-it \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.95
```

- `--max-model-len` is the longest request in tokens: the instruction, the
  schema, the report's pages and the answer together. A longer report
  fails; see [When something goes wrong](#when-something-goes-wrong).
- `--gpu-memory-utilization 0.95` lets vLLM use 95% of the GPU's memory.
  What the weights leave holds the reports vLLM is working on.

Start vLLM without `--reasoning-parser`: thinking is off, so there is no
reasoning to parse.

## Step 2: Run

```bash
uv run --env-file .env gentrex stage3
```

This reads the newest finished stage 2 run, `results/pagedecide/latest`, and
writes a new folder named after the time the run started, such as
`results/extract/20261014-150000/`. To read another stage 2 run:

```bash
uv run --env-file .env gentrex stage3 --input results/pagedecide/20261014-131500
```

While it runs, Gentrex prints one line per report. The last line counts the
reports written and failed, and gives the speed in reports per minute.
Running it again writes a new folder; earlier runs stay.

## Check the result

Each run folder holds three files:

| File | Contents |
| --- | --- |
| `extractions.jsonl` | One record per report. |
| `run.yaml` | The command, the stage 2 run that was read, and the settings, including the instruction and the schema. |
| `log.txt` | What Gentrex printed during the run. |

`results/extract/latest` points to the newest run that finished.

`extractions.jsonl` has one line per report, in the order of the input. Each
line is a JSON object, shown here with most of `data` left out:

```json
{"file": "report-01.pdf", "pages": [1, 2], "data": {"mrn": "SYN-MRN-0001", "test_name": "Developmental Disorders Panel", "variants": [{"gene_symbol": "SCN2A", "hgvs_c": "c.2815G>A", "classification": "uncertain_significance", "classification_raw": "VUS"}]}, "error": null}
{"file": "report-02.pdf", "pages": [1, 3], "data": {"mrn": null, "test_name": "Inherited Arrhythmia Panel", "variants": []}, "error": "page 2: stage 1: APITimeoutError: Request timed out."}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `pages` | The pages sent to the model. |
| `data` | The record, with one entry per field of the schema. `null` if the report got no answer. |
| `error` | The pages left out because of a stage 1 error, and why the request failed; `null` when nothing went wrong. |

`data` and `error` together tell you how complete a record is:

| `data` | `error` | Meaning |
| --- | --- | --- |
| set | `null` | Complete: the model read every kept page. |
| set | set | Pages are missing: what is stated only on them is not in the record. |
| `null` | set | Nothing was extracted. |

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

The model can fill a field from its own knowledge or from an example in the
schema, where the report does not state it. Before you rely on the records,
compare some of them with their PDFs, field by field, including the fields
that came back `null`.

## Settings

The fields to extract are in
[`src/gentrex/defaults/schema.yaml`](../src/gentrex/defaults/schema.yaml).
The instruction, the model and the other stage 3 settings are in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml),
under `extract`. Each value is explained there.

The schema is a [JSON Schema](https://json-schema.org/). The report-level
fields are under `properties`, and the fields of each variant under
`variants.items.properties`. Each field is one block:

```yaml
  test_name:
    description: >-
      Name of the test, panel or assay (e.g. Inherited Arrhythmia Panel,
      Proband Exome with Secondary Findings).
    type: [string, "null"]
```

- To add a field, add a block. To remove one, delete its block.
- Keep `"null"` in every `type`. Without it, the model must make up a value
  for a field the report does not state.
- Write the description for the model, which reads it: say what the field
  holds and when to fill it. An example value shows the format, but the
  model may copy it into a record whose report does not state the field.
- For a field with a fixed list of values, add an `enum` that ends with
  `null`, and a `_raw` field for the report's own wording, as
  `classification` and `classification_raw` do.

`run.yaml` records the instruction and the schema of every run. To see what
changed between two runs:

```bash
diff results/extract/20261014-150000/run.yaml results/extract/20261015-090000/run.yaml
```

## When something goes wrong

Gentrex ends with an exit code that tells you what happened:

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report has a complete record. | Nothing. |
| 1 | No finished stage 2 run was found, or some reports have an error. The failed files are listed at the end of the output. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 1. |

A report is listed as failed in two cases:

- **One of its pages has a stage 1 error.** The record is written from the
  other pages, and `error` starts with `page N: stage 1:`. Run stage 1
  again, then stages 2 and 3.
- **The request failed.** `data` is `null`, and `error` says why. Gentrex
  already retried a server that was busy or unreachable three times (after
  5, 20 and 60 seconds) before giving up. Check that the server is running,
  then run the command again.

Three errors come from the report rather than the server:

- `ValueError: answer cut off at max_tokens (4096)`: the record did not fit
  in `max_tokens`. Raise `max_tokens` in the settings, raise
  `timeout_seconds` by the same factor, and run again. If the report lists
  few variants, the model was more likely stuck repeating itself, for
  example writing spaces without end. Then also start vLLM with
  `--structured-outputs-config '{"disable_any_whitespace": true}'`, which
  leaves no room for spaces between the parts of the JSON.
- `APITimeoutError: Request timed out.`: the answer took longer than
  `timeout_seconds` to write, on all four attempts. Raise `timeout_seconds`
  in the settings and run again.
- `BadRequestError: Error code: 400`, with a message about the maximum
  context length: the report is longer than `--max-model-len` allows. Start
  vLLM with a higher `--max-model-len`, if the GPU has the memory, and run
  again.

If every report fails with the same error, the server is the problem, not
the reports. Check that it runs the model named in the settings, with that
model's own chat template, and that it supports `response_format` with a
JSON schema, as vLLM does.

A wrong key or an unknown model name stops the run at once, because every
report would fail the same way. Fix `.env` or the model name and run again.
A run that stops early keeps its folder, but `latest` does not move to it.
