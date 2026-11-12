# Transcribe PDF pages

`gentrex transcribe` reads a folder of PDF reports and writes the text of every
page to one file, `pages.jsonl`. `gentrex select` then reads this file instead
of the PDFs.

Each page is read in one of two ways, and one report can mix both:

- A **native** page has its text stored in the PDF. Gentrex reads that text
  directly, which is fast and exact.
- A **scanned** page is only a picture, like a scan or a fax. Gentrex sends it
  to an OCR (optical character recognition) model, which reads the text off
  the image. The model runs in a model server, a program that loads it onto a
  GPU and answers Gentrex's requests.

A page counts as scanned when the PDF has fewer than 20 characters of text for
it, not counting spaces and line breaks. A page with more text can count as
scanned too, like a page image whose only text is a document code.
[How it works](#how-it-works) says when.

If none of your reports has a scanned page, you don't need a GPU or a model
server. To find out, do steps 1 and 2 and run the command with `--no-ocr`
([step 5](#step-5-run)). The last line of the output counts the scanned pages.

## Before you start

You need:

- [uv](https://docs.astral.sh/uv/), which installs Python and the packages
  Gentrex needs.
- Your PDF reports in one folder.
- For scanned pages, an NVIDIA GPU and [vLLM](https://docs.vllm.ai). The OCR
  model's weights, the numbers it learned in training, take about 9 GB of GPU
  memory.

On Mount Sinai's Minerva cluster, follow [Running on Minerva](../minerva/minerva.md)
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

PDFs in subfolders are left out. Every later command identifies a report by
its file name, so keep the names unique.

The reports contain patient data, so keep the repository folder on storage
approved for it ([Patient data](../../README.md#patient-data)).

## Step 3: Start the OCR server

Skip this step and step 4 if your reports have no scanned pages.

The model server is [vLLM](https://docs.vllm.ai). Its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
shows how to install it on the GPU machine. Gentrex sends every scanned page to
the server as an image, so use a machine approved for patient data.

Start vLLM in a second terminal and leave it running while Gentrex works:

```bash
vllm serve lightonai/LightOnOCR-3-4B \
  --max-model-len 18000 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

The first start downloads the model's weights, about 9 GB, into
`~/.cache/huggingface/`. `lightonai/LightOnOCR-3-4B` is its name on Hugging
Face and the name Gentrex asks for (`transcribe.ocr.model` in settings.yaml).

`--max-model-len 18000` sets the context length, the most tokens one request
can hold. Tokens are words or pieces of words. A page image takes a few
thousand tokens and the answer at most 8,192 (`transcribe.ocr.max_tokens` in
settings.yaml), so 18,000 holds both. `--default-chat-template-kwargs` turns
off the model's thinking mode, in which it would write out reasoning before the
page text. LightOnOCR is trained with thinking off.

vLLM is ready when its terminal shows `Application startup complete`. To
check, run this in your first terminal:

```bash
curl http://localhost:8000/v1/models
```

The answer lists the model as `"id":"lightonai/LightOnOCR-3-4B"`. vLLM listens
on port 8000 unless you start it with `--port`. To stop it, press Ctrl-C in its
terminal.

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
uv run --env-file .env gentrex transcribe
```

`uv run` runs Gentrex in the environment from step 1, and `--env-file .env`
passes it the values from `.env`. The command reads the PDFs in `data/raw/`
and writes a new folder named after its start time, like
`results/transcribe/20261014-123000/`. `results/transcribe/latest` points to
the newest finished run ([Runs and results](runs-and-results.md#run-folders)).

To read PDFs from another folder:

```bash
uv run --env-file .env gentrex transcribe --input-dir my/reports
```

To skip OCR, which leaves scanned pages empty:

```bash
uv run gentrex transcribe --no-ocr
```

To send only the pages that failed in an earlier run to OCR again, name that
run with `--retry` ([Redo failed files](runs-and-results.md#redo-failed-files)).
It can't be combined with `--no-ocr`.

```bash
uv run --env-file .env gentrex transcribe --retry results/transcribe/latest
```

Gentrex prints one line per PDF as it goes. The last line counts the pages and
shows the speed:

```text
wrote 1450 pages (1210 scanned) in 785 s: 110.8 pages per minute
```

## Check the result

The run folder has three files:

| File | Contents |
| --- | --- |
| `pages.jsonl` | The text of every page. |
| `run.yaml` | The command, the input folder and the settings the run used. |
| `log.txt` | What Gentrex printed during the run. |

`pages.jsonl` has one line per page, each a JSON object:

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
grep -c '"source": "scanned"' results/transcribe/2*/pages.jsonl
```

`2*` matches the run folders, whose names start with the year, and skips the
`latest` link, which would count the newest run twice.

To see what changed between two runs, compare their `run.yaml`:

```bash
diff results/transcribe/20261014-123000/run.yaml results/transcribe/20261015-090000/run.yaml
```

## How it works

Two more kinds of pages go to OCR, although they have 20 characters or more.
On a page image, the only text may be a document code or a caption. Such a
page goes to OCR when images cover at least half of it and it has fewer than
300 characters.

Some PDFs draw their text as outlines, which are shapes in the form of letters,
and store only a few fields as characters, like the patient's name and dates.
Outlined text makes about one curve per letter, so such a page has thousands of
curves. Other pages have far fewer. A page with at least 1,000 curves and fewer
than 600 characters goes to OCR.

Each scanned page is drawn as an image at 400 dots per inch
(`transcribe.ocr.render_dpi`) and then shrunk until its longer side is 2,048
pixels (`transcribe.ocr.longest_dim`), the size LightOnOCR is trained on.
Drawing the page large and shrinking it keeps small print smooth. The image
goes to the server with no other text, and the answer becomes the page's text.

Up to 8 pages go to the server at the same time, across PDFs
(`transcribe.ocr.concurrency`), because vLLM processes requests together
faster than one by one. The pages of each PDF are still written together and
in order.

## Settings

The model, the prompt, the image settings and the 20-character limit
(`transcribe.native_min_chars`) are under `transcribe` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml).
A comment above each value explains it. To change one, name it in a
[settings file of your own](runs-and-results.md#change-the-settings). The limits on images and curves that
send a page with more text to OCR are fixed in
[`src/gentrex/transcribe/native.py`](../../src/gentrex/transcribe/native.py).

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was transcribed. | Nothing. |
| 1 | No PDFs were found (`no PDFs in data/raw`), [`--retry`](runs-and-results.md#redo-failed-files) refused the earlier run, some files failed, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_OCR_BASE_URL` is not set. | Do step 4, or add `--no-ocr`. |

A file is listed as failed in two cases:

- **OCR failed on one of its pages.** The other pages are still written, and
  the failed page has an `error`. A connection error or a timeout means the
  server was down or busy, even after Gentrex's
  [retries](runs-and-results.md#failed-requests). Check that the server is
  running, then run `gentrex transcribe --retry results/transcribe/latest`.
- **The PDF could not be opened.** Nothing is written for it, and the error is
  in the output. The file is usually damaged or not a real PDF.

A traceback means the run stopped early, most often because of a wrong API key
or model name. [Runs and results](runs-and-results.md#failed-requests) lists the
causes.
