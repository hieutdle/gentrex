# Stage 6: Export report data as Phenopackets

Stage 6 writes the records of a stage 4 run as Phenopackets, one JSON file per
patient. A Phenopacket is the format of the Global Alliance for Genomics and
Health (GA4GH) for one patient's clinical features and genetic findings. It is
published as ISO standard 4454:2022, and rare-disease tools such as Exomiser
and LIRICAL read it. Other centers can import your results from Phenopackets
without learning Gentrex's own format.

For example, a report on a girl with seizures and a pathogenic SCN1A variant
becomes a Phenopacket with these parts:

- The HPO term HP:0001250, Seizure.
- The variant `NM_001165963.4:c.4933C>T` in SCN1A, heterozygous and
  pathogenic.
- The diagnosis MONDO:0100135, Dravet syndrome, which stage 4 found for the
  variant's `associated_phenotype`.

Stage 6 reads `normalized.jsonl` and `run.yaml` from a stage 4 run and writes
to `results/export/`. It needs no model server, no GPU and no database, and it
exports a few hundred reports in a second.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 4 run, in `results/normalize/`, made with the MONDO release
  of [stage 4, step 3](stage4.md#step-3-download-the-mondo-release). Stage 6
  stops on a stage 4 run from before Gentrex looked up diseases.

## Step 1: Run

```bash
uv run gentrex stage6
```

This reads the newest finished stage 4 run, `results/normalize/latest`, and
writes a new folder named after the time the run started, such as
`results/export/20261104-203946/`. To export another stage 4 run:

```bash
uv run gentrex stage6 --input results/normalize/20261019-030000
```

Gentrex prints one line per Phenopacket, such as
`wrote mrn_SYN-MRN-0001.json from report-01.pdf, report-02.pdf`. The last line
counts the Phenopackets and the reports they came from, as in
`wrote 2 Phenopackets from 3 of 4 reports in 0 s`.

## Check the result

The run folder holds:

| File | Contents |
| --- | --- |
| `phenopackets/` | One JSON file per patient, named after the patient's key, such as `mrn_SYN-MRN-0001.json`. |
| `run.yaml` | The command, the stage 4 run that was read, and the MONDO and HPO releases that stage 4 used. |
| `log.txt` | What Gentrex printed during the run. |

`results/export/latest` points to the newest finished run.
[Runs and results](../README.md#runs-and-results) explains run folders and
`latest`.

The Phenopackets hold patient identifiers. Each one's `id` is the patient's
key, such as `mrn:SYN-MRN-0001`, so it contains the MRN, and the subject
holds the date of birth. Before you share Phenopackets with anyone not
approved to see patient data, replace the IDs and remove the dates, as your
privacy office requires.

Shortened, a Phenopacket looks like this:

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

The Phenopacket's fields come from the stage 4 record:

| Phenopacket field | From |
| --- | --- |
| `subject.dateOfBirth`, `subject.sex` | `normalized.date_of_birth`, and `data.sex` as printed, such as `F` or `Female`. |
| `phenotypicFeatures` | The HPO term of each clinical feature. `excluded` is `true` for a feature that the patient doesn't have, with `present` set to `false`. |
| `interpretations` | One per report and disease. `summary` is the report's `overall_result_raw`. |
| `progressStatus` | `UNSOLVED` for a negative report, `COMPLETED` for any other result, and `UNKNOWN_PROGRESS` if `overall_result` is `null`. |
| `diagnosis.disease` | The variant's `disease_id` and `disease_label` from stage 4. |
| `interpretationStatus` | `CANDIDATE` for a primary finding, `UNKNOWN_STATUS` for a secondary finding, and `REJECTED` for a benign or likely benign variant. |
| `acmgPathogenicityClassification` | `classification`, in capitals. `other` has no ACMG class and is left out. |
| `geneContext` | `hgnc_id` and `gene_symbol`. |
| `expressions` | `transcript` and `hgvs_c`, as one HGVS expression. |
| `allelicState` | `zygosity`, as a term of the Genotype Ontology (GENO). |
| `label` | The gene symbol, `hgvs_c` or `dna_change_raw`, and `hgvs_p`. |

To check that every file follows the Phenopacket schema, parse each one with
GA4GH's Python package:

```bash
uv run --with phenopackets python -c "
import pathlib
from google.protobuf import json_format
from phenopackets import Phenopacket
paths = sorted(pathlib.Path('results/export/latest/phenopackets').glob('*.json'))
for path in paths:
    json_format.Parse(path.read_text(), Phenopacket())
print(len(paths), 'files follow the schema')
"
```

The package stops with an error that names the field if a file breaks the
schema. Gentrex's tests run this check on every change.

## How it works

### One Phenopacket per patient

A Phenopacket describes one patient. So the reports of one patient, those
with the same `patient_key` as in
[stage 5](stage5.md#link-reports-to-patients), make one Phenopacket, and each
report adds its own interpretations. A report without data, from a failed
stage 3 request, adds nothing, and stage 6 lists it among the failed files.

The patient's date of birth and sex are kept only when all reports that give
one agree. Suppose stage 3 misread the date of birth on one of two reports.
Neither date then goes into the Phenopacket, because Gentrex can't tell which
one is right. The log names the reports, so that you can check the PDFs.

Each HPO term appears once. A term is excluded only if no report of the
patient finds the feature present. Features that a report is unsure of, with
`present` set to `null`, are left out, because a Phenopacket has no value for
them. If stage 4 ran with `--no-hpo`, the Phenopacket has no features.

### Diagnoses

In a Phenopacket, each variant belongs to a diagnosis. Stage 6 groups the
variants of a report by their MONDO disease, and makes one interpretation per
disease. A report with a pathogenic SCN1A variant for Dravet syndrome and a
secondary BRCA2 finding for hereditary breast and ovarian cancer gets two.

A diagnosis needs a disease. A variant whose `associated_phenotype` found no
MONDO disease in stage 4 goes under MONDO:0000001, disease, the root term of
MONDO, so that it isn't lost. A report without variants, such as a negative
one, gets one interpretation without a diagnosis.

Stage 6 doesn't decide whether a variant causes the patient's disease, or
whether a report solves the case. So a positive report is `COMPLETED`, not
`SOLVED`, and a primary finding is a `CANDIDATE`, not `CAUSATIVE`. The
laboratory's own assessment is in `acmgPathogenicityClassification` and in the
`summary`.

### Variants

An HGVS expression needs a reference sequence. `hgvs_c` becomes an expression
when it starts with one, such as `NM_000059.4:c.5946del`, or when the report
names the `transcript`. The protein change goes only into the `label`,
because reports rarely print the protein's reference sequence. A change
without a c. notation, such as a mitochondrial change or a deletion of whole
exons, goes into the `label` as printed, in `dna_change_raw`.

### Ontology versions

`metaData.resources` names the release of each ontology that the terms come
from. The HPO and MONDO releases are the ones in the `run.yaml` of the stage 4
run. The Genotype Ontology terms for zygosity come from its release of 2
February 2026. A stage 4 run with `--no-hpo` uses no HPO terms, so the
Phenopackets then don't list HPO.

## Settings

Stage 6 has no settings.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was exported, and none has an error. | Nothing. |
| 1 | The stage 4 run is missing or too old, some reports have no data or an error, or the run stopped with a traceback. The end of the output says which. | See below. |

If the stage 4 run can't be exported, stage 6 stops before it writes anything:

| Message | What to do |
| --- | --- |
| `results/normalize/latest/normalized.jsonl not found` | Run stage 4 first, or name a stage 4 run with `--input`. |
| `run.yaml doesn't record the MONDO release, because it is from before stage 4 found diseases` | Download the MONDO release as in [stage 4, step 3](stage4.md#step-3-download-the-mondo-release), and run stage 4 again. |

While it exports, stage 6 prints a warning for each problem it works around:

- `skipped report-13.pdf, which has no data: APITimeoutError: Request timed out.`
  means that stage 3 got no data for the report. Run stage 3 again for it,
  and then stages 4 and 6.
- `report-01.pdf, report-02.pdf give different dates of birth, so the
  Phenopacket leaves them out` means that the reports of one patient disagree.
  Check the PDFs. The same goes for `different sexes`.

A report with an error from stage 3 or 4 is still exported, but it is listed
among the failed files at the end, as in stages 3 to 5.

If the HPO resource in `metaData` has the version `unknown`, the HPO index is
from before Gentrex recorded its release. Build the index again as in
[stage 4, step 2](stage4.md#step-2-build-the-hpo-index), and run stages 4 and
6 again.
