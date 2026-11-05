# Select the pages to keep

`gentrex select` decides which pages `gentrex extract` reads. Many pages of a
report only describe the test, and dropping them leaves `gentrex extract` less
to read. The command scores every page from `gentrex transcribe` and writes the
scores, with a copy of the kept pages, to `results/select/`.

The scores come from yes/no questions that a language model, Gemma 4 26B-A4B,
answers about each page. By default there are two:

- `has_result` asks whether the page states the patient's test result or lists
  the variants found in the patient.
- `has_phenotype` asks whether the page describes the patient's own symptoms,
  clinical features or reason for testing.

A page is kept when, for at least one question, the model answers yes with a
probability of 0.5 or more. [How it works](#how-it-works) explains where the
probability comes from.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex transcribe`, in `results/transcribe/`.
- An NVIDIA GPU with 80 GB of memory, and [vLLM](https://docs.vllm.ai) 0.25 or
  newer.
- A [Hugging Face](https://huggingface.co) account, if the model download asks
  you to log in.

On Mount Sinai's Minerva cluster, follow
[Select the pages to keep on Minerva](../minerva/minerva.md#select-the-pages-to-keep)
instead of the steps below. Then come back to
[Check the result](#check-the-result).

## Step 1: Start the model server

If the OCR server from `gentrex transcribe` is still running, stop it with
Ctrl-C in its terminal. Every model server uses port 8000, and this model
needs the GPU's memory.

If vLLM isn't installed yet, its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
shows how. Gentrex sends the text of every page to the server, so use a machine
approved for patient data. Start vLLM in a second terminal and leave it running
while Gentrex works:

```bash
vllm serve google/gemma-4-26B-A4B-it --max-model-len 16384
```

The first start downloads the model's weights, about 50 GB, into
`~/.cache/huggingface/`. The weights also take 50 GB of GPU memory, so the
model needs a GPU with 80 GB. Gentrex asks for the model by its Hugging Face
name (`select.model` in settings.yaml).

`--max-model-len 16384` sets the context length, the most tokens one request
can hold. Tokens are words or pieces of words. One page and one question come
to a few thousand tokens, even for a dense page.

vLLM's [Gemma 4 guide](https://recipes.vllm.ai/Google/gemma-4-26B-A4B-it) adds
`--reasoning-parser gemma4` to some of its commands. Leave it out. A reasoning
parser separates the model's reasoning from its answer, and Gentrex turns
thinking off, which leaves nothing to separate.

If the download stops with an error that access to the model is restricted,
accept Google's terms on the
[model's page](https://huggingface.co/google/gemma-4-26B-A4B-it). Then log in
with `uvx --from huggingface_hub hf auth login` and start vLLM again.

vLLM is ready when `curl http://localhost:8000/v1/models` lists
`google/gemma-4-26B-A4B-it`. `gentrex select` relies on three vLLM defaults.
If you add options of your own, keep prefix caching on, `--logprobs-mode` at
`raw_logprobs` and `--max-logprobs` at 20 or more.
[How it works](#how-it-works) explains why.

## Step 2: Point Gentrex at the model server

`gentrex select` and `gentrex extract` read the text model's address and API
key from `.env`. If you don't have a `.env` file yet, create it from the
example file:

```bash
cp .env.example .env
```

The example values fit vLLM on your own machine. Change them only for a server
elsewhere:

| Variable | What to put there |
| --- | --- |
| `GENTREX_LLM_BASE_URL` | The server's address, ending in `/v1`. It is `http://localhost:8000/v1` for vLLM on your own machine. |
| `GENTREX_LLM_API_KEY` | The key for that server. Leave `EMPTY` if the server needs none. vLLM needs one only if you start it with `--api-key`. |

## Step 3: Run

```bash
uv run --env-file .env gentrex select
```

The command reads the newest finished run of `gentrex transcribe`,
`results/transcribe/latest`, and writes a new folder like
`results/select/20261014-131500/`. To read another run of `gentrex transcribe`:

```bash
uv run --env-file .env gentrex select --input results/transcribe/20261014-123000
```

To ask again only about the pages that failed in an earlier run, name that run
with `--retry` ([Redo failed files](runs-and-results.md#redo-failed-files)):

```bash
uv run --env-file .env gentrex select --retry results/select/latest
```

Gentrex prints one line per PDF as it goes. The last line counts the pages and
the kept pages, and shows the speed in pages per minute.

## Check the result

The run folder has four files:

| File | Contents |
| --- | --- |
| `decisions.jsonl` | The scores and the keep flag of every page. |
| `pages.jsonl` | The kept pages, unchanged from `gentrex transcribe`. `gentrex extract` reads this file. |
| `run.yaml` | The command, the run of `gentrex transcribe` that was read, and the settings. |
| `log.txt` | What Gentrex printed during the run. |

`decisions.jsonl` has one line per page, in input order, each a JSON object:

```json
{"file": "report-01.pdf", "page": 1, "p_yes": {"has_result": 0.98, "has_phenotype": 0.93}, "keep": true, "error": null}
{"file": "report-01.pdf", "page": 5, "p_yes": {"has_result": 0.02, "has_phenotype": 0.01}, "keep": false, "error": null}
```

| Field | Meaning |
| --- | --- |
| `file` | Name of the PDF. |
| `page` | Page number, starting at 1. |
| `p_yes` | For each question, the probability that the answer is yes. `null` if the question was not asked or failed. |
| `keep` | `true` if `gentrex extract` reads the page. |
| `error` | Why questions failed on this page, or the page's error from `gentrex transcribe`. `null` when nothing went wrong. |

To count the kept pages:

```bash
grep -c '"keep": true' results/select/latest/decisions.jsonl
```

To list the pages with an error:

```bash
grep -v '"error": null' results/select/latest/decisions.jsonl
```

To compare runs, for example after rewording a question, give grep all of
them. It prints one count per run:

```bash
grep -c '"keep": true' results/select/2*/decisions.jsonl
```

`2*` matches the run folders, whose names start with the year, and skips the
`latest` link, which would count the newest run twice.

The model is often more sure of its answer than it should be. Before you rely
on the decisions, open some dropped pages in their PDFs and check that none of
them reports a result.

## How it works

Each request has the instruction (`select.instruction` in settings.yaml), the
text of one page and one question, followed by "Answer with Yes or No." A
page's questions go one after another, and prefix caching lets vLLM read the
page once for all of them.

Gentrex asks vLLM for the 20 most likely first tokens of the answer and their
probabilities, and reads those instead of the token the model writes:

| First token | Probability |
| --- | --- |
| `Yes` | 0.951 |
| `No` | 0.041 |
| ` yes` | 0.002 |

vLLM returns these as logprobs, the logarithms of the probabilities.
`--max-logprobs` has to be 20 or more for vLLM to return all 20, and
`raw_logprobs` returns them as the model computed them, before settings such
as temperature change them.

Gentrex adds up the probabilities of the tokens that spell the same answer,
ignoring case and spaces. Here that gives 0.953 for yes and 0.041 for no.
`p_yes`, the probability that the answer is yes, is then
0.953 / (0.953 + 0.041) = 0.96. That is above the 0.5 of
`select.keep_threshold`, so the page is kept.

Gemma 4 has a thinking mode, in which it writes out its reasoning before the
answer. Gentrex turns it off in every request, so the first token is the
answer.

A page is also kept when Gentrex can't tell whether it matters:

- OCR failed on the page in `gentrex transcribe`, so there is no text to ask
  about. The page and its error go on to `gentrex extract`, and the report is
  listed as failed.
- A question got no usable answer. The request still failed after the
  retries, the server rejected the page (for example because it is longer
  than `--max-model-len` allows), or the model's first token was neither Yes
  nor No.

A page with no text and no error is empty, and Gentrex drops it without asking
the model. Scanned pages are empty when `gentrex transcribe` ran with
`--no-ocr`.

### Why Gentrex uses probabilities

- A probability is a score, so you can choose how sure the model must be.
  `keep_threshold` sets the cut-off, and `p_yes` in `decisions.jsonl` shows how
  close each page came to it.
- It is cheap. The one pass through the model that reads the page already
  gives the probabilities of the first token, and each further token would
  take another pass. A question costs little more than reading the page.

## Settings

The questions, the model, the threshold and the other settings are under
`select` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml).
A comment above each value explains it.

```yaml
  questions:
    has_result: >-
      Does this page state the patient's test result or list the variants
      found in the patient? Answer No if the page only explains the result,
      recommends next steps or describes the test.
```

You can reword, add or delete questions. A question's name labels its answer
in `p_yes`, and each question adds one request per page. Phrase each question
about "this page", so that Yes or No answers it. To leave a kind of page out,
say so in the question, as `has_result` does with
"Answer No if the page only ...".

Don't ask about something every page shows, like the patient's name or date
of birth. Page headers repeat them, so every page would be kept. If too many
pages are kept, look for the question with a high `p_yes` on them, and reword
or remove it.

Lower `keep_threshold` to keep more pages. Fewer result pages are missed, but
`gentrex extract` has more to read. Raise it to keep fewer pages.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was decided. | Nothing. |
| 1 | No finished run of `gentrex transcribe` was found (`pages.jsonl not found; run gentrex transcribe first`), [`--retry`](runs-and-results.md#redo-failed-files) refused the earlier run, some files had errors, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 2. |

A file is listed as failed in two cases:

- **A question failed on one of its pages.** The page is kept with its other
  answers, and `error` says which question failed. A connection error or a
  timeout means the server was down or busy, even after Gentrex's
  [retries](runs-and-results.md#failed-requests). Check that the server is
  running, then run `gentrex select --retry results/select/latest`.
- **One of its pages has an error from `gentrex transcribe`.** The page is
  kept, and its `error` starts with `transcribe:`. Run `gentrex transcribe`
  and then `gentrex select` again, each with `--retry`.

An error that reads `answer starts with '...'` means the model's first token
was neither Yes nor No. For example, `'<|channel>'` starts Gemma 4's
reasoning, and `'**'` starts bold text. If many pages have such errors, check
that the server runs `google/gemma-4-26B-A4B-it` with the model's own chat
template, and reword the questions that cause them. A chat template turns a
request into the text format the model was trained on, including the switch
that turns thinking off. vLLM uses the model's own template unless you start
it with `--chat-template`.

A traceback means the run stopped early.
[Runs and results](runs-and-results.md#failed-requests) lists the common causes.
`MissingLogprobsError: the server sent no logprobs` also stops the run. Use
vLLM, or another server that returns logprobs.
