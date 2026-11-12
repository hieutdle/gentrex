# Export report data into an OMOP database

`gentrex export omop` writes the report data into an OMOP CDM, the Common
Data Model of the OHDSI community. The CDM is a fixed set of tables, such as
PERSON and MEASUREMENT, that many hospitals fill with their EHR data. OHDSI's
tools, like ATLAS, select cohorts and run studies on these tables. With the
reports in the same CDM, one query can find the patients with a pathogenic
SCN1A variant along with their diagnoses and drugs from the EHR.

For example, a report with the variant `NM_001165963.4:c.4933C>T` in SCN1A,
pathogenic and heterozygous, becomes the rows below. Each row stores its
meaning as a concept, a numbered entry in OMOP's vocabularies.

| Table | Row |
| --- | --- |
| PROCEDURE_OCCURRENCE | The test, as the SNOMED concept Molecular genetic test. |
| MEASUREMENT | The variant, as the concept "SCN1A (sodium voltage-gated channel alpha subunit 1) gene variant measurement", with the value Present and the HGVS change as its source value. |
| MEASUREMENT | Its clinical significance, as the LOINC code 53037-8 with the answer Pathogenic. |
| MEASUREMENT | Its allelic state, as the LOINC code 53034-5 with the answer Heterozygous. |

The export reads `normalized.jsonl` from a run of `gentrex normalize` and
writes the rows into the PostgreSQL database that `GENTREX_OMOP_DATABASE_URL`
points to. Its run folder goes to `results/export/omop/`. A few hundred
reports take a few seconds.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex normalize` in `results/normalize/`.
- An OMOP CDM 5.4 or 5.5 database in PostgreSQL, with OHDSI's standardized
  vocabularies loaded. Step 1 explains how to get one.
- A machine approved for patient data, because the CDM will hold the records
  of every report.

The export writes only to PostgreSQL, because OHDSI's tools store dates in
SQLite as numbers and Gentrex writes them as text.

## Step 1: Get a CDM database

### Use your institution's CDM

Ask the team that runs the CDM, for example Mount Sinai's OMOP team, for three
things:

- A database user that may insert rows into the CDM tables and read the
  vocabulary tables.
- A schema in the same database for Gentrex's own two tables, which list the
  rows it wrote. A schema is a named group of tables inside a PostgreSQL
  database.
- A person map, a CSV file with the columns `patient_key` and `person_id` and
  one row per patient, as in `mrn:SYN-MRN-0001,1234567`. The `patient_key` is
  the key from [Link reports to patients](load.md#link-reports-to-patients),
  and only the team can match it to their persons.

Then go on to step 2.

### Create a CDM of your own

A CDM of your own holds only Gentrex's records, so Gentrex adds a person for
each patient. Start PostgreSQL in Docker
([Load report data into a database](load.md#postgresql)) and create a
database for the CDM in it:

```bash
docker exec gentrex-postgres createdb -U gentrex omop
```

Then download and run OHDSI's DDL for PostgreSQL, the SQL that creates the
CDM tables with their primary keys and indices. Release v5.4.3 is the latest
of CDM 5.4, the version that OHDSI's tools support most widely:

```bash
mkdir -p data/omop
for part in ddl primary_keys indices; do
  curl -f -L -o data/omop/$part.sql \
    https://raw.githubusercontent.com/OHDSI/CommonDataModel/v5.4.3/inst/ddl/5.4/postgresql/OMOPCDM_postgresql_5.4_$part.sql
done
for part in ddl primary_keys indices; do
  sed 's/@cdmDatabaseSchema/public/g' data/omop/$part.sql |
    docker exec -i gentrex-postgres psql -q -U gentrex -d omop -v ON_ERROR_STOP=1
