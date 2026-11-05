# Database tables

`gentrex load` stores each run of `gentrex normalize` in eight tables, which
are the same in SQLite, PostgreSQL and MySQL. They're defined in
[`tables.py`](../../src/gentrex/load/tables.py).
[Load report data into a database](load.md#check-the-result) shows how to
open the database.

## How the tables link

```
reports                       file
├── variants                  file, variant_number
└── patient_phenotypes        file, phenotype_number
    └── phenotype_candidates  file, phenotype_number, rank

hpo_terms                     hpo_id
hpo_ancestors                 hpo_id, ancestor_id
hpo_release                   sha256
schema_version                version
```

Each table is shown with its primary key. An indented table belongs to the
one above it and repeats its key, so every variant row has the `file` of its
report. When Gentrex loads a report again, it deletes the old report, and the
database deletes its variants, features and candidates with it.

The HPO tables and `schema_version` aren't linked to the others. Queries join
the HPO tables on `hpo_id`, as in
[Find a term together with the terms under it](load.md#find-a-term-together-with-the-terms-under-it).
A feature matched to a term that is missing from the HPO release still loads,
with a warning.

## Column types

Each database stores the six column types in its own way:

| Type | SQLite | PostgreSQL | MySQL |
| --- | --- | --- | --- |
| text | `TEXT` | `TEXT` | `TEXT` |
| integer | `INTEGER` | `INTEGER` | `INTEGER` |
| boolean | `BOOLEAN`, stored as 1 or 0 | `BOOLEAN` | `BOOL`, stored as 1 or 0 |
| date | `DATE`, stored as text like `1984-06-29` | `DATE` | `DATE` |
| timestamp | `DATETIME`, stored as text in UTC | `TIMESTAMP WITH TIME ZONE` | `DATETIME`, in UTC |
| JSON | `JSON`, stored as text | `JSONB` | `JSON` |

Key columns are `VARCHAR`, text with a maximum length, because MySQL can't
use text of unlimited length in a key. The limits are 255 characters for
`file`, 32 for HPO IDs and 64 for `sha256`. On MySQL, `file` and the HPO ID
columns are case-sensitive and the other text columns aren't
([Supported databases](load.md#supported-databases)).

To write a query that runs on all three databases:

- Use a boolean column on its own in a condition, as in `WHERE p.present` or
  `WHERE NOT p.models_agree`.
- Write dates as `'YYYY-MM-DD'`, as in
  `WHERE r.date_of_birth >= '2000-01-01'`. SQLite stores dates as text in
  this form, so the comparison works there too.
- Prefix `rank` with its table, as in `c.rank`, because MySQL reserves the
  word.

## Columns

Columns ending in `_raw` contain the text as the report printed it. The
column with the same name minus `_raw`, like `date_of_birth` next to
`date_of_birth_raw`, contains the standard value from `gentrex normalize` or
the category that `gentrex extract` picked. The categories listed are those of
the default [`schema.yaml`](../../src/gentrex/defaults/schema.yaml). If
`gentrex normalize` failed on a report, its standard values are null and
`error` says why.

In the Null column, yes means that the value can be missing.

### reports

One row per report, except reports that got no data from `gentrex extract`.
The key is `file`. Dates are null when the report gives none, or when
`gentrex normalize` can't read the printed one.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `file` | text, up to 255 characters | no | The PDF's file name, like `report-01.pdf`. |
| `patient_key` | text | no | Identifies the patient across reports, for example `mrn:SYN-MRN-0001`. [Link reports to patients](load.md#link-reports-to-patients) explains how it is built. |
| `pages` | JSON | no | Pages that `gentrex extract` sent to the model, like `[1, 2]`. |
| `error` | text | yes | Error from `gentrex extract` or `gentrex normalize`, if any. [Normalize report data](normalize.md#when-something-goes-wrong) explains the errors. |
| `mrn` | text | yes | Medical record number, as printed. |
| `submitter_patient_id` | text | yes | Patient ID from the ordering clinic or submitter, as printed. |
| `lab_accession_number` | text | yes | Laboratory accession or order number, as printed. |
| `date_of_birth` | date | yes | Date of birth. |
| `date_of_birth_raw` | text | yes | Date of birth as printed, like `29-JUN-1984`. |
| `sex` | text | yes | Sex as printed, like `Female` or `M`. `gentrex normalize` doesn't standardize it, so a query must match `F` and `Female` separately. |
| `specimen_type` | text | yes | Specimen category, one of `buccal_swab`, `whole_blood`, `saliva`, `bone_marrow`, `amniotic_fluid`, `chorionic_villus`, `fibroblast` or `tissue`. Null when no category fits or more than one does. |
| `specimen_type_raw` | text | yes | Specimen as printed, for example `Blood in EDTA`. |
| `collection_date` | date | yes | Date the specimen was collected. |
| `collection_date_raw` | text | yes | Collection date as printed. |
| `received_date` | date | yes | Date the laboratory received the specimen. |
| `received_date_raw` | text | yes | Received date as printed. |
| `test_name` | text | yes | Name of the test, panel or assay, like `Inherited Arrhythmia Panel`. |
| `test_type` | text | yes | Kind of test, one of `panel`, `exome`, `genome`, `single_gene`, `targeted_variant`, `microarray` or `other`. |
| `test_started_date` | date | yes | Date the laboratory started the analysis. |
| `test_started_date_raw` | text | yes | Start date as printed. |
| `report_date` | date | yes | Date the report was finalized. |
| `report_date_raw` | text | yes | Report date as printed. |
| `overall_result` | text | yes | Result category, one of `positive`, `negative`, `uncertain`, `carrier` or `inconclusive`. Null when neither the result statement nor the variant classifications give one. |
| `overall_result_basis` | text | yes | `wording` if `overall_result` comes from the result statement, `variants` if it comes from the variant classifications. |
| `overall_result_conflict` | boolean | yes | True when the result statement and the variant classifications disagree. Check these reports against the PDF. |
| `overall_result_raw` | text | yes | Overall result statement, copied verbatim. |
| `clinical_indication` | text | yes | Why the test was ordered, as printed, like `Diagnostic evaluation`. |
| `lab_name` | text | yes | Testing laboratory. |
| `record` | JSON | no | The full line of `normalized.jsonl`, including fields without a column of their own, such as one you added to `schema.yaml`. [See what each table holds](load.md#see-what-each-table-holds) shows how to query it. |
| `normalize_run` | text | no | Full path of the run folder of `gentrex normalize` that the report came from. |
| `loaded_at` | timestamp | no | When Gentrex loaded the report, in UTC. |

### variants

One row per reported variant. The key is `file` and `variant_number`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `file` | text, up to 255 characters | no | The report that the variant belongs to. |
| `variant_number` | integer | no | Position of the variant in the report's list, starting at 1. |
| `page` | integer | yes | Page that the variant is reported on, or the first such page. |
| `gene_symbol` | text | yes | Approved HGNC symbol, or null when the printed symbol matches no gene or more than one. |
| `gene_symbol_raw` | text | yes | Gene symbol as printed, like `BRCA1`. |
| `hgnc_id` | text | yes | HGNC ID, like `HGNC:1100`. |
| `gene_status` | text | yes | How the printed symbol matched, one of `approved`, `alias`, `previous`, `alias_or_previous`, `ambiguous`, `unmapped` or `missing`. [Normalize report data](normalize.md#check-the-result) explains the values. |
| `transcript` | text | yes | Reference transcript, like `NM_007294.4`. |
| `hgvs_c` | text | yes | Coding DNA change, copied verbatim, like `c.5266dupC`. |
| `hgvs_p` | text | yes | Protein change, copied verbatim, like `p.(Gln1756Profs*74)`. |
| `dna_change_raw` | text | yes | DNA change when the report gives no c. notation, for example `NC_012920.1:m.3243A>G` or `Deletion of exons 45-50`. |
| `chromosomal_position` | text | yes | Genomic position or range as printed, like `chr17:43057062`. The genome build isn't extracted, so check the reports before you compare positions across laboratories. |
| `classification` | text | yes | Classification, one of `pathogenic`, `likely_pathogenic`, `uncertain_significance`, `likely_benign`, `benign` or `other`. |
| `classification_raw` | text | yes | Classification as printed, like `Pathogenic (Class 5)` or `VUS`. |
| `zygosity` | text | yes | Zygosity, one of `heterozygous`, `homozygous`, `hemizygous`, `heteroplasmic`, `homoplasmic` or `other`. |
| `zygosity_raw` | text | yes | Zygosity or heteroplasmy as printed, for example `Heteroplasmic (28%)`. |
| `parental_origin` | text | yes | Origin of the variant, one of `de_novo`, `maternal`, `paternal`, `both_parents` or `other`. |
| `parental_origin_raw` | text | yes | Origin as printed, like `Maternally inherited`. |
| `associated_phenotype` | text | yes | Disease or condition that the report links to the variant, like `Cystic fibrosis`. |
| `disease_id` | text | yes | MONDO ID of that disease, from `gentrex normalize`, like `MONDO:0009061`. Null when the name matches no MONDO disease, or several. |
| `disease_label` | text | yes | MONDO label of the disease, like `cystic fibrosis`. |
| `disease_status` | text | yes | How the name matched, one of `label`, `synonym`, `ambiguous`, `unmapped` or `missing`. [Normalize report data](normalize.md#check-the-result) explains the values. |
| `mode_of_inheritance` | text | yes | Inheritance pattern of the condition, one of `autosomal_dominant`, `autosomal_recessive`, `x_linked_dominant`, `x_linked_recessive`, `x_linked`, `mitochondrial` or `other`. `x_linked` means X-linked without dominant or recessive. |
| `mode_of_inheritance_raw` | text | yes | Inheritance pattern as printed, like `Autosomal recessive`. |
| `is_secondary_finding` | boolean | yes | True for a secondary or incidental finding, false for a primary finding, and null when the report doesn't say. |
| `variant_type_raw` | text | yes | Variant type as printed, for example `Missense` or `Frameshift deletion`. |

### patient_phenotypes

One row per clinical feature of a report. The key is `file` and
`phenotype_number`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `file` | text, up to 255 characters | no | The report that the feature belongs to. |
| `phenotype_number` | integer | no | Position of the feature in the report's list, starting at 1. |
| `text` | text | no | The feature, copied verbatim, like `Global developmental delay`. |
| `present` | boolean | yes | True if the patient has the feature, false if the report rules it out, and null if the report is unsure, as in `possible seizure`. Filter on `present` when you count the patients with a feature, or "no hearing impairment" counts as hearing impairment. |
| `hpo_id` | text, up to 32 characters | yes | Matched HPO term, like `HP:0001263`. It is the first candidate, and null if `gentrex normalize` ran with `--no-hpo`. |
| `hpo_label` | text | yes | Label of the matched term. |
| `models_agree` | boolean | yes | True if all the models rank the same term first. False marks a match worth checking, because these are wrong more often. Null with a single model, or with `--no-hpo`. |

### phenotype_candidates

The candidate HPO terms of each feature, best first. `normalize.hpo.top_k` in
settings.yaml sets how many, 5 by default. The key is `file`,
`phenotype_number` and `rank`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `file` | text, up to 255 characters | no | The report. |
| `phenotype_number` | integer | no | The feature that the candidate belongs to. |
| `rank` | integer | no | 1 for the match, then 2 to 5 for the alternatives. |
| `hpo_id` | text, up to 32 characters | no | Candidate term, like `HP:0012758`. |
| `hpo_label` | text | no | Label of the candidate term. |
| `models` | JSON | no | Per model, the term's closest label or synonym (`name`) and its cosine similarity to the feature (`similarity`). |

For example:

```json
{
  "cambridgeltl/SapBERT-from-PubMedBERT-fulltext": {"name": "Tumours of the breast", "similarity": 0.8094},
  "google/embeddinggemma-2": {"name": "Breast tumor", "similarity": 0.9627}
}
```

### hpo_terms

Every current term of the HPO release, meaning every labelled class that
isn't deprecated. The HPO index of `gentrex normalize` contains the same
terms. The key is `hpo_id`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `hpo_id` | text, up to 32 characters | no | HPO ID, like `HP:0001250`. |
| `hpo_label` | text | no | Label, like `Seizure`. |

### hpo_ancestors

One row for each term and each of its ancestors, including the term itself.
[Find a term together with the terms under it](load.md#find-a-term-together-with-the-terms-under-it)
lists the 8 rows of HP:0002384. The key is `hpo_id` and `ancestor_id`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `hpo_id` | text, up to 32 characters | no | HPO term. |
| `ancestor_id` | text, up to 32 characters | no | The term itself, or any term above it in the `is_a` hierarchy. |

### hpo_release

A single row for the HPO release in `hpo_terms` and `hpo_ancestors`. Loading
a different release replaces all three tables. The key is `sha256`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `sha256` | text, up to 64 characters | no | Checksum of the release file, which the run's `run.yaml` also lists as `hpo_sha256`. |
| `loaded_at` | timestamp | no | When the release was loaded, in UTC. |

### schema_version

A single row with the version of the tables, which a new version of Gentrex
raises when a column changes. `gentrex load` never changes a table that
exists, so it stops on a database whose tables have another version.
[Load a run again](load.md#load-a-run-again) says what to do then. A database
from before `schema_version` existed counts as version 1. The key is
`version`.

| Column | Type | Null | Holds |
| --- | --- | --- | --- |
| `version` | integer | no | The version of the tables, which is 2 for this Gentrex. |

## SQL that creates the tables

`gentrex load` creates the tables in a new database at the start of a run. To
print the `CREATE TABLE` statements for one database without connecting to
it:

```bash
uv run python -c "
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from gentrex.load import tables
for table in tables.metadata.sorted_tables:
    print(CreateTable(table).compile(dialect=postgresql.dialect()))
"
```

For SQLite or MySQL, replace both `postgresql` with `sqlite` or `mysql`.
