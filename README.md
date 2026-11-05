# Gentrex

Gentrex (Genetic Test Report eXtraction) turns clinical genetic test reports
into data you can analyze. It reads a folder of PDF reports and writes one JSON
record per report. The record holds the patient's identifiers, the specimen,
the test, the overall result, the patient's clinical features and every
variant reported, with its gene, HGVS changes, classification and zygosity.
Gentrex can then load the records into a database, so that you can count
and compare reports with SQL. It can also export them as Phenopackets, the GA4GH
format for sharing a patient's clinical features and genetic findings, and
into an OMOP CDM database, where OHDSI's tools can study them together with
EHR data.

Gentrex is a command-line program. `gentrex transcribe`, `gentrex select` and
`gentrex extract` use models that run in a separate model server,
[vLLM](https://docs.vllm.ai), on GPUs that you control. Gentrex sends each
page or report to that server and writes what comes back. `gentrex normalize`
needs no server, because its models run inside Gentrex on the CPU.
`gentrex load` writes the records into one of three databases. A SQLite file
needs no server, and PostgreSQL and MySQL run as servers in Docker on your
workstation. `gentrex export phenopackets` writes files and needs no server
either.

## How it works

Gentrex turns the reports into records with four commands. You run them in
order, because each one reads the output of the one before it.

| Command | What it does | Writes to | Model and GPU |
| --- | --- | --- | --- |
| [`gentrex transcribe`](docs/transcribe.md) | Reads the text of every page. Scanned pages go to an OCR model, which reads the text off the image. | `results/transcribe/` | LightOnOCR-3-4B on one GPU, only for scanned pages |
| [`gentrex select`](docs/select.md) | Asks a language model yes/no questions about every page, and keeps the pages with the result or the patient's symptoms. | `results/select/` | Gemma 4 26B-A4B on one GPU with 80 GB |
| [`gentrex extract`](docs/extract.md) | Sends the kept pages of each report to a language model, which returns one record per report. | `results/extract/` | Gemma 4 31B on two GPUs with 80 GB, or one B200 |
| [`gentrex normalize`](docs/normalize.md) | Adds standard values to each record: ISO dates, categories for the specimen and the result, HGNC IDs for the genes, MONDO IDs for the diseases and HPO terms for the clinical features. | `results/normalize/` | SapBERT and EmbeddingGemma 2 on the CPU, no GPU |

Many pages of a report only describe the test. `gentrex select` drops them,
so `gentrex extract` has less to read.

Then you can load the records into a database, export them as Phenopackets
and export them into an OMOP database, in any combination. Each of these
commands reads the output of `gentrex normalize`, so you run only what you
need, in any order.

| Command | What it does | Writes to | Model and GPU |
| --- | --- | --- | --- |
| [`gentrex load`](docs/load.md) | Writes the records into tables of a SQLite, PostgreSQL or MySQL database, with the HPO terms and their hierarchy, so that you can query them with SQL. | The database, and `results/load/` | No model and no GPU |
| [`gentrex export phenopackets`](docs/export-phenopackets.md) | Writes one Phenopacket per patient, the GA4GH format that rare-disease tools read and other centers can import. | `results/export/phenopackets/` | No model and no GPU |
| [`gentrex export omop`](docs/export-omop.md) | Writes the records into the standard tables of an OMOP CDM database in PostgreSQL, so that OHDSI's tools, such as ATLAS, can select patients by gene, ACMG class and zygosity. | The CDM database, and `results/export/omop/` | No model and no GPU |
| [`gentrex export omop-extended`](docs/export-omop-extended.md) | Writes the same rows, and adds extension tables, outside the CDM's schema, with what the CDM can't hold, such as parental origin and full-length HGVS changes. | The CDM database, and `results/export/omop-extended/` | No model and no GPU |

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
[Extract report data](docs/extract.md#check-the-result) explains how to read
the records. [`gentrex normalize`](docs/normalize.md#check-the-result) adds
the standard values next to them, in a field named `normalized`.
[`gentrex load`](docs/load.md#check-the-result) stores both in tables of a
database, and
[`gentrex export phenopackets`](docs/export-phenopackets.md#check-the-result)
writes them as Phenopackets.
[`gentrex export omop`](docs/export-omop.md#check-the-result) writes them into
an OMOP CDM database.

## What you need

- [uv](https://docs.astral.sh/uv/), which installs Python and the packages
  Gentrex needs.
- NVIDIA GPUs with [vLLM](https://docs.vllm.ai) 0.25 or newer, which the
  model of `gentrex select` needs, or an account on Mount Sinai's Minerva
  cluster.
- A [Hugging Face](https://huggingface.co) account, if a Gemma download asks
  you to log in.
- About 120 GB of disk for the models: 9 GB for `gentrex transcribe`, 50 GB
  for `gentrex select` and 62 GB for `gentrex extract`.
- About 3 GB of disk for `gentrex normalize`: 400 MB for the HGNC complete
  set, the HPO and MONDO releases and the HPO index, and 2.8 GB for
  sentence-transformers, PyTorch and the two embedding models, which Gentrex
  uses to find HPO terms.
- A database, if you load the records into one. SQLite needs nothing more,
  because it comes with Python. PostgreSQL 18 and MySQL 8.4 are the servers
  that `gentrex load` is tested with, and it refuses the address of any other
  database. [Supported databases](docs/load.md#supported-databases) says what
  the tests check and how to add a database.
- An OMOP CDM database in PostgreSQL with OHDSI's vocabularies, if you export
  the records into OMOP. [Get a CDM database](docs/export-omop.md#step-1-get-a-cdm-database)
  says how to get one.
- [Docker](https://docs.docker.com/get-started/get-docker/), if you load the
  records into PostgreSQL or MySQL, or create a CDM database of your own. It
  runs the server in a container, which takes 1 to 2 GB of disk with the
  database. SQLite needs neither.
- Storage approved for patient data, for the reports and everything Gentrex
  writes from them.

## Get started

On your own machine, follow these pages in order. On each page, you start
the command's model server, run the command and check the result. You stop
the server before the next command starts its own.

1. [Transcribe PDF pages](docs/transcribe.md)
2. [Select the pages to keep](docs/select.md)
3. [Extract report data](docs/extract.md)
4. [Normalize report data](docs/normalize.md)

Then use the records in one or both of these ways:

- [Load report data into a database](docs/load.md)
- [Export report data as Phenopackets](docs/export-phenopackets.md)
- [Export report data into an OMOP database](docs/export-omop.md), or
  [with extension tables](docs/export-omop-extended.md)

`gentrex normalize`, `gentrex load`, `gentrex export phenopackets` and
`gentrex export omop` need no model server.

On Mount Sinai's Minerva cluster, `gentrex transcribe`, `gentrex select` and
`gentrex extract` run as batch jobs, and the other commands run in an
interactive session. Follow [Running on Minerva](docs/minerva.md).

## Runs and results

Every run writes a new folder, named after the time it started, such as
`results/transcribe/20261014-123000/`. Earlier runs stay, so you can compare
them. Besides the command's output, each run folder holds two files:

- `run.yaml` records the command, the input the run read and the settings it
  used. The input is the actual run folder, so you can always tell which run
  a result came from.
- `log.txt` holds everything Gentrex printed during the run.

`latest` in each command's folder, such as `results/transcribe/latest`, is a
link to the newest run that finished. The next command reads it unless you name
another run with `--input`. A run that finished with some failed files still
counts, so `latest` moves to it. A run that stopped with an error keeps its
folder, but `latest` stays where it was.

A run can't be resumed. Running a command again starts from the first file,
in a new folder.

When the model server can't be reached, is busy, returns a server error or
takes longer than the command's `timeout_seconds`, Gentrex tries the request
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
means the model server's address, or for `gentrex load` and
`gentrex export omop` the database's address, is not set. 2 also means a mistake on the command line, such as a
command or option that doesn't exist, and the message says which. Each
command's page says what to do for each code.

## Patient data

Reports, and everything Gentrex writes from them, may contain patient data.

- Keep the Gentrex folder on storage approved for patient data, because the
  reports go into its `data/` folder and the results into `results/`. Git
  ignores both folders, and reports and results must never be committed.
- Gentrex sends page images and page text to the model servers set in `.env`.
  Run those servers on machines approved for patient data.
- `gentrex load` and `gentrex export omop` write the records into the
  databases set in `.env`. Keep a SQLite file, or run a database server, only
  on a machine approved for patient data.

## Documentation

- [Transcribe PDF pages](docs/transcribe.md)
- [Select the pages to keep](docs/select.md)
- [Extract report data](docs/extract.md)
- [Normalize report data](docs/normalize.md)
- [Load report data into a database](docs/load.md)
  - [Database tables](docs/database-tables.md)
- [Export report data as Phenopackets](docs/export-phenopackets.md)
- [Export report data into an OMOP database](docs/export-omop.md)
  - [With extension tables](docs/export-omop-extended.md)
- [Running on Minerva (Mount Sinai)](docs/minerva.md)
- [Development](docs/development.md)
- [Evaluate HPO matching](evaluation/README.md)
