# Export report data as Phenopackets

`gentrex export phenopackets` writes one Phenopacket per patient. A
Phenopacket is a JSON file in GA4GH's format for one patient's clinical
features and genetic findings, published as ISO standard 4454:2022.
Rare-disease tools such as Exomiser and LIRICAL read it, and other centers can
import your results without learning Gentrex's own format.

For example, a report on a girl with seizures and a pathogenic SCN1A variant
becomes a Phenopacket with these parts:

- The HPO term HP:0001250, Seizure.
- The variant `NM_001165963.4:c.4933C>T` in SCN1A, heterozygous and
  pathogenic.
- The diagnosis MONDO:0100135, Dravet syndrome, which `gentrex normalize`
  found for the variant's `associated_phenotype`.

The export reads `normalized.jsonl` and `run.yaml` from a run of
`gentrex normalize` and writes to `results/export/phenopackets/`. A few
hundred reports take about a second.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex normalize` in `results/normalize/`, made with the
  [MONDO release](normalize.md#step-3-download-the-mondo-release).

## Step 1: Run

```bash
uv run gentrex export phenopackets
```

This reads the newest finished run of `gentrex normalize`, in
`results/normalize/latest`, and writes a new folder, for example
`results/export/phenopackets/20261104-203946/`. To export another run:

```bash
uv run gentrex export phenopackets --input results/normalize/20261019-030000
```

You'll see a line for each Phenopacket, for example
`wrote mrn_SYN-MRN-0001.json from report-01.pdf, report-02.pdf`, and then the
totals, as in `wrote 2 Phenopackets from 3 of 4 reports in 0 s`.

## Check the result

The run folder contains:

| File | Contents |
| --- | --- |
| `phenopackets/` | One JSON file per patient, named after the patient's key, like `mrn_SYN-MRN-0001.json`. |
| `run.yaml` | The command, the run of `gentrex normalize` that was read, and the MONDO and HPO releases that it used. |
| `pseudonyms.csv` | Only with `--pseudonymize`. Each patient key and file name with its pseudonym. |
| `log.txt` | Everything the run printed. |

`results/export/phenopackets/latest` points to the newest finished run
([Runs and results](../../README.md#runs-and-results)).

The Phenopackets contain patient identifiers. Each `id` is the patient's key,
such as `mrn:SYN-MRN-0001`, so it includes the MRN. The subject has the date of
birth, and the IDs of the interpretations include the PDF's file name. To
share Phenopackets with anyone not approved to see patient data, export them
with pseudonyms ([Share Phenopackets](#share-phenopackets)).

A Phenopacket looks like this, shortened:

```json
{
  "id": "mrn:SYN-MRN-0001",
  "subject": {"id": "mrn:SYN-MRN-0001", "dateOfBirth": "2018-05-14T00:00:00Z", "sex": "FEMALE"},
  "phenotypicFeatures": [
    {"type": {"id": "HP:0001250", "label": "Seizure"}},
    {"type": {"id": "HP:0000365", "label": "Hearing impairment"}, "excluded": true}
  ],
  "interpretations": [
    {
      "id": "report-01.pdf:1",
      "progressStatus": "COMPLETED",
      "summary": "POSITIVE: A pathogenic variant was identified.",
      "diagnosis": {
        "disease": {"id": "MONDO:0100135", "label": "Dravet syndrome"},
        "genomicInterpretations": [
          {
            "subjectOrBiosampleId": "mrn:SYN-MRN-0001",
            "interpretationStatus": "CANDIDATE",
            "variantInterpretation": {
              "variationDescriptor": {
                "id": "report-01.pdf:1",
                "label": "SCN1A c.4933C>T p.(Arg1645*)",
                "geneContext": {"valueId": "HGNC:10585", "symbol": "SCN1A"},
                "expressions": [{"syntax": "hgvs.c", "value": "NM_001165963.4:c.4933C>T"}],
                "allelicState": {"id": "GENO:0000135", "label": "heterozygous"}
              },
              "acmgPathogenicityClassification": "PATHOGENIC"
            }
          }
        ]
      }
    }
  ],
  "metaData": {
    "created": "2026-11-04T19:39:46Z",
    "createdBy": "Gentrex",
    "resources": [
      {"id": "hp", "name": "human phenotype ontology", "url": "http://purl.obolibrary.org/obo/hp.owl", "version": "2026-09-01", "namespacePrefix": "HP", "iriPrefix": "http://purl.obolibrary.org/obo/HP_"},
      {"id": "mondo", "name": "Mondo Disease Ontology", "url": "http://purl.obolibrary.org/obo/mondo.owl", "version": "2026-11-03", "namespacePrefix": "MONDO", "iriPrefix": "http://purl.obolibrary.org/obo/MONDO_"},
      {"id": "geno", "name": "Genotype Ontology", "url": "http://purl.obolibrary.org/obo/geno.owl", "version": "2026-02-02", "namespacePrefix": "GENO", "iriPrefix": "http://purl.obolibrary.org/obo/GENO_"}
    ],
    "phenopacketSchemaVersion": "2.0"
  }
}
```

Its fields come from the record of `gentrex normalize`:

| Phenopacket field | From |
| --- | --- |
| `subject.dateOfBirth`, `subject.sex` | `normalized.date_of_birth`, and `data.sex` as printed, like `F` or `Female`. |
| `phenotypicFeatures` | The HPO term of each clinical feature. `excluded` is `true` for a feature that the patient doesn't have, with `present` set to `false`. |
| `interpretations` | One per report and disease. `summary` is the report's `overall_result_raw`. |
| `progressStatus` | `UNSOLVED` for a negative report, `COMPLETED` for any other result, and `UNKNOWN_PROGRESS` if `overall_result` is `null`. |
| `diagnosis.disease` | The variant's `disease_id` and `disease_label` from `gentrex normalize`. |
| `interpretationStatus` | `CANDIDATE` for a primary finding, `UNKNOWN_STATUS` for a secondary finding, and `REJECTED` for a benign or likely benign variant. |
| `acmgPathogenicityClassification` | `classification` in capitals. `other` has no ACMG class and is left out. |
| `geneContext` | `hgnc_id` and `gene_symbol`. |
| `expressions` | `transcript` and `hgvs_c` as one HGVS expression. |
| `allelicState` | `zygosity` as a term of the Genotype Ontology (GENO). |
| `label` | The gene symbol, `hgvs_c` or `dna_change_raw`, and `hgvs_p`. |

To check that every file follows the Phenopacket schema, parse them with
GA4GH's Python package:

```bash
uv run --with phenopackets python -c "
import pathlib
from google.protobuf import json_format
from phenopackets import Phenopacket
paths = sorted(pathlib.Path('results/export/phenopackets/latest/phenopackets').glob('*.json'))
for path in paths:
    json_format.Parse(path.read_text(), Phenopacket())