done
```

`sed` puts `public`, PostgreSQL's default schema, in place of the placeholder
`@cdmDatabaseSchema`. That's also the schema that `export.omop.cdm_schema` in
settings.yaml uses by default. `ON_ERROR_STOP=1` makes psql stop at the first
error instead of running the rest of the file. The tables it created before
the error stay, so if you see an error, drop the database with
`docker exec gentrex-postgres dropdb -U gentrex omop` and start step 1 again.

The commands leave out OHDSI's optional constraints, which make the database
check every concept ID against the vocabulary.

Next, get the vocabularies from Athena, OHDSI's vocabulary server. Log in at
[athena.ohdsi.org](https://athena.ohdsi.org), open Download, and select at
least SNOMED, LOINC, OMOP Genomic, Gender and Type Concept. The last two
contain the concepts for sex and for where data came from, which OHDSI's
tools show. Athena sends you a link to a zip file of tab-separated files,
for example `CONCEPT.csv`. Unzip it into `data/omop/vocabulary/` and load
each file into the table of the same name:

```bash
for file in data/omop/vocabulary/*.csv; do
  table=$(basename "$file" .csv | tr '[:upper:]' '[:lower:]')
  docker exec -i gentrex-postgres psql -U gentrex -d omop -c \
    "COPY public.$table FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', HEADER, QUOTE E'\b')" < "$file"
done
```

`COPY` prints the number of rows it loaded, as in `COPY 1085621`. Large files,
such as `CONCEPT_ANCESTOR.csv`, take several minutes. `QUOTE E'\b'` is OHDSI's
usual setting, because Athena's files don't quote their text and concept
names can contain quotation marks.

## Step 2: Point Gentrex at the CDM

Set the address of the CDM's database in `.env`:

```
GENTREX_OMOP_DATABASE_URL=postgresql://gentrex:gentrex@127.0.0.1:5432/omop
```

It has the same form as the PostgreSQL addresses in
[Load report data into a database](load.md#step-2-point-gentrex-at-the-database).
For a CDM of your own, the settings under `export.omop` in settings.yaml fit
as they are. For your institution's CDM, set the schemas and the person map
that its team gave you, for example:

```yaml
export:
  omop:
    cdm_schema: cdm
    vocabulary_schema: vocab
    gentrex_schema: gentrex
    person_map: data/omop/person_map.csv
```

[Settings](#settings) explains each one.

## Step 3: Run

```bash
uv run --env-file .env --extra postgresql gentrex export omop
```

The first time, `--extra postgresql` installs psycopg, the driver that
Gentrex uses for PostgreSQL. The command reads the newest finished run of
`gentrex normalize`, in `results/normalize/latest`. To export another run:

```bash
uv run --env-file .env --extra postgresql gentrex export omop --input results/normalize/20261019-030000
```

You'll see one line per report, like `exported report-01.pdf`, and a total at
the end, as in `exported 300 of 300 reports in 4 s`.

## Check the result

The records go into the CDM. The run folder, for example
`results/export/omop/20261105-015324/`, contains two files:

| File | Contents |
| --- | --- |
| `run.yaml` | The command, the run of `gentrex normalize` that was read, and the settings. |
| `log.txt` | Everything the run printed. |

`results/export/omop/latest` points to the newest finished run.

Open the database with psql
([Open the database](load.md#open-the-database)) and add `-d omop`. This
query counts the patients with a pathogenic or likely pathogenic variant, per
gene:

```sql
SELECT gene.concept_name AS gene, count(DISTINCT variant.person_id) AS patients
FROM measurement variant
JOIN concept gene ON gene.concept_id = variant.measurement_concept_id
JOIN measurement class ON class.measurement_event_id = variant.measurement_id
  AND class.meas_event_field_concept_id = 1147138
JOIN concept answer ON answer.concept_id = class.value_as_concept_id
WHERE gene.vocabulary_id = 'OMOP Genomic'
  AND answer.vocabulary_id = 'LOINC'
  AND answer.concept_code IN ('LA6668-3', 'LA26332-9')
GROUP BY gene.concept_name
ORDER BY patients DESC, gene.concept_name;
```

`class` is the row of the variant's clinical significance. It points to the
variant's row through `measurement_event_id`, and
`meas_event_field_concept_id` 1147138 says that this ID is a
`measurement_id`. LA6668-3 and LA26332-9 are LOINC's answers Pathogenic and
Likely pathogenic.

To count the patients who have each clinical feature, by HPO term:

```sql
SELECT observation_source_value AS hpo_id, value_as_string AS term,
  count(DISTINCT person_id) AS patients
FROM observation
JOIN concept present ON present.concept_id = observation.value_as_concept_id
WHERE observation_source_value LIKE 'HP:%' AND present.concept_code = 'LA9633-4'
GROUP BY 1, 2
ORDER BY patients DESC;
```

LA9633-4 is LOINC's answer Present, so the query leaves out the features that
a report says the patient doesn't have.

## How it works

### Turn a report into rows

Each report gets one row for the test and, if the report names a specimen,
one row for the specimen. Every other row of the report points to the test's
row.

| Report data | Table | Concept | Value |
| --- | --- | --- | --- |
| The test | PROCEDURE_OCCURRENCE | SNOMED 405825005, Molecular genetic test | The test name as source value |
| The specimen | SPECIMEN | The SNOMED specimen concept of `specimen_type`, such as 258580003 for `whole_blood` | The accession number as `specimen_source_id` |
| A variant | MEASUREMENT | The OMOP Genomic concept of its gene, else LOINC 69548-6, Genetic variant assessment | Present, with the HGVS change as source value |
| Its classification | MEASUREMENT | LOINC 53037-8, Genetic variation clinical significance | The LOINC answer of the ACMG class |
| Its zygosity | MEASUREMENT | LOINC 53034-5, Allelic state | The LOINC answer of the zygosity |
| Its gene | MEASUREMENT | LOINC 48018-6, Gene studied | The approved symbol as text |
| Its protein change | MEASUREMENT | LOINC 48005-3, Amino acid change | `hgvs_p` as text |
| Its disease | MEASUREMENT or OBSERVATION | LOINC 81259-4, Associated phenotype | The MONDO ID, and the disease label as text |
| A clinical feature | OBSERVATION | 0 | Present or Absent, with the HPO ID as source value |

The rows of a variant's attributes point to the variant's row, so a query can
find the class or zygosity of each variant, like the first query in
[Check the result](#check-the-result).

Every row gets the collection date of the specimen or, if the report gives
none, the received date, the test start date or the report date. OMOP needs a
date on every row, so a report with none of these dates is left out.

### Find the concepts

Gentrex looks up each concept by its vocabulary and code, as in LOINC
53037-8, in the CDM's own tables, so the IDs match the vocabulary release that
the CDM holds. Only a few IDs are fixed, the same ones that OHDSI's own ETL
programs use. They are 32858 (NLP) for data that a program read from text,
8532 and 8507 for female and male, and the field concepts such as 1147138.

OMOP's rules put each concept into the table of its domain. A concept of the
Observation domain, for example, must go to OBSERVATION. Gentrex follows the
domain in the vocabulary, which is why the associated phenotype can end up in
either table.

OMOP Genomic, OHDSI's vocabulary of genes and variants, has one concept per
gene, named like "SCN1A (sodium voltage-gated channel alpha subunit 1) gene
variant measurement". Gentrex finds it by the approved symbol from
`gentrex normalize`. OMOP Genomic also has concepts for single variants, but
matching an HGVS change to one of them takes
[KOIOS](https://github.com/OHDSI/Koios), OHDSI's tool for this. A variant
therefore gets its gene's concept, with the HGVS change as source value.

A code that the vocabulary lacks gets concept 0, OMOP's concept for "no
matching concept", and keeps its source value.

### What OMOP can't hold

- OMOP has no HPO vocabulary, so the clinical features get concept 0. Their
  HPO ID is in `observation_source_value`, their HPO label in
  `value_as_string`, and the feature as printed in `value_source_value`.
  Features that a report is unsure of are left out.
- There's no MONDO vocabulary in OMOP either, and the disease keeps its MONDO
  ID as text.
- The source value columns hold at most 50 characters, and `value_as_string`
  60. Longer text is cut off, for example a long HGVS change. The whole record
  stays in `normalized.jsonl` and in the tables of `gentrex load`.
- The parental origin, the mode of inheritance, whether a variant is a
  secondary finding, its copy number, the karyotype and the genome build have
  no row, because LOINC codes for them couldn't be checked.

[`gentrex export omop-extended`](export-omop-extended.md) keeps all of this in
extension tables, outside the CDM's schema.

### Create or map persons

With a person map, each report gets the `person_id` that the map gives its
patient. A patient who isn't in the map, or whose person isn't in the CDM, is
left out, so no result lands on the wrong person.

Without a person map, Gentrex adds one PERSON for each patient, with the sex
and date of birth that the patient's reports agree on. OHDSI drops persons
without a year of birth, so a patient whose reports give no date of birth, or
different ones, is left out. Each person also gets one OBSERVATION_PERIOD, the
time in which the CDM has data on them, from their first to their last row.
Later runs reuse the persons that Gentrex created.

Without a person map, Gentrex also refuses a CDM that already holds persons it
didn't create, because new persons there would duplicate real patients.

### Export a run again

Each report replaces the rows that an earlier export wrote for its file, in
one transaction. Gentrex finds them in `omop_rows` in `gentrex_schema`, which
lists the table and ID of every row it wrote. Rows that other programs wrote
stay as they are, and so do the rows of other files.

Each new row gets the next free ID of its table. Don't run another program
that writes into the same tables at the same time, because the two could take
the same IDs. If an institutional CDM is rebuilt from the EHR, run the export
again afterwards.

## Settings

The settings are under `export.omop` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml).
To change one, name it in a
[settings file of your own](runs-and-results.md#change-the-settings):

| Setting | Default | What it does |
| --- | --- | --- |
| `cdm_schema` | `null` | The schema of the CDM tables. `null` is the database's default schema, `public`. |
| `vocabulary_schema` | `null` | The schema of the vocabulary tables. `null` is the same as `cdm_schema`, where most CDMs keep them. |
| `gentrex_schema` | `gentrex` | The schema of Gentrex's tables `omop_rows` and `omop_persons`. Gentrex creates it if it doesn't exist. It must differ from `cdm_schema`, so that the CDM schema holds only CDM tables. |
| `person_map` | `null` | The CSV file with the `person_id` of each patient. `null` makes Gentrex add a person for each patient. |
| `extension_schema` | `omop_extension` | Used only by [`gentrex export omop-extended`](export-omop-extended.md#settings). |

The database address is set in `.env` as `GENTREX_OMOP_DATABASE_URL`
(step 2).

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was exported, and none has an error. | Nothing. |
| 1 | The input or a table is missing, the database can't be used, some reports were left out or have an error, or the run stopped with a traceback. The end of the output says which. | See below. |
| 2 | `GENTREX_OMOP_DATABASE_URL` is not set. | Do step 2. |

If the CDM can't take the export, Gentrex stops before it writes anything:

| Message | What to do |
| --- | --- |
| `results/normalize/latest/normalized.jsonl not found` | Run `gentrex normalize` first, or name a run with `--input`. |
| `can't connect to the database: ...` | Check that PostgreSQL is running and that `GENTREX_OMOP_DATABASE_URL` in `.env` has the right address, user and password. |
| `the OMOP export writes only to PostgreSQL` | Use a CDM in PostgreSQL (step 1). |
| `the database has no table person` | The address points to a database without CDM tables, or `cdm_schema` is the wrong schema. Create the CDM as in step 1, or correct the setting. |
| `the CDM holds ... persons that Gentrex didn't create` | The CDM belongs to someone else. Set `person_map` to the file that its team gave you (step 2). |
| `export.omop.gentrex_schema must differ from cdm_schema` | Choose another schema for Gentrex's tables. |
| `can't create Gentrex's tables: permission denied for database` | The database user may not create `gentrex_schema`. Ask the CDM's team to create it, or to grant the right. |
| `... lacks the columns patient_key, person_id` | The person map needs these two columns, with a header line. |
| `... has a person_id that is not a number` | Every `person_id` in the person map must be a whole number. |

While it exports, Gentrex prints a warning for each report it leaves out:

- `left out report-07.pdf: the person map has no mrn:SYN-MRN-0007` means the
  patient isn't in the person map. Ask the CDM's team to add them.
- `left out report-07.pdf: OMOP needs a person's year of birth, and the
  reports give none` means Gentrex can't create the person. Check the date of
  birth in the report.
- `left out report-07.pdf: the CDM has no person 1234567` means the person
  map points to a person that the CDM doesn't have. Ask the CDM's team to
  correct the map.
- `left out report-07.pdf, which has no date` means the report gives no
  collection, received, start or report date.
- `left out report-13.pdf, which has no data` means `gentrex extract` got no
  data for the report. Run `gentrex extract` again for it, and then
  `gentrex normalize` and the export.

`failed report-07.pdf: DataError: ...` means that the database refused the
report's rows. Each report is written in a transaction of its own, so nothing
of that report is in the CDM, and the export goes on with the next one. The
text after the file name says what the database refused.

The warning `the vocabulary has no standard concept for LOINC LA6703-8, so
their rows have concept 0` lists the codes that the CDM's vocabulary lacks.
Load the missing vocabularies from Athena as in step 1, and run the export
again.

A report with an error from `gentrex extract` or `gentrex normalize` is still
exported, but it's listed among the failed files at the end.
