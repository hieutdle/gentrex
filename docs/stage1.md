# Stage 1: Transcribe PDF pages

Stage 1 reads a folder of PDF reports and writes the text of every page to one
file, `pages.jsonl`. Stages 2 and 3 read that file instead of the PDFs.

Gentrex handles each page on its own, because one report can mix two kinds of
page:

- A **native** page has its text stored in the PDF. Gentrex reads that
  text directly, which is fast and exact.
- A **scanned** page is only a picture, such as a scan or a fax. Gentrex sends
  the picture to an OCR (optical character recognition) model, which reads the
  text off the image. The model runs in a
  [model server](../README.md#terms) on a GPU.

A page counts as scanned when the PDF holds fewer than 20 characters of text
for it, not counting spaces and line breaks.

If none of your reports has a scanned page, you need no GPU and no model server
for this stage. To find out, do steps 1 and 2, then run stage 1 with
`--no-ocr` as in [step 5](#step-5-run). The last line of its output counts the
scanned pages.

## Before you start

You need:

- [uv](https://docs.astral.sh/uv/), which installs Python and the packages
  Gentrex needs.
- Your PDF reports in one folder.
- For scanned pages, an NVIDIA GPU and [vLLM](https://docs.vllm.ai). The OCR
  model's [weights](../README.md#terms), the numbers it learned in training,
  take about 9 GB of GPU memory.

On Mount Sinai's Minerva cluster, follow [Running on Minerva](minerva.md)
instead of the steps below. Then come back to
[Check the result](#check-the-result).

## Step 1: Install

Run this once, from the repository folder:

```bash
uv sync
```

It creates `.venv/` and installs everything Gentrex needs.

## Step 2: Put your PDFs in place

Copy the reports into `data/raw/`:

```bash
mkdir -p data/raw
cp /path/to/your/reports/*.pdf data/raw/
```

Gentrex reads only the PDFs directly inside the folder, not those in
subfolders. The file name identifies the report in every later stage, so keep
names unique.

The reports contain patient data, so keep the repository folder on storage
approved for it. See [Patient data](../README.md#patient-data).

## Step 3: Start the OCR server

Skip this step and step 4 if your reports have no scanned pages.

[vLLM](https://docs.vllm.ai) is a model server. It loads a model onto the GPU
and answers requests from Gentrex over HTTP. Install it on the GPU machine as
its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
describes.

Start vLLM in a second terminal, and leave it running while Gentrex works:

```bash
vllm serve lightonai/LightOnOCR-3-4B \
  --max-model-len 18000 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

- `lightonai/LightOnOCR-3-4B` is the model's name on Hugging Face, and the
  name Gentrex asks for (`transcribe.ocr.model` in settings.yaml). The first
  start downloads the model's weights, about 9 GB, into
  `~/.cache/huggingface/`. Later starts reuse them.
- `--max-model-len 18000` sets the [context length](../README.md#terms), the
  most tokens one request can hold. Tokens are words or pieces of words, the
  units a model reads and writes. A page image takes a few thousand tokens and
  the answer at most 8,192 (`transcribe.ocr.max_tokens` in settings.yaml), so
  18,000 holds both.
- `--default-chat-template-kwargs '{"enable_thinking": false}'` turns off the
  model's [thinking](../README.md#terms) mode, in which it would write out
  reasoning before the page text. LightOnOCR is trained with thinking off.

vLLM is ready when its terminal shows `Application startup complete`. To
check, run this in your first terminal:

```bash
curl http://localhost:8000/v1/models
```

The answer lists the model as `"id":"lightonai/LightOnOCR-3-4B"`. vLLM listens
on port 8000 unless you start it with `--port`. To stop vLLM, press Ctrl-C in
its terminal.

Gentrex sends every scanned page to this server as an image. Run the server on
a machine approved for patient data.

## Step 4: Point Gentrex at the OCR server

Gentrex reads the server's address and API key from a file named `.env`.
Create it from the example file:

```bash
cp .env.example .env
```

The example values fit vLLM on your own machine. Change them only for a server
elsewhere:

| Variable | What to put there |
| --- | --- |
| `GENTREX_OCR_BASE_URL` | The server's address, ending in `/v1`. It is `http://localhost:8000/v1` for vLLM on your own machine. |
| `GENTREX_OCR_API_KEY` | The key for that server. Leave `EMPTY` if the server needs none. vLLM needs one only if you start it with `--api-key`. |

Git ignores `.env`, so the address and key stay out of the repository.

## Step 5: Run

```bash
uv run --env-file .env gentrex stage1
```

`uv run` runs Gentrex in the environment that step 1 created, and
`--env-file .env` passes it the values from `.env`. Gentrex reads the PDFs in
`data/raw/` and writes a new folder named after the time the run started, such
as `results/transcribe/20261014-123000/`.

To read PDFs from another folder:

```bash
uv run --env-file .env gentrex stage1 --input-dir my/reports
```

To skip OCR, which leaves scanned pages empty:

```bash
uv run gentrex stage1 --no-ocr
```

While it runs, Gentrex prints one line per PDF. The last line counts the pages
and gives the speed:

```text
wrote 1450 pages (1210 scanned) in 785 s: 110.8 pages per minute
```

The time runs from reading the first PDF to writing the last page.

## Check the result

The run folder holds three files:

| File | Contents |
| --- | --- |
| `pages.jsonl` | The text of every page. |
| `run.yaml` | The command, the input folder and the settings the run used. |
| `log.txt` | What Gentrex printed during the run. |

Stage 2 reads the newest finished run, `results/transcribe/latest`, unless you
name another. [Runs and results](../README.md#runs-and-results) explains run
folders and `latest`.

`pages.jsonl` is a [JSONL](../README.md#terms) file, with one JSON object per
line and one line per page:

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
| `error` | Why OCR failed on this page, or `null` when nothing went wrong. |

To count the pages of each kind:

```bash
grep -c '"source": "native"' results/transcribe/latest/pages.jsonl
grep -c '"source": "scanned"' results/transcribe/latest/pages.jsonl
```

To list the pages where OCR failed:

```bash
grep -v '"error": null' results/transcribe/latest/pages.jsonl
```

To compare runs, give grep all of them. It prints one count per run:

```bash
grep -c '"source": "scanned"' results/transcribe/*/pages.jsonl
```

To see what changed between two runs, compare their `run.yaml`:

```bash
diff results/transcribe/20261014-123000/run.yaml results/transcribe/20261015-090000/run.yaml
```

## How it works

Gentrex reads the text stored in each page of a PDF, and sorts the pages into
native and scanned by the 20-character rule at the top of this page
(`transcribe.native_min_chars`).

The OCR model reads images, so Gentrex draws each scanned page as an image at
400 dots per inch (`transcribe.ocr.render_dpi`). It then shrinks the image so
its longer side is 2,048 pixels (`transcribe.ocr.longest_dim`), the size
LightOnOCR is trained on. Drawing the page large and then shrinking it keeps
small print smooth. Gentrex sends the image to the OCR server with no other
text, and writes the answer as the page's text.

Gentrex sends up to 8 pages to the server at the same time, across PDFs
(`transcribe.ocr.concurrency`), because vLLM processes requests together
faster than one by one. It still writes the pages of each PDF together and in
order.

## Settings

The model, the prompt and the image settings are under `transcribe` in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml).
A comment above each value explains it. Edit that file to change one.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was transcribed. | Nothing. |
| 1 | No PDFs were found (`no PDFs in data/raw`), some files failed, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_OCR_BASE_URL` is not set. | Do step 4, or add `--no-ocr`. |

A file is listed as failed in two cases:

- **OCR failed on one of its pages.** The other pages are still written, and
  the failed page has an `error`. If the error is a connection error or a
  timeout, the server was down or busy, even after Gentrex's
  [retries](../README.md#runs-and-results). Check that the server is running,
  then run stage 1 again.
- **The PDF could not be opened.** Nothing is written for it. The error is in
  the output. The file is usually damaged or not a real PDF.

A traceback means the run stopped early, most often because of a wrong API key
or model name. [Runs and results](../README.md#runs-and-results) explains the
causes.
