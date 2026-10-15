# Stage 2: Decide which pages to keep

Stage 2 decides which pages stage 3 reads. It asks a language model yes/no
questions about every page that stage 1 wrote, and keeps a page when the model
is likely to answer yes. Many pages of a report only describe the test, and
dropping them leaves stage 3 less to read.

Stage 2 reads `pages.jsonl` from a stage 1 run. It writes a score for every
page, and a copy of the kept pages, to `results/pagedecide/`. The model, Gemma
4 26B-A4B, runs on one GPU with 80 GB of memory.

By default, Gentrex asks two questions about every page:

- `has_result` asks whether the page states the patient's test result or lists
  the variants found in the patient.
- `has_phenotype` asks whether the page describes the patient's own symptoms,
  clinical features or reason for testing.

A page is kept when, for at least one question, the model answers yes with a
probability of 0.5 or more. [How it works](#how-it-works) explains where the
probability comes from.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 1 run, in `results/transcribe/`.
- An NVIDIA GPU with 80 GB of memory, and [vLLM](https://docs.vllm.ai) 0.25 or
  newer.
- A [Hugging Face](https://huggingface.co) account, if the model download asks
  you to log in.

On Mount Sinai's Minerva cluster, follow
[Stage 2 on Minerva](minerva.md#stage-2-decide-which-pages-to-keep) instead of
the steps below. Then come back to [Check the result](#check-the-result).

## Step 1: Start the model server

If the stage 1 server is still running, stop it with Ctrl-C in its terminal.
Every stage's server uses port 8000, and this model needs the GPU's memory.

If vLLM isn't installed yet, install it as its
[installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/)
describes. Then start it in a second terminal, and leave it running while
Gentrex works:

```bash
vllm serve google/gemma-4-26B-A4B-it --max-model-len 16384
```

- `google/gemma-4-26B-A4B-it` is the model's name on Hugging Face, and the
  name Gentrex asks for (`pagedecide.model` in settings.yaml). The first start
  downloads the model's [weights](../README.md#terms), about 50 GB, into
  `~/.cache/huggingface/`. The weights also take 50 GB of GPU memory, so the
  model needs a GPU with 80 GB.
- `--max-model-len 16384` sets the [context length](../README.md#terms), the
  most tokens one request can hold. Tokens are words or pieces of words. A
  request holds one page and one question, which is a few thousand tokens even
  for a dense page.

vLLM's [Gemma 4 guide](https://recipes.vllm.ai/Google/gemma-4-26B-A4B-it) adds
`--reasoning-parser gemma4` to some of its commands. Leave it out. A reasoning
parser separates the model's reasoning from its answer, and Gentrex turns
[thinking](../README.md#terms) off, so there is no reasoning to separate.

If the download stops with an error that access to the model is restricted,
open the [model's page](https://huggingface.co/google/gemma-4-26B-A4B-it) on
Hugging Face and accept Google's terms. Then log in with
`uvx --from huggingface_hub hf auth login`, and start vLLM again.

vLLM is ready when `curl http://localhost:8000/v1/models` lists
`google/gemma-4-26B-A4B-it`. Gentrex sends the text of every page to this
server, so run it on a machine approved for patient data.

Stage 2 relies on three vLLM defaults, so the command above leaves them out.
If you add options of your own, keep these:

- Prefix caching stays on. Gentrex asks all questions about a page one after
  another, and each request starts with the same page. With
  [prefix caching](../README.md#terms), vLLM reads the page once and reuses
  that work for the other questions.
- `--logprobs-mode` stays `raw_logprobs`. [Logprobs](../README.md#terms) are
  the probabilities of the most likely tokens, which stage 2 reads instead of
  the answer. `raw_logprobs` returns them as the model computed them, before
  settings such as temperature change them.
- `--max-logprobs` stays at 20 or more, so that vLLM can return the 20 most
  likely first tokens that Gentrex asks for.

## Step 2: Point Gentrex at the model server

Stages 2 and 3 read the text model's address and API key from `.env`. If you
have no `.env` file yet, create it from the example file:

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
uv run --env-file .env gentrex stage2
```

Gentrex reads the newest finished stage 1 run, `results/transcribe/latest`,
and writes a new folder named after the time the run started, such as
`results/pagedecide/20261014-131500/`. To read another stage 1 run:

```bash
uv run --env-file .env gentrex stage2 --input results/transcribe/20261014-123000
```

While it runs, Gentrex prints one line per PDF. The last line counts the pages
and the kept pages, and gives the speed in pages per minute.

## Check the result

The run folder holds four files:

| File | Contents |
| --- | --- |
| `decisions.jsonl` | The scores and the keep flag of every page. |
| `pages.jsonl` | The kept pages, unchanged from stage 1. Stage 3 reads this file. |
| `run.yaml` | The command, the stage 1 run that was read, and the settings. |
| `log.txt` | What Gentrex printed during the run. |

Stage 3 reads the newest finished run, `results/pagedecide/latest`, unless you
name another. [Runs and results](../README.md#runs-and-results) explains run
folders and `latest`.

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
| `keep` | `true` if stage 3 reads the page. |
| `error` | Why questions failed on this page, or the page's stage 1 error. `null` when nothing went wrong. |

To count the kept pages:

```bash
grep -c '"keep": true' results/pagedecide/latest/decisions.jsonl
```

To list the pages with an error:

```bash
grep -v '"error": null' results/pagedecide/latest/decisions.jsonl
```

To compare runs, for example after rewording a question, give grep all of
them. It prints one count per run:

```bash
grep -c '"keep": true' results/pagedecide/*/decisions.jsonl
```

The model is often more sure of its answer than it should be, so a dropped
page can still matter. Before you rely on the decisions, open some dropped
pages in their PDFs and check that none of them reports a result.

## How it works

Gentrex sends the model one page and one question per request. Each request
holds the instruction (`pagedecide.instruction` in settings.yaml), the page's
text and the question, followed by "Answer with Yes or No."

Models write text in tokens, which are words or pieces of words. Gentrex asks
vLLM for the 20 most likely first tokens of the answer and their
probabilities. It reads those instead of the token the model writes, for
example:

| First token | Probability |
| --- | --- |
| `Yes` | 0.951 |
| `No` | 0.041 |
| ` yes` | 0.002 |

vLLM returns these as logprobs, the logarithms of the probabilities, and
Gentrex turns them back into probabilities. It adds up the tokens that spell
the same answer, ignoring case and spaces, such as `Yes` and ` yes` with a
leading space. Here that gives 0.953 for yes and 0.041 for no. Gentrex turns
the two into `p_yes`, the probability that the answer is yes, as
0.953 / (0.953 + 0.041) = 0.96.

Gemma 4 has a thinking mode, in which it writes out its reasoning before the
answer. Gentrex turns it off in every request, so the first token is the
answer.

A page is kept when at least one question has a `p_yes` of 0.5 or more
(`pagedecide.keep_threshold`). A page is also kept when Gentrex can't tell
whether it matters:

- OCR failed on the page in stage 1, so there is no text to ask about. The page
  and its error go on to stage 3, and the report is listed as failed. Run
  stage 1 again to read the page.
- A question got no usable answer. The server still failed after its retries,
  rejected the page (for example because it is longer than `--max-model-len`
  allows), or the model's first token was neither Yes nor No.

A page with no text and no error is empty. Gentrex drops it without asking the
model. This includes scanned pages when stage 1 ran with `--no-ocr`.

### Why Gentrex uses probabilities

- A probability is a score, so you can choose how sure the model must be.
  `keep_threshold` sets the cut-off, and `p_yes` in `decisions.jsonl` shows how
  close each page came to it.
- It is cheap. vLLM reads the whole page in one pass through the model, which
  the GPU runs in parallel, and that pass already gives the probabilities of
  the first token. Each further token would take one more pass. Gentrex asks
  for one token, so a question costs little more than reading the page.

## Settings

The questions are under `pagedecide` in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml),
with the model, the threshold and the other stage 2 settings. A comment above
each value explains it.

```yaml
  questions:
    has_result: >-
      Does this page state the patient's test result or list the variants
      found in the patient? Answer No if the page only explains the result,
      recommends next steps or describes the test.
```

- To reword a question, edit its text.
- To add a question, add a name and its text. The name labels the answer in
  `p_yes`.
- To remove a question, delete it.

Phrase each question about "this page", so that Yes or No answers it. Gentrex
adds "Answer with Yes or No." after each question. Each question adds one
request per page. To leave a kind of page out, name it in the question, as
`has_result` does with "Answer No if the page only ...".

Don't ask about something every page shows, such as the patient's name or date
of birth. Page headers repeat them, so the answer is yes on every page and
every page is kept. If too many pages are kept, check which question has a
high `p_yes` on them, and reword or remove it.

`keep_threshold` is 0.5 by default. Lower it to keep more pages, so that fewer
result pages are missed but stage 3 has more to read. Raise it to keep fewer
pages.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every page was decided. | Nothing. |
| 1 | No finished stage 1 run was found (`pages.jsonl not found; run stage 1 first`), some files had errors, or the run stopped with a traceback. The end of the output lists the failed files. | See below. |
| 2 | `GENTREX_LLM_BASE_URL` is not set. | Do step 2. |

A file is listed as failed in two cases:

- **A question failed on one of its pages.** The page is kept with its other
  answers, and `error` names the question. If the error is a connection error
  or a timeout, the server was down or busy, even after Gentrex's
  [retries](../README.md#runs-and-results). Check that the server is running,
  then run stage 2 again.
- **One of its pages has a stage 1 error.** The page is kept, and its `error`
  starts with `stage 1:`. Run stage 1 again, then stage 2.

An error that reads `answer starts with '...'` means the model's first token
was neither Yes nor No. For example, `'<|channel>'` is the token that starts
Gemma 4's reasoning, and `'**'` starts bold text. If many pages have such
errors, check that the server runs `google/gemma-4-26B-A4B-it` with the
model's own chat template, and reword the questions that cause them. A
[chat template](../README.md#terms) comes with each model. It turns each
request into the exact text format the model was trained on, including the
switch that turns thinking off. vLLM uses the model's own template unless you
start it with `--chat-template`.

A traceback means the run stopped early.
[Runs and results](../README.md#runs-and-results) explains the common causes.
Stage 2 also stops with `MissingLogprobsError: the server sent no logprobs`
when the server returns no logprobs. vLLM returns them, so use vLLM or another
server that does.