print(len(paths), 'files follow the schema')
"
```

If a file breaks the schema, the package stops with an error that names the
field.

### Share Phenopackets

With `--pseudonymize`, each patient key and PDF file name is replaced by a
pseudonym, for example `P-5a1ccba4f48d478f` for `mrn:SYN-MRN-0001`, and the
date of birth is left out. The pseudonyms are made with a secret key of
yours. The same patient gets the same pseudonym in every run, and nobody
without the key can tell whose a Phenopacket is.

Make a key once with `openssl rand -hex 32` and add it to `.env` as
`GENTREX_PSEUDONYM_KEY` (see `.env.example`). Keep it secret and keep using
it, because a new key gives every patient a new pseudonym. Then export:

```bash
uv run --env-file .env gentrex export phenopackets --pseudonymize
```

The files are now named after the pseudonyms, as in
`P-5a1ccba4f48d478f.json`. Your team can look up the patient behind a
Phenopacket in `pseudonyms.csv` in the run folder:

```text
name,pseudonym
mrn:SYN-MRN-0001,P-5a1ccba4f48d478f
report-01.pdf,R-6947a2b0db4251c0
```

Share only the `phenopackets/` folder, because `pseudonyms.csv` contains the
MRNs and `log.txt` names the PDFs. Each interpretation's `summary` is the
report's own wording of the result. Read a few before you share them, in case
a laboratory wrote the patient's name there.

## How it works

### One Phenopacket per patient

The reports with the same `patient_key` as in
[`gentrex load`](load.md#link-reports-to-patients) go into one Phenopacket,
and each report adds its own interpretations.

The date of birth and sex are kept only when all reports that give one agree.
If `gentrex extract` misread the date of birth on one of two reports, neither
date goes in, because Gentrex can't tell which one is right.

Each HPO term appears once. It's excluded only if no report of the patient
finds the feature present. Features that a report is unsure of, with
`present` set to `null`, are left out, because a Phenopacket has no value for
them. If `gentrex normalize` ran with `--no-hpo`, there are no features.

### Diagnoses

In a Phenopacket, each variant belongs to a diagnosis, so the variants of a
report are grouped by MONDO disease into one interpretation per disease. A
report with a pathogenic SCN1A variant for Dravet syndrome and a secondary
BRCA2 finding for hereditary breast and ovarian cancer gets two.

A variant for which `gentrex normalize` found no MONDO disease goes under
MONDO:0000001, disease, the root term of MONDO, because a diagnosis needs a
disease. A negative report, or any other without variants, gets one
interpretation without a diagnosis.

Gentrex doesn't decide whether a variant causes the patient's disease, or
whether a report solves the case. A positive report is therefore `COMPLETED`,
not `SOLVED`, and a primary finding is a `CANDIDATE`, not `CAUSATIVE`. The
laboratory's own assessment is in `acmgPathogenicityClassification` and the
`summary`.

### Variants

An HGVS expression needs a reference sequence. `hgvs_c` becomes one when it
starts with a reference sequence, as in `NM_000059.4:c.5946del`, or when the
report names the `transcript`. The protein change goes only into the `label`,
because reports rarely print the protein's reference sequence. So does a
change without a c. notation, such as a mitochondrial change or a deletion of
whole exons, as printed in `dna_change_raw`.

### Pseudonyms

Gentrex computes each pseudonym with HMAC-SHA256, a hash that needs the key
in `GENTREX_PSEUDONYM_KEY`. It hashes the name with `P:` in front for a
patient key and `R:` for a file name, as in `P:mrn:SYN-MRN-0001`, so that
the two kinds can't collide. It keeps the first 16 hexadecimal
characters and puts `P-` before those of a patient key and `R-` before those
of a file name. The IDs of the interpretations and variants start with their
report's pseudonym, as in `R-6947a2b0db4251c0:1`.

### Ontology versions

`metaData.resources` lists the release of each ontology. The HPO and MONDO
releases come from the `run.yaml` of `gentrex normalize`, and the zygosity
terms from the Genotype Ontology release of 2 February 2026. After a run of
`gentrex normalize` with `--no-hpo`, HPO isn't listed.

## Settings

`gentrex export phenopackets` has no settings.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was exported, and none has an error. | Nothing. |
| 1 | The run of `gentrex normalize` is missing or too old, some reports have no data or an error, or the run stopped with a traceback. The end of the output says which. | See below. |
| 2 | `--pseudonymize` was given, but `GENTREX_PSEUDONYM_KEY` is not set. | Add the key to `.env` ([Share Phenopackets](#share-phenopackets)) and run with `uv run --env-file .env`. |

If the run of `gentrex normalize` can't be exported, Gentrex stops before it
writes anything:

| Message | What to do |
| --- | --- |
| `results/normalize/latest/normalized.jsonl not found` | Run `gentrex normalize` first, or name a run of `gentrex normalize` with `--input`. |
| `run.yaml doesn't record the MONDO release, because it is from before gentrex normalize found diseases` | Download the [MONDO release](normalize.md#step-3-download-the-mondo-release) and run `gentrex normalize` again. |

While it exports, Gentrex prints a warning for each problem it works around:

- `skipped report-13.pdf, which has no data: APITimeoutError: Request timed out.`
  means `gentrex extract` got no data for the report. Run `gentrex extract`
  again for it, and then `gentrex normalize` and `gentrex export phenopackets`.
- `report-01.pdf, report-02.pdf give different dates of birth, so the
  Phenopacket leaves them out` means the reports of one patient disagree.
  Check the PDFs. The same goes for `different sexes`.

A report with an error from `gentrex extract` or `gentrex normalize` is still
exported, but it's listed among the failed files at the end.

If the HPO resource in `metaData` has the version `unknown`, the HPO index is
from before Gentrex recorded its release. Rebuild the
[HPO index](normalize.md#step-2-build-the-hpo-index), then run
`gentrex normalize` and `gentrex export phenopackets` again.
