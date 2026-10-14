# Stage 2: Which pages to keep

Stage 2 asks a text model yes/no questions about every page that stage 1
wrote, and marks each page keep or drop. Later stages read only the kept
pages.

## How it works

Gentrex sends the model one page and one question at a time, and lets it
answer with a single word. It does not use the word itself: it reads how
likely the model found "Yes" and how likely "No", and turns the two into
`p_yes`, the probability that the answer is yes, between 0 and 1.

A page is kept when at least one question has a `p_yes` of 0.5 or more. Two
kinds of page skip the model:

- A page with no text is dropped.
- A page that stage 1 could not transcribe is kept, so it is not lost
  unseen.

A question that fails also keeps its page, for the same reason.

By default, Gentrex asks whether a page reports the patient's test result
(`has_result`) and whether it describes the patient's symptoms or reason for
testing (`has_phenotype`).

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 1 run, in `results/transcribe/`.
- A server that hosts the text model and speaks the OpenAI API, such as
  [vLLM](https://docs.vllm.ai) 0.25 or newer.

On Mount Sinai's Minerva cluster, follow
[Running on Minerva](minerva.md#stage-2-which-pages-to-keep) instead of steps
1 and 2, then come back to [Check the result](#check-the-result).

## Step 1: Point Gentrex at the model server

If you have no `.env` file yet, copy the example file:

```bash
cp .env.example .env
```

Then open `.env` and set the two values:

| Variable | What to put there |
| --- | --- |
| `GENTREX_LLM_BASE_URL` | Address of the server, ending in `/v1`. For vLLM on your own machine: `http://localhost:8000/v1`. |
| `GENTREX_LLM_API_KEY` | The key for that server. Leave `EMPTY` if it needs none. |

Every page's text is sent to this server, so use one approved for patient
data.

The server must serve the model under the name in the settings, which is
`google/gemma-4-26B-A4B-it` by default. Its weights take about 50 GB, so it
needs a GPU with 80 GB. With vLLM:

```bash
vllm serve google/gemma-4-26B-A4B-it --max-model-len 16384
```

Do not turn off prefix caching: Gentrex asks a page's questions one after
another, and the cache lets the server read the page once for all of them. Do
not change `--logprobs-mode` or lower `--max-logprobs` below 20: Gentrex reads
the model's raw probabilities for the 20 likeliest first words. No reasoning
parser is needed, because Gentrex turns thinking off in every request.

## Step 2: Run

```bash
uv run --env-file .env gentrex stage2
```

This reads the newest finished stage 1 run, `results/transcribe/latest`, and
writes a new folder named after the time the run started, such as
`results/pagedecide/20261014-131500/`. To read another stage 1 run:

```bash
uv run --env-file .env gentrex stage2 --input results/transcribe/20261014-123000
```

While it runs, Gentrex prints one line per PDF. The last line counts the
pages written and kept, and gives the speed in pages per minute. Running it
again writes a new folder; earlier runs stay.

## Check the result

Each run folder holds four files:

| File | Contents |
| --- | --- |
| `decisions.jsonl` | The scores and the keep flag of every page. |
| `pages.jsonl` | The kept pages, unchanged from stage 1. Later stages read this file. |
| `run.yaml` | The command, the stage 1 run that was read, and the settings. |
| `log.txt` | What Gentrex printed during the run. |

`results/pagedecide/latest` points to the newest run that finished.

`decisions.jsonl` has one line per page, in the order of the input. Each line
is a JSON object:

```json
{"file": "report-01.pdf", "page": 1, "p_yes": {"has_result": 0.98, "has_phenotype": 0.93}, "keep": true, "error": null}
{"file": "report-01.pdf", "page": 5, "p_yes": {"has_result": 0.02, "has_phenotype": 0.01}, "keep": false, "error": null}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `page` | Page number, starting at 1. |
| `p_yes` | For each question, the probability that the answer is yes. `null` if the question was not asked or failed. |
| `keep` | `true` if later stages read the page. |
| `error` | Why questions failed on this page, or the page's stage 1 error; `null` when nothing went wrong. |

To count the kept pages:

```bash
grep -c '"keep": true' results/pagedecide/latest/decisions.jsonl
```

To list pages with an error:

```bash
grep -v '"error": null' results/pagedecide/latest/decisions.jsonl
```

To compare runs, for example after rewording a question, give grep all of
them: it prints one count per run.

```bash
grep -c '"keep": true' results/pagedecide/*/decisions.jsonl
```

Before you rely on the decisions, open some dropped pages in their PDFs and
check that none of them reports a result.

## Settings

The questions are in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml),
under `pagedecide`, with the model, the threshold and the other stage 2
settings. Each value is explained there.

```yaml
  questions:
    has_result: >-
      Does this page report the patient's genetic test result, such as an
      overall result or a variant found in the patient?
```

- To reword a question, edit its text.
- To add a question, add a name and its text. The name labels the answer in
  `p_yes`.
- To remove a question, delete it.

Phrase each question about "this page", so that Yes or No answers it. Gentrex
adds "Answer with Yes or No." after each question. Each question adds one
request per page.

Do not ask about what every page shows, such as the patient's name or date of
birth: page headers repeat them, so the answer is yes on every page and every
page is kept. If too many pages are kept, check which question is high on
them and reword or remove it.

`keep_threshold` is 0.5 by default. Lower it to keep more pages: fewer result
pages are missed, but later stages have more to read. Raise it to keep fewer.

## When something goes wrong

Gentrex ends with an exit code that tells you what happened:

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was decided. | Nothing. |
| 1 | No finished stage 1 run was found, or some files had errors. The failed files are listed at the end of the output. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 1. |

A file is listed as failed in two cases:

- **A question failed on one of its pages.** The page is kept with its other
  answers, and `error` names the question. Gentrex already retried a server
  that was busy or unreachable three times (after 5, 20 and 60 seconds)
  before giving up. Check that the server is running, then run the command
  again.
- **One of its pages has a stage 1 error.** The page is kept, and its `error`
  starts with `stage 1:`. Run stage 1 again, then stage 2.

An error that reads `answer starts with '...'` means the model's first word
was neither Yes nor No, for example `'<|channel>'` when the model starts to
think, or `'**'` when it starts with bold text. If many pages have them,
check that the server runs the model named in the settings with that model's
own chat template, and reword the questions that cause them.

A wrong key, an unknown model name, or a server that sends no logprobs stops
the run at once, because every page would fail the same way. Fix `.env`, the
model name or the server, and run again. A run that stops early keeps its
folder, but `latest` does not move to it.
