# Export report data into an OMOP database, with extension tables

`gentrex export omop-extended` writes the same rows into an OMOP CDM database
as [`gentrex export omop`](export-omop.md), and also fills four extension
tables with what the CDM's tables can't hold. These tables keep each value at
full length, and they keep the fields that OMOP has no place for. Examples
are the parental origin of a variant, its mode of inheritance, and the HPO
candidates of a clinical feature.

For example, the variant "Deletion of exons 1 to 26 of SCN1A, including the
promoter region" is cut to its first 50 characters in the source value of its
MEASUREMENT row. Its row in `genomic_variant` holds the whole text, next to
the variant's parental origin `de_novo`.

The extension tables go into their own schema, `omop_extension` by default,
outside the CDM's schema. The CDM's schema then holds only standard tables,
so OHDSI's tools and the CDM's other programs see no difference. Each row of
an extension table names the CDM row it extends, so that a query can join the
two.

## Before you start

You need the same as for
[Export report data into an OMOP database](export-omop.md#before-you-start).
In an institutional CDM, the database user also needs the right to create the
extension schema, or the CDM's team creates it for you.

## Step 1: Run

Get a CDM and point Gentrex at it, as in steps 1 and 2 of
[Export report data into an OMOP database](export-omop.md#step-1-get-a-cdm-database).
Then run:

```bash
uv run --env-file .env --extra postgresql gentrex export omop-extended
```

The command works like `gentrex export omop`, and it prints the same lines.
It writes its run folder to `results/export/omop-extended/`. Use one of the
two commands for a CDM. Both replace the same CDM rows, but
`gentrex export omop` leaves the extension rows of an earlier extended run in
place, pointing to rows that no longer exist.

## Check the result

The four tables are in the schema that `export.omop.extension_schema` in
settings.yaml names:

| Table | One row per | Extends |
| --- | --- | --- |
| `genomic_test` | Report | The test's row, usually in PROCEDURE_OCCURRENCE |
| `genomic_variant` | Variant | The variant's row in MEASUREMENT |
| `phenotype_feature` | Clinical feature that the patient has or doesn't have | The feature's row in OBSERVATION |
| `phenotype_candidate` | Candidate HPO term of a clinical feature | The feature's row in OBSERVATION |

Every table has these columns:

| Column | Holds |
| --- | --- |
| `cdm_table` | The CDM table of the row it extends, such as `measurement`. |
| `cdm_row_id` | The ID of that row, such as its `measurement_id`. |
| `file` | The PDF that the row comes from. |
| `person_id` | The person, as in the CDM row. |

The other columns have the names of the fields of `gentrex normalize`, which
[Database tables](database-tables.md) describes for the tables of
`gentrex load`. `genomic_test` holds the test name and type, the overall
result and its wording, the clinical indication, the laboratory and the
accession number. `genomic_variant` holds every field of a variant, with the
gene's HGNC ID and the MONDO disease. `phenotype_feature` holds the feature
as printed, `present`, its HPO term and `models_agree`, and
`phenotype_candidate` holds the candidates with their `rank`.

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
[`gentrex export omop`](export-omop.md#how-it-works) does. For each test,
variant and clinical feature, it then adds a row to the matching extension
table, with the key of the CDM row. Clinical features that a report is unsure
of have no CDM row, so they have no extension row either.

When you export a file again, Gentrex replaces its extension rows together
with its CDM rows, in the same transaction.

## Settings

The command uses the settings of `gentrex export omop`, which
[Settings](export-omop.md#settings) lists, and one more under `export.omop`
in settings.yaml:

| Setting | Default | What it does |
| --- | --- | --- |
| `extension_schema` | `omop_extension` | The schema of the extension tables. Gentrex creates it if it doesn't exist. It must differ from `cdm_schema`, so that the CDM's schema holds only standard tables. |

## When something goes wrong

The exit codes and messages are those of
[`gentrex export omop`](export-omop.md#when-something-goes-wrong). One more
message can appear:

| Message | What to do |
| --- | --- |
| `export.omop.extension_schema must differ from cdm_schema` | Choose another schema for the extension tables. |
| `can't create Gentrex's tables: permission denied for database` | The database user may not create the extension schema. Ask the CDM's team to create it, or to grant the right. |
