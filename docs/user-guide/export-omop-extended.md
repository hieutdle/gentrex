# Export report data into an OMOP database, with extension tables

`gentrex export omop-extended` writes the same rows into an OMOP CDM database
as [`gentrex export omop`](export-omop.md) and fills four extension tables
with what the CDM can't hold. These tables keep each value at full length and
add the fields that OMOP has no place for, like a variant's parental origin,
its mode of inheritance and the HPO candidates of a clinical feature.

For example, the variant "Deletion of exons 1 to 26 of SCN1A, including the
promoter region" is cut to its first 50 characters in the source value of its
MEASUREMENT row. Its row in `genomic_variant` has the whole text, next to the
variant's parental origin `de_novo`.

The extension tables go into a schema of their own, `omop_extension` by
default. The CDM's schema keeps only its standard tables, so OHDSI's tools
and other programs that use the CDM see no difference. Each extension row
points to the CDM row it extends.

## Before you start

You need the same as for
[Export report data into an OMOP database](export-omop.md#before-you-start).
In an institutional CDM, the database user also needs the right to create the
extension schema, unless the CDM's team creates it for you.

## Step 1: Run

Get a CDM and point Gentrex at it with steps 1 and 2 of
[Export report data into an OMOP database](export-omop.md#step-1-get-a-cdm-database).
Then run:

```bash
uv run --env-file .env --extra postgresql gentrex export omop-extended
```

It prints the same lines as `gentrex export omop` and writes its run folder
to `results/export/omop-extended/`.

Use only one of the two commands on a CDM. Both replace the same CDM rows,
but `gentrex export omop` leaves the extension rows of an earlier extended
run in place, pointing to rows that no longer exist.

## Check the result

The four tables are in the schema set by `export.omop.extension_schema` in
settings.yaml:

| Table | One row per | Extends |
| --- | --- | --- |
| `genomic_test` | Report | The test's row, usually in PROCEDURE_OCCURRENCE |
| `genomic_variant` | Variant | The variant's row in MEASUREMENT |
| `phenotype_feature` | Clinical feature that the patient has or doesn't have | The feature's row in OBSERVATION |
| `phenotype_candidate` | Candidate HPO term of a clinical feature | The feature's row in OBSERVATION |

Every table has these columns:

| Column | Holds |
| --- | --- |
| `cdm_table` | The CDM table of the row it extends, like `measurement`. |
| `cdm_row_id` | The ID of that row, for example its `measurement_id`. |
| `file` | The PDF that the row comes from. |
| `person_id` | The person, as in the CDM row. |

The other columns are named after the fields of `gentrex normalize`, like the
columns of `gentrex load` in [Database tables](database-tables.md).
`genomic_test` has the test name and type, the overall result and its
wording, the karyotype, the clinical indication, the laboratory, the
accession number and the genome build.
`genomic_variant` has every field of a variant, with the gene's HGNC ID and
the MONDO disease. `phenotype_feature` has the feature as printed, `present`,
its HPO term and `models_agree`, and `phenotype_candidate` lists the
candidates with their `rank`.

To list the de novo pathogenic variants with their HGVS change:

```sql
SELECT v.gene_symbol, v.hgvs_c, count(DISTINCT m.person_id) AS patients
FROM omop_extension.genomic_variant v
JOIN measurement m ON v.cdm_table = 'measurement'
  AND m.measurement_id = v.cdm_row_id
WHERE v.parental_origin = 'de_novo' AND v.classification = 'pathogenic'
GROUP BY v.gene_symbol, v.hgvs_c
ORDER BY patients DESC;
```

## How it works

Gentrex builds the CDM rows exactly as
[`gentrex export omop`](export-omop.md#how-it-works) does. Then it adds a row
to the matching extension table for each test, variant and clinical feature.
Clinical features that a report is unsure of have no CDM row, so they get no
extension row either.

When you export a file again, its extension rows are replaced together with
its CDM rows, in the same transaction.

## Settings

The command uses the
[settings of `gentrex export omop`](export-omop.md#settings) and one more
under `export.omop` in settings.yaml:

| Setting | Default | What it does |
| --- | --- | --- |
| `extension_schema` | `omop_extension` | The schema of the extension tables. Gentrex creates it if it doesn't exist. It must differ from `cdm_schema`. |

## When something goes wrong

The exit codes and messages are those of
[`gentrex export omop`](export-omop.md#when-something-goes-wrong), and the
extension schema adds these:

| Message | What to do |
| --- | --- |
| `export.omop.extension_schema must differ from cdm_schema` | Choose another schema for the extension tables. |
| `can't create Gentrex's tables: permission denied for database` | The database user may not create the extension schema. Ask the CDM's team to create it, or to grant the right. |

`failed report-01.pdf: ProgrammingError: ... column "karyotype" of relation
"genomic_test" does not exist` means that an older version of Gentrex created
the extension tables, with fewer columns. Gentrex never changes a table that
exists, so delete the four tables in psql
([Check the result](export-omop.md#check-the-result) shows how to open it):

```sql
DROP TABLE omop_extension.genomic_test, omop_extension.genomic_variant,
  omop_extension.phenotype_feature, omop_extension.phenotype_candidate;
```

If you changed `export.omop.extension_schema`, write its schema in place of
`omop_extension`. Then run `gentrex export omop-extended` again for each run
of `gentrex normalize` that you exported.
