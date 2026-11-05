# Gentrex

Gentrex (Genetic Test Report eXtraction) turns clinical genetic test reports
into structured data. Labs like GeneDx and Invitae send these reports as
PDFs, and only a few of their pages hold the findings. Gentrex finds those
pages and writes one record per report, with the patient's details, the
overall result, the clinical features and each reported variant. It adds
standard IDs from HGNC, MONDO and HPO, so reports from different labs can be
compared.

You can then load the records into a SQL database, or export them as
Phenopackets, into an OMOP CDM or as FHIR® Bundles.

![One report through Gentrex. transcribe reads the text of its 8 pages, with OCR for the 2 scanned ones. select keeps 3 pages. extract turns them into one record with the values as printed, like SCN1A and Dravet syndrome. normalize adds IDs like HGNC:10585 and MONDO:0100135. The records then load into SQLite, PostgreSQL or MySQL, or export as Phenopackets, into an OMOP CDM or as FHIR Bundles.](docs/images/gentrex-arch.svg)

## Running Gentrex

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
| [`gentrex export fhir`](docs/user-guide/export-fhir.md) | One FHIR Bundle per report, in the HL7® Genomics Reporting format, for an EHR or a FHIR server |

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

Each run writes a new folder in `results/`.
[Runs and results](docs/user-guide/runs-and-results.md) explains what's in
it, what the exit codes mean and how to redo only the files that failed.

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

The user guide in `docs/user-guide/` has a page for each command, and one
for what they have in common:

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
- [Runs and results](docs/user-guide/runs-and-results.md)

Running Gentrex on Minerva:

- [Running on Minerva (Mount Sinai)](docs/minerva/minerva.md)

Working on Gentrex itself:

- [Development](docs/development/development.md)
- [Contributing](docs/development/contributing.md)
- [Release a new version](docs/development/release.md)
- [Evaluate HPO matching](evaluation/README.md)
- [Benchmark design](docs/development/benchmark.md)
- [Run the benchmark (gentrex-bench)](gentrex-bench/README.md)

The [changelog](docs/CHANGELOG.md) lists what changed in each version.

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
