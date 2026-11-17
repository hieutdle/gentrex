# Evaluate MONDO matching

`gentrex normalize`
[looks up the disease of each variant in MONDO](../docs/user-guide/normalize.md#diseases),
by the diseases' labels and exact synonyms. The script in this folder
measures how often that lookup finds the right disease. Its test set comes
from ClinVar, whose `variant_summary` file names the conditions of each
variant and gives most of them a MONDO ID.

Run the script when you change how `gentrex normalize` matches disease names,
or after a new MONDO release. The results of the last run, and what they mean
for Gentrex, are in
[evaluation_results/mondo-matching.md](../evaluation_results/mondo-matching.md).

## Before you start

You need Gentrex installed
([Transcribe PDF pages](../docs/user-guide/transcribe.md#step-1-install))
and two reference files, which this script downloads into `data/` if they
are missing:

```bash
evaluation/download_reference_files.sh
```

ClinVar's file takes 440 MB. Neither file contains patient data, so the
script can run on any machine.

## Run

```bash
uv run python evaluation/mondo_normalization.py
```

The script takes about 15 seconds and ends with
`wrote evaluation_results/mondo_normalization.json and .md`. It reads the
ClinVar file and the MONDO release that `evaluation/settings.yaml` and the
default settings name. `--clinvar` and `--release` name other files.

## Check the result

A run writes two files to `evaluation_results/`:

| File | What it holds |
| --- | --- |
| `mondo_normalization.md` | The shares of names that got ClinVar's ID, another ID or none, and the most frequent names of the last two kinds |
| `mondo_normalization.json` | The same numbers, with the checksum of the ClinVar file and the MONDO release |

The table has two columns. "Distinct names" counts each condition name
once. "Weighted by variants" counts a name once for each ClinVar variant
that has it, so a name that many variants share weighs more.

## How it works

Each row of `variant_summary` lists a variant's conditions twice, as names
in `PhenotypeList` and as IDs in `PhenotypeIDS`, in the same order. The
script pairs them and keeps the pairs with a MONDO ID. Names such as "not
provided" are left out, and so are IDs that the MONDO release no longer
uses. A variant has one row per genome build, and only the GRCh38 rows are
read.

Every distinct name then goes through the lookup of `gentrex normalize`.
The outcome is one of these:

| Outcome | Meaning |
| --- | --- |
| same ID | The lookup found the disease that ClinVar gives |
| other ID | The lookup found another disease |
| ambiguous | Several diseases have the name, so the lookup gave none |
| unmapped | No disease has the name |
