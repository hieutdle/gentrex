# Gentrex

Gentrex (Genetic Test Report eXtraction) turns clinical genetic test reports
into data you can analyze. It reads a folder of PDF reports and writes one JSON
record per report. The record holds the patient's identifiers, the specimen,
the test, the overall result, the patient's clinical features and every
variant reported, with its gene, HGVS changes, classification and zygosity.

Gentrex is a command-line program. The models it uses run in a separate
model server, [vLLM](https://docs.vllm.ai), on GPUs that you control.
Gentrex sends each page or report to that server and writes what comes
back.

## How it works

Gentrex works in three stages. You run them in order, and each stage reads
the output of the stage before it.

| Stage | What it does | Writes to | Model and GPU |
| --- | --- | --- | --- |
| [1. Transcribe PDF pages](docs/stage1.md) | Reads the text of every page. Scanned pages go to an OCR model, which reads the text off the image. | `results/transcribe/` | LightOnOCR-3-4B on one GPU, only for scanned pages |
| [2. Decide which pages to keep](docs/stage2.md) | Asks a language model yes/no questions about every page, and keeps the pages with the result or the patient's symptoms. | `results/pagedecide/` | Gemma 4 26B-A4B on one GPU with 80 GB |
| [3. Extract report data](docs/stage3.md) | Sends the kept pages of each report to a language model, which returns one record per report. | `results/extract/` | Gemma 4 31B on two GPUs with 80 GB, or one B200 |

Many pages of a report only describe the test. Stage 2 drops them, so stage 3
has less to read.

Each record is one line of `extractions.jsonl`. Shortened and spread over
several lines, a record looks like this:

```json
{
  "file": "report-01.pdf",
  "pages": [1, 2, 4],
  "data": {
    "mrn": "SYN-MRN-0001",
    "date_of_birth": "06/19/1981",
    "sex": "Female",
    "test_name": "Hereditary Cancer Panel",
    "test_type": "panel",
    "overall_result_raw": "POSITIVE: A pathogenic variant was identified.",
    "patient_phenotypes": [{"text": "Breast cancer at age 38", "present": true}],
    "variants": [
      {
        "page": 1,
        "gene_symbol": "BRCA1",
        "transcript": "NM_007294.4",
        "hgvs_c": "c.5266dupC",
        "hgvs_p": "p.(Gln1756Profs*74)",
        "classification_raw": "Pathogenic",
        "classification": "pathogenic",
        "zygosity_raw": "Heterozygous",
        "zygosity": "heterozygous"
      }
    ]
  },
  "error": null
}
```

All the fields, with what each one holds, are in
[`schema.yaml`](src/gentrex/defaults/schema.yaml).
[Stage 3](docs/stage3.md#check-the-result) explains how to read and load the
records.

## What you need

- [uv](https://docs.astral.sh/uv/), which installs Python and the packages
  Gentrex needs.
- NVIDIA GPUs with [vLLM](https://docs.vllm.ai) 0.25 or newer, which the
  stage 2 model needs, or an account on Mount Sinai's Minerva cluster.
- A [Hugging Face](https://huggingface.co) account, if a Gemma download asks
  you to log in.
- About 120 GB of disk for the models: 9 GB for stage 1, 50 GB for stage 2
  and 62 GB for stage 3.
- Storage approved for patient data, for the reports and everything Gentrex
  writes from them.

## Get started

On your own machine, follow the stage pages in order. On each page, you start
the stage's model server, run the stage and check the result. You stop the
server before the next stage starts its own.

1. [Stage 1: Transcribe PDF pages](docs/stage1.md)
2. [Stage 2: Decide which pages to keep](docs/stage2.md)
3. [Stage 3: Extract report data](docs/stage3.md)

On Mount Sinai's Minerva cluster, each stage runs as a batch job. Follow
[Running on Minerva](docs/minerva.md).

## Runs and results

Every run writes a new folder, named after the time it started, such as
`results/transcribe/20261014-123000/`. Earlier runs stay, so you can compare
them. Besides the stage's output, each run folder holds two files:

- `run.yaml` records the command, the input the run read and the settings it
  used. The input is the actual run folder, so you can always tell which run
  a result came from.
- `log.txt` holds everything Gentrex printed during the run.

`latest` in each stage's folder, such as `results/transcribe/latest`, is a
link to the newest run that finished. The next stage reads it unless you name
another run with `--input`. A run that finished with some failed files still
counts, so `latest` moves to it. A run that stopped with an error keeps its
folder, but `latest` stays where it was.

A run can't be resumed. Running a stage again starts from the first file, in
a new folder.

When the model server can't be reached, is busy, returns a server error or
takes longer than the stage's `timeout_seconds`, Gentrex tries the request
again after 5, 20 and 60 seconds. If the fourth try fails too, Gentrex records
the error for that page or report and goes on with the others.

A wrong API key or a model name the server doesn't know stops the run at once,
because every request would fail the same way. Gentrex then prints a Python
traceback. If it ends in `openai.AuthenticationError`, fix the API key in
`.env`. If it ends in `openai.NotFoundError`, the server runs a different
model than settings.yaml names, or the address in `.env` doesn't end in
`/v1`.

Gentrex ends with an exit code, which `echo $?` shows right after a run. 0
means every file went through. 1 means that some files failed, the input was
missing or the run stopped with an error. The end of the output says which. 2
means the model server's address is not set. Each stage page says what to do
for each code.

## Patient data

Reports, and everything Gentrex writes from them, may contain patient data.

- Keep the Gentrex folder on storage approved for patient data, because the
  reports go into its `data/` folder and the results into `results/`. Git
  ignores both folders, and reports and results must never be committed.
- Gentrex sends page images and page text to the model servers set in `.env`.
  Run those servers on machines approved for patient data.

## Terms

| Term | What it means | Where you meet it |
| --- | --- | --- |
| Model server | A program that loads a model onto GPUs and answers requests over HTTP. Gentrex uses [vLLM](https://docs.vllm.ai). | `vllm serve`, the addresses in `.env` |
| OpenAI-compatible API | The request format of OpenAI's API, which vLLM accepts too. Gentrex sends requests in this format to the server address in `.env` and nowhere else. | The `/v1` at the end of the address, `openai.` in error names |
| Weights | The numbers a model learned in training. They are files of several GB that vLLM loads into GPU memory, so their size sets how much memory a model needs. | Model sizes on the stage pages |
| Token | A word or a piece of a word, the unit a model reads and writes. 1,000 tokens are about 750 English words. | `--max-model-len`, `max_tokens` in settings.yaml |
| Context length | The most tokens one request can hold, counting both the input and the answer. | `--max-model-len`, `maximum context length` errors |
| KV cache | The GPU memory that holds the requests vLLM is working on. It gets the memory that the weights leave free. | `--gpu-memory-utilization`, memory errors when vLLM starts |
| Prefix caching | vLLM keeps the KV cache of text it has read. A later request that starts with the same text reuses it instead of reading that text again. It is on by default. | `--no-enable-prefix-caching` |
| Logprobs | Log-probabilities. With each token the model writes, vLLM can return the most likely tokens and how likely each one was. | `--logprobs-mode`, `--max-logprobs`, `the server sent no logprobs` |
| Chat template | A file that comes with a model and turns a request into the exact text format the model was trained on. vLLM applies it to every request. | `--default-chat-template-kwargs`, `--chat-template` |
| Thinking | A mode in which the model writes out its reasoning before the answer. Every stage runs its model with thinking off, so vLLM needs no `--reasoning-parser`. | `enable_thinking` |
| Structured output | vLLM lets the model write only text that follows a given format. Stage 3 gives the format as a [JSON Schema](https://json-schema.org/), a standard way to describe the fields of a JSON object. | `schema.yaml`, `response_format` |
| Tensor parallelism | Splitting a model across several GPUs, so that a model too large for one GPU runs on two. | `--tensor-parallel-size` |
| JSONL | JSON Lines, a text file with one JSON object per line. | `pages.jsonl`, `decisions.jsonl`, `extractions.jsonl` |

## Documentation

- [Stage 1: Transcribe PDF pages](docs/stage1.md)
- [Stage 2: Decide which pages to keep](docs/stage2.md)
- [Stage 3: Extract report data](docs/stage3.md)
- [Running on Minerva (Mount Sinai)](docs/minerva.md)
- [Development](docs/development.md)
