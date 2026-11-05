# Gentrex

Gentrex (Genetic Test Report eXtraction) reads clinical genetic test reports
in PDF form and writes one structured record per report. A record holds the
patient's identifiers, the specimen, the test, the overall result, the
clinical features and every reported variant with its gene, HGVS changes,
classification and zygosity.

You can query the records with SQL after `gentrex load`, or export them as
GA4GH Phenopackets, into an OMOP CDM or as HL7 FHIR Bundles. The language
models run in [vLLM](https://docs.vllm.ai) on GPUs that you control.

## How it works

Four commands turn the PDFs into records. Run them in this order:

| Command | What it does | Model and GPU |
| --- | --- | --- |
| [`gentrex transcribe`](docs/user-guide/transcribe.md) | Reads the text of every page. Scanned pages go through OCR. | LightOnOCR-3-4B on one GPU, for scanned pages only |
| [`gentrex select`](docs/user-guide/select.md) | Keeps the pages with the result or the patient's clinical features. Most other pages only describe the test. | Gemma 4 26B-A4B on one GPU with 80 GB |
| [`gentrex extract`](docs/user-guide/extract.md) | Turns the kept pages of each report into one record. | Gemma 4 31B on two GPUs with 80 GB, or one B200 |
| [`gentrex normalize`](docs/user-guide/normalize.md) | Adds ISO dates, categories for the specimen and the result, HGNC IDs, MONDO IDs and HPO terms. | SapBERT and EmbeddingGemma 2 on the CPU |

The other commands all read the output of `gentrex normalize`, so you run
only the ones you need:

| Command | What you get |
| --- | --- |
| [`gentrex load`](docs/user-guide/load.md) | Tables in SQLite, PostgreSQL or MySQL, with the HPO hierarchy |
| [`gentrex export phenopackets`](docs/user-guide/export-phenopackets.md) | One Phenopacket per patient, for rare-disease tools and other centers |
| [`gentrex export omop`](docs/user-guide/export-omop.md) | Rows in the standard tables of an OMOP CDM in PostgreSQL, for OHDSI tools like ATLAS |
| [`gentrex export omop-extended`](docs/user-guide/export-omop-extended.md) | The same rows, plus extension tables for what the CDM can't hold |
| [`gentrex export fhir`](docs/user-guide/export-fhir.md) | One FHIR Bundle per report, in HL7's Genomics Reporting format, for an EHR or a FHIR server |

None of these needs a GPU.

A record from `gentrex extract` looks like this, shortened:

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

Every field is described in
[`schema.yaml`](src/gentrex/defaults/schema.yaml). `gentrex normalize` keeps
the record as it is and adds its standard values in a field named
`normalized`.

## What you need

- [uv](https://docs.astral.sh/uv/), which installs Python and the
  dependencies.
- NVIDIA GPUs with [vLLM](https://docs.vllm.ai) 0.25 or newer, or an account
  on Mount Sinai's Minerva cluster.
- A [Hugging Face](https://huggingface.co) account. Google asks you to accept
  its terms before you can download a Gemma model.
- About 120 GB of disk for the models, and 3 GB more for
  `gentrex normalize`.
- A database for `gentrex load`. SQLite comes with Python. Gentrex is tested
  with PostgreSQL 18 and MySQL 8.4 and refuses
  [other databases](docs/user-guide/load.md#supported-databases).
- An OMOP CDM in PostgreSQL with OHDSI's vocabularies, for the OMOP exports.
  [Get a CDM database](docs/user-guide/export-omop.md#step-1-get-a-cdm-database)
  shows how to set one up.
- [Docker](https://docs.docker.com/get-started/get-docker/), if you run
  PostgreSQL, MySQL or a CDM of your own on your workstation.
- Storage approved for patient data.

## Get started

Work through these pages in order. Each one starts the model server that the
command needs, runs the command and checks its output. Stop each server
before you start the next one.

1. [Transcribe PDF pages](docs/user-guide/transcribe.md)
2. [Select the pages to keep](docs/user-guide/select.md)
3. [Extract report data](docs/user-guide/extract.md)
4. [Normalize report data](docs/user-guide/normalize.md)

Then load or export the records:

- [Load report data into a database](docs/user-guide/load.md)
- [Export report data as Phenopackets](docs/user-guide/export-phenopackets.md)
- [Export report data into an OMOP database](docs/user-guide/export-omop.md),
  with or without [extension tables](docs/user-guide/export-omop-extended.md)
- [Export report data as FHIR Bundles](docs/user-guide/export-fhir.md)

On Mount Sinai's Minerva cluster, the three GPU commands run as batch jobs and
the rest in an interactive session. [Running on Minerva](docs/minerva/minerva.md)
walks you through it.

## Runs and results

Every run gets a new folder named after its start time, for example
`results/transcribe/20261014-123000/`. A second run in the same second gets
`-2` added to the name. Old runs stay, so you can compare them.

Next to its output, each run folder has two files. `run.yaml` records the
command, the Gentrex version and git commit, the run it read and the
settings, so you can always trace a result back to what made it. It says
`modified: true` when the code in `src/gentrex/` had changes that weren't
committed. `log.txt` holds everything the run printed.
`uv run gentrex --version` prints the version.

`latest` in each command's folder, as in `results/transcribe/latest`, points
to the newest finished run. The next command reads it unless you name another
run with `--input`. A run that finished with some failed files still becomes
`latest`. A run that crashed doesn't.

When a request to the model server fails or times out, Gentrex tries it again
after 5, 20 and 60 seconds. After the fourth failure it records the error for
that page or report and moves on to the next. A wrong API key or model name
stops the run straight away, since every request would fail. A traceback that
ends in `openai.AuthenticationError` means the API key in `.env` is wrong.
`openai.NotFoundError` means the server runs a different model than
settings.yaml names, or the address in `.env` doesn't end in `/v1`.

The exit code, which `echo $?` prints right after a run, tells you how it
went. 0 means every file went through. 1 means some files failed, the input
was missing or the run crashed, and the last lines of the output say which. 2
means a value the command needs from `.env` isn't set, or the command line
has a mistake. Each command's page lists what to do.

### Redo failed files

If some pages or reports fail in `gentrex transcribe`, `gentrex select` or
`gentrex extract`, or a job hits its time limit, run the command again with
`--retry` and the earlier run's folder:

```bash
uv run --env-file .env gentrex extract --retry results/extract/latest
```

Every record that came through without an error is reused, and only the rest
go to the model. The log tells you how many, as in
`reusing 497 of 500 reports from results/extract/latest`. The new run still
writes a complete set of records, and its `run.yaml` names the earlier run
under `retry`.

A record is reused only if its input hasn't changed. This lets retries build
on each other. Once `gentrex transcribe --retry` has read a page that failed,
`gentrex select --retry` and `gentrex extract --retry` send just that report
to the model again. For a PDF, unchanged means the same pages, each scanned
or native as before, with the same text on the native ones.

The settings have to match the earlier run, except for `timeout_seconds`,
`concurrency` and `max_tokens`. Raising those is how most failures get fixed.
After any other change, such as a different model, run without `--retry`.

A run that crashed, like a job that hit its time limit, never becomes
`latest`. Name its folder instead, as in
`--retry results/extract/20261019-030000`.

Gentrex refuses the earlier run, with exit code 1, if the folder isn't a run
of the same command, if that run used other settings, or if the input it read
no longer exists. The message says which. In the last two cases, run the
command without `--retry`.

## Patient data

The reports, and everything Gentrex writes from them, can contain patient
data.

- Keep the Gentrex folder on storage approved for patient data. The reports
  go into `data/` and the results into `results/`. Git ignores both, and
  neither may ever be committed.
- Gentrex sends page images and text to the model servers in `.env`. Run
  them only on machines approved for patient data.
- The same goes for the databases that `gentrex load` and
  `gentrex export omop` write into, including a SQLite file.
- Phenopackets hold the MRN and the date of birth, unless you export them
  with `--pseudonymize` as
  [Share Phenopackets](docs/user-guide/export-phenopackets.md#share-phenopackets)
  explains.

## Documentation

The user guide in `docs/user-guide/` has a page for each command:

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

Running Gentrex on Minerva:

- [Running on Minerva (Mount Sinai)](docs/minerva/minerva.md)

Working on Gentrex itself:

- [Development](docs/development/development.md)
- [Contributing](docs/development/contributing.md)
- [Release a new version](docs/development/release.md)
- [Evaluate HPO matching](evaluation/README.md)

The [changelog](docs/CHANGELOG.md) lists what changed in each version.
