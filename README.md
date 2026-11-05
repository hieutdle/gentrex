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
EHR data. As FHIR Bundles, HL7's format for genetic test results, the reports
can go into an EHR or a FHIR server.

Gentrex is a command-line program. `gentrex transcribe`, `gentrex select` and
`gentrex extract` use models that run in a separate model server,
[vLLM](https://docs.vllm.ai), on GPUs that you control. Gentrex sends each
page or report to that server and writes what comes back. `gentrex normalize`
needs no server, because its models run inside Gentrex on the CPU.
`gentrex load` writes the records into one of three databases. A SQLite file
needs no server, and PostgreSQL and MySQL run as servers in Docker on your
workstation. `gentrex export phenopackets` and `gentrex export fhir` write
files and need no server either.

## How it works

Gentrex turns the reports into records with four commands. You run them in
order, because each one reads the output of the one before it.

| Command | What it does | Writes to | Model and GPU |
| --- | --- | --- | --- |
| [`gentrex transcribe`](docs/user-guide/transcribe.md) | Reads the text of every page. Scanned pages go to an OCR model, which reads the text off the image. | `results/transcribe/` | LightOnOCR-3-4B on one GPU, only for scanned pages |
| [`gentrex select`](docs/user-guide/select.md) | Asks a language model yes/no questions about every page, and keeps the pages with the result or the patient's symptoms. | `results/select/` | Gemma 4 26B-A4B on one GPU with 80 GB |
| [`gentrex extract`](docs/user-guide/extract.md) | Sends the kept pages of each report to a language model, which returns one record per report. | `results/extract/` | Gemma 4 31B on two GPUs with 80 GB, or one B200 |
| [`gentrex normalize`](docs/user-guide/normalize.md) | Adds standard values to each record: ISO dates, categories for the specimen and the result, HGNC IDs for the genes, MONDO IDs for the diseases and HPO terms for the clinical features. | `results/normalize/` | SapBERT and EmbeddingGemma 2 on the CPU, no GPU |

Many pages of a report only describe the test. `gentrex select` drops them,
so `gentrex extract` has less to read.

Then you can load the records into a database, export them as Phenopackets
or FHIR Bundles and export them into an OMOP database, in any combination.
Each of these commands reads the output of `gentrex normalize`, so you run
only what you need, in any order.

| Command | What it does | Writes to | Model and GPU |
| --- | --- | --- | --- |
| [`gentrex load`](docs/user-guide/load.md) | Writes the records into tables of a SQLite, PostgreSQL or MySQL database, with the HPO terms and their hierarchy, so that you can query them with SQL. | The database, and `results/load/` | No model and no GPU |
| [`gentrex export phenopackets`](docs/user-guide/export-phenopackets.md) | Writes one Phenopacket per patient, the GA4GH format that rare-disease tools read and other centers can import. | `results/export/phenopackets/` | No model and no GPU |
| [`gentrex export omop`](docs/user-guide/export-omop.md) | Writes the records into the standard tables of an OMOP CDM database in PostgreSQL, so that OHDSI's tools, such as ATLAS, can select patients by gene, ACMG class and zygosity. | The CDM database, and `results/export/omop/` | No model and no GPU |
| [`gentrex export omop-extended`](docs/user-guide/export-omop-extended.md) | Writes the same rows, and adds extension tables, outside the CDM's schema, with what the CDM can't hold, such as parental origin and full-length HGVS changes. | The CDM database, and `results/export/omop-extended/` | No model and no GPU |
| [`gentrex export fhir`](docs/user-guide/export-fhir.md) | Writes one FHIR Bundle per report, following HL7's Genomics Reporting Implementation Guide, so that an EHR or a FHIR server can take in the results. | `results/export/fhir/` | No model and no GPU |

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
[Extract report data](docs/user-guide/extract.md#check-the-result) explains how to read
the records. [`gentrex normalize`](docs/user-guide/normalize.md#check-the-result) adds
the standard values next to them, in a field named `normalized`.
[`gentrex load`](docs/user-guide/load.md#check-the-result) stores both in tables of a
database, and
[`gentrex export phenopackets`](docs/user-guide/export-phenopackets.md#check-the-result)
writes them as Phenopackets.
[`gentrex export omop`](docs/user-guide/export-omop.md#check-the-result) writes them into
an OMOP CDM database, and
[`gentrex export fhir`](docs/user-guide/export-fhir.md#check-the-result) writes them as
FHIR Bundles.

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
  database. [Supported databases](docs/user-guide/load.md#supported-databases) says what
  the tests check and how to add a database.
- An OMOP CDM database in PostgreSQL with OHDSI's vocabularies, if you export
  the records into OMOP. [Get a CDM database](docs/user-guide/export-omop.md#step-1-get-a-cdm-database)
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

1. [Transcribe PDF pages](docs/user-guide/transcribe.md)
2. [Select the pages to keep](docs/user-guide/select.md)
3. [Extract report data](docs/user-guide/extract.md)
4. [Normalize report data](docs/user-guide/normalize.md)

Then use the records in one or more of these ways:

- [Load report data into a database](docs/user-guide/load.md)
- [Export report data as Phenopackets](docs/user-guide/export-phenopackets.md)
- [Export report data into an OMOP database](docs/user-guide/export-omop.md), or
  [with extension tables](docs/user-guide/export-omop-extended.md)
- [Export report data as FHIR Bundles](docs/user-guide/export-fhir.md)

`gentrex normalize`, `gentrex load` and the exports need no model server.

On Mount Sinai's Minerva cluster, `gentrex transcribe`, `gentrex select` and
`gentrex extract` run as batch jobs, and the other commands run in an
interactive session. Follow [Running on Minerva](docs/minerva/minerva.md).

## Runs and results

Every run writes a new folder, named after the time it started, such as
`results/transcribe/20261014-123000/`. A second run that starts in the same
second gets `-2` added to the name. Earlier runs stay, so you can compare
them. Besides the command's output, each run folder holds two files:

- `run.yaml` records the command, the version of Gentrex, the input the run
  read and the settings it used. The input is the actual run folder, so you
  can always tell which run a result came from. When Gentrex runs from a git
  clone, `run.yaml` also records the commit, and `modified: true` if the code
  in `src/gentrex/` has changes that aren't committed. Changes to
  settings.yaml and schema.yaml don't count, because `run.yaml` records the
  settings themselves. `uv run gentrex --version` prints the version.
- `log.txt` holds everything Gentrex printed during the run.

`latest` in each command's folder, such as `results/transcribe/latest`, is a
link to the newest run that finished. The next command reads it unless you name
another run with `--input`. A run that finished with some failed files still
counts, so `latest` moves to it. A run that stopped with an error keeps its
folder, but `latest` stays where it was.

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
means that a value the command needs from `.env` is not set, such as the
model server's address, the database's address for `gentrex load` and
`gentrex export omop`, or the pseudonym key for
`gentrex export phenopackets --pseudonymize`. 2 also means a mistake on the
command line, such as a command or option that doesn't exist, and the message
says which. Each command's page says what to do for each code.

### Redo failed files

`gentrex transcribe`, `gentrex select` and `gentrex extract` send each page
or report to a model on a GPU. If some fail, or a job stops at its time limit,
run the command again with `--retry` and the folder of the earlier run:

```bash
uv run --env-file .env gentrex extract --retry results/extract/latest
```

The new run reuses every record of the earlier run that has no error, and
sends only the others to the model. It writes all the records to a new run
folder, so the next command reads one complete run, and `run.yaml` names the
earlier run under `retry`. The log says how many records were reused, as in
`reusing 497 of 500 reports from results/extract/latest`.

A record is reused only if its input is the same as when the earlier run read
it. So when `gentrex transcribe --retry` reads a page that failed before,
`gentrex select --retry` and `gentrex extract --retry` send only that page's
report to the model again. For `gentrex transcribe`, a PDF counts as the same
if it has the same pages, each scanned or native as before, with the same
text on its native pages.

The settings in settings.yaml must be the same as in the earlier run, except
`timeout_seconds`, `concurrency` and `max_tokens`. These only limit how long
Gentrex waits for an answer, how many requests it sends at once and how long
an answer may be, so raising them is how most failures are fixed. After any
other change, such as another model, run the command without `--retry`.

`latest` doesn't move to a run that stopped halfway, such as a job that
reached its time limit. To continue such a run, name its folder, as in
`--retry results/extract/20261019-030000`.

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
- Phenopackets hold the MRN and the date of birth, unless you export them
  with `--pseudonymize`, as
  [Share Phenopackets](docs/user-guide/export-phenopackets.md#share-phenopackets) shows.

## Documentation

Most pages are in `docs/`, in one folder for each use.

The user guide, in `docs/user-guide/`, explains how Gentrex works and how to
run each command:

- [Transcribe PDF pages](docs/user-guide/transcribe.md)
- [Select the pages to keep](docs/user-guide/select.md)
- [Extract report data](docs/user-guide/extract.md)
- [Normalize report data](docs/user-guide/normalize.md)
- [Load report data into a database](docs/user-guide/load.md)
  - [Database tables](docs/user-guide/database-tables.md)
- [Export report data as Phenopackets](docs/user-guide/export-phenopackets.md)
- [Export report data into an OMOP database](docs/user-guide/export-omop.md)
  - [With extension tables](docs/user-guide/export-omop-extended.md)
- [Export report data as FHIR Bundles](docs/user-guide/export-fhir.md)

Running Gentrex on Minerva, in `docs/minerva/`:

- [Running on Minerva (Mount Sinai)](docs/minerva/minerva.md)

Working on Gentrex itself, in `docs/development/`:

- [Development](docs/development/development.md)
- [Contributing](docs/development/contributing.md)
- [Release a new version](docs/development/release.md)
- [Evaluate HPO matching](evaluation/README.md), next to its script in
  `evaluation/`

The [changelog](docs/CHANGELOG.md) lists what changed in each version.
