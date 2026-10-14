# Stage 1: PDF pages to text

Stage 1 reads a folder of PDF reports and writes the text of every page to one
file. Later stages work from that file, not from the PDFs.

## How it works

Each page is handled on its own, because one report can mix both kinds:

- **Native page**: the PDF already contains the text. It is read directly,
  which is fast and exact.
- **Scanned page**: the page is only a picture (a scan or a fax). It is sent
  to a vision model that reads the picture and returns the text. This is OCR.

A page counts as scanned when the PDF holds fewer than 20 non-whitespace
characters of text for it.

## Before you start

You need:

- [uv](https://docs.astral.sh/uv/), which manages Python and the dependencies.
- Your PDF reports in one folder.
- For scanned pages: a server that hosts the OCR model and speaks the OpenAI
  API, such as [vLLM](https://docs.vllm.ai).

If all your reports are native PDFs, you do not need a model server. Skip
step 2 and use `--no-ocr` in step 4.

On Mount Sinai's Minerva cluster, follow [Running on Minerva](minerva.md)
instead of steps 1 to 4, then come back to [Check the result](#check-the-result).

## Step 1: Install

Run this once, from the repository folder:

```bash
uv sync
```

It creates `.venv/` and installs everything Gentrex needs.

## Step 2: Point Gentrex at the OCR server

Copy the example file:

```bash
cp .env.example .env
```

Then open `.env` and set the two values:

| Variable | What to put there |
| --- | --- |
| `GENTREX_OCR_BASE_URL` | Address of the server, ending in `/v1`. For vLLM on your own machine: `http://localhost:8000/v1`. |
| `GENTREX_OCR_API_KEY` | The key for that server. Leave `EMPTY` if it needs none. |

The server must serve the OCR model under the name in the settings, which is
`lightonai/LightOnOCR-3-4B` by default. With vLLM:

```bash
vllm serve lightonai/LightOnOCR-3-4B \
  --max-model-len 18000 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

`.env` is gitignored, so the address and key stay out of git.

## Step 3: Put your PDFs in place

Copy the reports into `data/raw/`:

```bash
mkdir -p data/raw
cp /path/to/your/reports/*.pdf data/raw/
```

Only PDFs directly inside the folder are read; subfolders are ignored. The
file name identifies the report in every later stage, so keep names unique.

## Step 4: Run

```bash
uv run --env-file .env gentrex stage1
```

This reads `data/raw/` and writes a new folder named after the time the run
started, such as `results/transcribe/20261014-123000/`. To read PDFs from
another folder:

```bash
uv run --env-file .env gentrex stage1 --input-dir my/reports
```

To skip OCR:

```bash
uv run gentrex stage1 --no-ocr
```

Scanned pages are then written with empty text.

While it runs, Gentrex prints one line per PDF. The last line gives the
speed:

```text
wrote 1450 pages (1210 scanned) in 785 s: 110.8 pages per minute
```

The time runs from reading the first PDF to writing the last page. Running it
again starts from the beginning in a new folder; earlier runs stay.

## Check the result

Each run folder holds three files:

| File | Contents |
| --- | --- |
| `pages.jsonl` | The text of every page. |
| `run.yaml` | The command, the input folder and the settings the run used. |
| `log.txt` | What Gentrex printed during the run. |

`results/transcribe/latest` points to the newest run that finished. Stage 2
reads that run unless you name another.

`pages.jsonl` has one line per page. Each line is a JSON object:

```json
{"file": "report-01.pdf", "page": 1, "source": "native", "text": "Hereditary Cancer Panel ...", "error": null}
{"file": "report-01.pdf", "page": 2, "source": "scanned", "text": "RESULT: NEGATIVE ...", "error": null}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `page` | Page number, starting at 1. |
| `source` | `native` if the text came from the PDF, `scanned` if the page went to OCR. |
| `text` | The text of the page. Empty for a scanned page when OCR was off or failed. |
| `error` | Why OCR failed on this page; `null` when nothing went wrong. |

To see how many pages of each kind you got:

```bash
grep -c '"source": "native"' results/transcribe/latest/pages.jsonl
grep -c '"source": "scanned"' results/transcribe/latest/pages.jsonl
```

To list pages where OCR failed:

```bash
grep -v '"error": null' results/transcribe/latest/pages.jsonl
```

To compare runs, give grep all of them: it prints one count per run.

```bash
grep -c '"source": "scanned"' results/transcribe/*/pages.jsonl
```

To see what changed between two runs, compare their `run.yaml`:

```bash
diff results/transcribe/20261014-123000/run.yaml results/transcribe/20261015-090000/run.yaml
```

## When something goes wrong

Gentrex ends with an exit code that tells you what happened:

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was transcribed. | Nothing. |
| 1 | No PDFs were found, or some files failed. The failed files are listed at the end of the output. | See below. |
| 2 | `GENTREX_OCR_BASE_URL` is not set. | Do step 2, or add `--no-ocr`. |

A file is listed as failed in two cases:

- **OCR failed on one of its pages.** The other pages are still written, and
  the failed page has an `error`. Gentrex already retried a server that was
  busy or unreachable three times (after 5, 20 and 60 seconds) before giving
  up. Check that the server is running, then run the command again.
- **The PDF could not be opened.** Nothing is written for it. The error is in
  the output; the file is usually damaged or not a real PDF.

A wrong key or an unknown model name stops the run at once, because every
page would fail the same way. Fix `.env` or the model name and run again. A
run that stops early keeps its folder, but `latest` does not move to it.

## Settings

The model, the prompt and the image settings are in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml).
Each value is explained there. Edit that file to change one.

## Patient data

`data/` and `results/` are gitignored. Reports, and anything produced from
them, may contain patient data and must never be committed.
