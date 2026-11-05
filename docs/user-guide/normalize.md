# Normalize report data

`gentrex normalize` turns the values copied from each report into standard
values, so you can compare reports from different labs. A date printed as
`29-JUN-1984` becomes `1984-06-29`, and the result "POSITIVE: One pathogenic
variant and one VUS were identified." becomes `positive`. Each variant's gene
gets its approved HGNC symbol and ID, and the variant's disease gets its ID in
the Mondo Disease Ontology (MONDO). Each clinical feature gets the closest
term of the Human Phenotype Ontology (HPO).

The command reads `extractions.jsonl` from a run of `gentrex extract` and
writes `normalized.jsonl` to `results/normalize/`. It runs on the CPU without
a model server and takes a minute or two for a few hundred reports. Then you
can [load the records into a database](load.md), or export them as
[Phenopackets](export-phenopackets.md), into
[an OMOP database](export-omop.md) or as [FHIR® Bundles](export-fhir.md).

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A finished run of `gentrex extract` in `results/extract/`.
- About 400 MB of free disk in `data/ontology/` for the HGNC complete set,
  the HPO and MONDO releases and the HPO index.
- About 3 GB of free disk for the two models that find HPO terms and the
  Python packages that run them, sentence-transformers and PyTorch. Step 2
  installs them.

On Mount Sinai's Minerva cluster, start an
[interactive session](../minerva/minerva.md#normalize-report-data) first and
follow the steps below in it.

## Step 1: Download the HGNC complete set

Gentrex looks up each gene symbol in the HGNC complete set, which lists every
approved human gene symbol with its HGNC ID, aliases and previous symbols.
Download the snapshot of 6 October 2026 into `data/ontology/`:

```bash
mkdir -p data/ontology
curl -f -o data/ontology/hgnc_complete_set_2026-10-06.txt \
  https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/hgnc_complete_set_2026-10-06.txt
```

The file is about 17 MB. HGNC keeps its quarterly snapshots, so later runs
get the same symbols from it. To use a newer snapshot, download it and set
`normalize.hgnc_path` in settings.yaml to its name.

## Step 2: Build the HPO index

Gentrex finds the HPO term for a clinical feature by comparing embeddings. An
embedding is a list of numbers that a model computes for a text, and texts
with similar meanings get similar lists. The HPO index is a file with the
embeddings of all HPO labels and synonyms.

First, download the HPO release of 1 September 2026:

```bash
curl -f -L -o data/ontology/hp-base.json \
  https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/hp-base.json
```

Keep this file after you build the index, because [`gentrex load`](load.md)
reads the HPO hierarchy from it.

Then build the index from it:

```bash
uv run --extra hpo python scripts/build_hpo_index.py data/ontology/hp-base.json
```

The first time, `--extra hpo` installs sentence-transformers, PyTorch and
torchvision into Gentrex's `.venv` folder, and sentence-transformers
downloads the two models, SapBERT and EmbeddingGemma 2, from Hugging Face.
Only this script and `gentrex normalize` need these packages, so they're an
optional extra that uv installs only for a command with `--extra hpo`.

After about 6 minutes on a laptop CPU, the script prints
`wrote 45178 names to data/ontology/hpo-v2026-09-01.npz`. The index goes to
the path in `normalize.hpo.path` in settings.yaml, and running the script
again replaces it.

To try other sentence-transformers models, change `normalize.hpo.models` in
settings.yaml and build the index again. `gentrex normalize` stops if the
index was built with other models or prompts, because embeddings from
different models can't be compared.

To normalize without HPO terms, skip this step and run `gentrex normalize`
with `--no-hpo` in step 4.

## Step 3: Download the MONDO release

The disease names in `associated_phenotype` are matched to MONDO, which
merges OMIM, Orphanet and other disease lists. Each disease there has one ID,
like MONDO:0100135 for Dravet syndrome. Download the release of 3 November
2026:

```bash
curl -f -L -o data/ontology/mondo-base.json \
  https://github.com/monarch-initiative/mondo/releases/download/v2026-11-03/mondo-base.json
```

The file is about 95 MB. To use a newer release, download it in its place.

## Step 4: Run

```bash
uv run --extra hpo gentrex normalize
```

This reads `results/extract/latest`, the newest finished run of
`gentrex extract`, and writes a new run folder like
`results/normalize/20261019-030000/`. To read another run:

```bash
uv run --extra hpo gentrex normalize --input results/extract/20261014-150000
```

To run without the HPO index:

```bash
uv run gentrex normalize --no-hpo
```

The clinical features then get no HPO terms, and you don't need
`--extra hpo`.

The embedding models print a few lines of their own while they load. Then you
see one line per report and a count of the reports written and those with an
error. If some reports have an error, the last line lists them, as in
`failed files: report-07.pdf`.

## Check the result

Each run folder has three files:

| File | Contents |
| --- | --- |
| `normalized.jsonl` | One record per report. |
| `run.yaml` | The command, the run of `gentrex extract` it read and the settings, including the embedding models. It also has the checksum of the HGNC complete set (`hgnc_sha256`) and the MONDO and HPO releases (`mondo_version`, `hpo_version`). |
| `log.txt` | What Gentrex printed during the run. |

`results/normalize/latest` points to the newest finished run
([Runs and results](runs-and-results.md#run-folders)).

`normalized.jsonl` has one line per report, in the order of the records from
`gentrex extract`. Each line is the record from `gentrex extract`, unchanged,
with one more field, `normalized`. Shortened, a record looks like this:

```json
{
  "file": "report-04.pdf",
  "pages": [1, 2],
  "data": {
    "date_of_birth": "29-JUN-1984",
    "specimen_type": "Buccal swab",
    "overall_result_raw": "POSITIVE: One pathogenic variant and one VUS were identified.",
    "patient_phenotypes": [{"text": "Breast carcinoma", "present": true}],
    "variants": [
      {"gene_symbol": "BRCA2", "classification": "pathogenic", "associated_phenotype": "Hereditary breast and ovarian cancer syndrome"},
      {"gene_symbol": "ATM", "classification": "uncertain_significance", "associated_phenotype": "Ataxia-telangiectasia"}
    ]
  },
  "normalized": {
    "date_of_birth": "1984-06-29",
    "specimen_type": "buccal_swab",
    "overall_result": "positive",
    "overall_result_basis": "wording",
    "overall_result_conflict": false,
    "patient_phenotypes": [
      {
        "hpo_id": "HP:0003002",
        "label": "Breast carcinoma",
        "models_agree": true,
        "candidates": [
          {
            "hpo_id": "HP:0003002",
            "label": "Breast carcinoma",
            "models": {
              "cambridgeltl/SapBERT-from-PubMedBERT-fulltext": {"name": "Breast carcinoma", "similarity": 1.0},
              "google/embeddinggemma-2": {"name": "Breast carcinoma", "similarity": 1.0}
            }
          },
          {
            "hpo_id": "HP:0100013",
            "label": "Neoplasm of the breast",
            "models": {
              "cambridgeltl/SapBERT-from-PubMedBERT-fulltext": {"name": "Tumours of the breast", "similarity": 0.8094},
              "google/embeddinggemma-2": {"name": "Breast tumor", "similarity": 0.9627}
            }
          }
        ]
      }
    ],
    "variants": [
      {
        "gene_symbol": "BRCA2", "hgnc_id": "HGNC:1101", "gene_status": "approved",
        "disease_id": "MONDO:0003582", "disease_label": "hereditary breast ovarian cancer syndrome", "disease_status": "synonym"
      },
      {
        "gene_symbol": "ATM", "hgnc_id": "HGNC:795", "gene_status": "approved",
        "disease_id": "MONDO:0008840", "disease_label": "ataxia telangiectasia", "disease_status": "label"
      }
    ]
  },
  "error": null
}
```

A field in `normalized` has the name of the `data` field it comes from, or
that name without `_raw`. The exceptions are `overall_result_basis` and
`overall_result_conflict`, which describe how Gentrex chose
`overall_result`. Lists keep their order, so `normalized.variants[0]`
belongs to `data.variants[0]`.

| Field | Meaning |
| --- | --- |
| `date_of_birth`, `collection_date`, `received_date`, `test_started_date`, `report_date` | The date as YYYY-MM-DD, or `null` if the report gives no date or Gentrex can't read the printed one. |
| `specimen_type` | `buccal_swab`, `whole_blood`, `saliva`, `bone_marrow`, `amniotic_fluid`, `chorionic_villus`, `fibroblast` or `tissue`. `null` if no category fits, or if more than one does. |
| `overall_result` | `positive`, `negative`, `uncertain`, `carrier` or `inconclusive`. `null` if neither the result statement nor the classifications give a category. |
| `overall_result_basis` | `wording` if the category comes from the result statement, `overall_result_raw`. `variants` if it comes from the variants' classifications. `null` if `overall_result` is `null`. |
| `overall_result_conflict` | `true` if the result statement and the classifications give different categories. Check these reports against their PDFs. |
| `patient_phenotypes` | One HPO match per clinical feature, or `null` after a run with `--no-hpo`. |
| `variants` | One entry per variant, with the approved symbol, the HGNC ID and `gene_status`, and the MONDO ID, label and `disease_status` of the disease in `associated_phenotype`. |

Each HPO match has these fields:

| Field | Meaning |
| --- | --- |
| `hpo_id`, `label` | The matched HPO term and its label, the first of the `candidates`. |
| `models_agree` | `true` if both models score the same term highest. Check the matches with `false` first, because they're more often wrong. |
| `candidates` | The 5 terms with the highest combined score, best first. Under `models`, each model gives the term's label or synonym that came closest to the feature (`name`) and how close it came (`similarity`). |

`similarity` is the cosine similarity of the embeddings of the feature and
that name. It's 1.0 when the feature is written exactly like an HPO name,
apart from upper and lower case, and lower the more the two differ. For the
feature "Breast carcinoma", the term "Carcinoma" has a similarity of 0.65
with SapBERT and 0.96 with EmbeddingGemma 2. Each model has its own scale, so
compare a similarity only with others from the same model.

The feature "history of hypotonia" matched Hypotonia, and both models scored
it highest. For "seizures since infancy", the match was Neonatal seizure,
which is too specific. There the models disagreed, so `models_agree` is
`false`, and the candidates include the broader term Seizure.

On GSC+, a public test set of 939 phenotype mentions that experts mapped to
HPO, the match was the experts' term for 67.1% of the mentions, and the
experts' term was among the 5 candidates for 86.0%. Where the models agreed,
the match was right for 78.5%, and where they disagreed, for 36.1%.
[Evaluation results](../../evaluation_results/README.md) has the details.

`gene_status` says how the symbol matched:

| `gene_status` | Meaning |
| --- | --- |
| `approved` | The symbol is the gene's approved symbol. |
| `alias`, `previous` | The symbol is an alias or a previous symbol of exactly one gene, whose approved symbol is given. `alias_or_previous` means it is both. |
| `ambiguous` | The symbol is an alias or previous symbol of several genes. Gentrex can't tell which one the report meant, so it gives none. |
| `unmapped` | The symbol isn't in the HGNC complete set. |
| `missing` | The variant has no gene symbol. |

`disease_status` says how the disease name matched:

| `disease_status` | Meaning |
| --- | --- |
| `label` | The name is the disease's label in MONDO, apart from case and punctuation. `Ataxia-telangiectasia` matches the label `ataxia telangiectasia`. |
| `synonym` | The name is an exact synonym of exactly one disease. |
| `ambiguous` | The name is a label or exact synonym of several diseases. Gentrex can't tell which one the report meant, so it gives none. |
| `unmapped` | No disease has this name. [Diseases](#diseases) says which names end up here. |
| `missing` | The variant has no `associated_phenotype`. |

To count the variants per `disease_status`:

```bash
grep -o '"disease_status": "[a-z]*"' results/normalize/latest/normalized.jsonl | sort | uniq -c
```

To count the reports per result category:

```bash
grep -o '"overall_result": "[a-z]*"' results/normalize/latest/normalized.jsonl | sort | uniq -c
```

To list the reports whose statement and classifications disagree:

```bash
grep '"overall_result_conflict": true' results/normalize/latest/normalized.jsonl
```

## How it works

### Overall result

Gentrex takes the category from the laboratory's own result statement,
because the laboratory has already weighed the variants, their inheritance and
any secondary findings. The first category word in the statement decides:

| `overall_result_raw` | `overall_result` |
| --- | --- |
| POSITIVE: One pathogenic variant and one VUS were identified. | `positive` |
| UNCERTAIN: A variant of uncertain significance was identified. | `uncertain` |
| No pathogenic or likely pathogenic variants were identified. | `negative` |
| CARRIER: One heterozygous pathogenic CFTR variant was identified. | `carrier` |
| PRIMARY RESULT: NEGATIVE. SECONDARY RESULT: POSITIVE. | `negative` |
| INCONCLUSIVE: Additional characterization is required. | `inconclusive` |

Everything from the word "secondary" on is ignored, because a secondary
finding doesn't change the primary result. Besides the category words,
"pathogenic variant" counts as positive, and "VUS" and "unknown significance"
count as uncertain. "No" or "not" followed within six words by "variants"
counts as negative, and so does "not a carrier". In "No pathogenic or likely
pathogenic variants were identified.", the negative wording comes first, so
the statement is negative.

When the statement names no category, the classifications of the primary
findings decide. A pathogenic or likely pathogenic variant makes the report
positive. Without one, a VUS makes it uncertain. A report whose classified
variants are all benign or likely benign is negative. Variants with
`is_secondary_finding` set to `true` don't count. A report without variants,
or without classifications, gets `null`, so a failed extraction doesn't look
like a negative result.

`overall_result_conflict` compares the two only for positive, negative and
uncertain, because the classifications can't express carrier or
inconclusive.

### Dates

Gentrex reads dates printed like `2026-08-27`, `08/27/2026`, `27-AUG-2026`,
`27-August-2026`, `August 27, 2026` and `Aug 27, 2026`. A date in any other
format becomes `null` instead of a guess.

Dates with slashes are read month first, as US laboratories print them. A
date printed day first, like `27/08/2026`, becomes `null`, because 27 is not a
month. But `06/08/2026` printed day first is read as June 8, so check the
dates of reports from laboratories that print the day first.

### Specimen

Each category has a rule that looks for its words, such as "blood",
"saliva", "buccal" or "cheek swab". A specimen gets a category only if
exactly one rule matches, so "Blood and saliva" gets `null`.

### Genes

Each symbol is looked up among the approved symbols of the HGNC complete set
first, and then among the aliases and previous symbols. Upper and lower case
don't matter.

### Diseases

Each `associated_phenotype` is compared with the labels of the current MONDO
diseases first, and then with their exact synonyms. Case and punctuation
don't matter. If the name as printed matches nothing, Gentrex tries it again
without the text in parentheses, so
`Hereditary breast and ovarian cancer syndrome (HBOC)` matches too.

Related, broader and narrower synonyms don't count, because they can name a
different disease from the one the report means. Abbreviations don't count
either, so `MELAS` alone stays unmapped, while
`Mitochondrial encephalomyopathy, lactic acidosis, and stroke-like episodes`
matches. One abbreviation often stands for several diseases. In MONDO, `RTS`
is an abbreviation of Rett syndrome, but laboratories also write it for
Rubinstein-Taybi syndrome. A name that ties the disease to a gene, like
`SCN1A-related disorders`, isn't a MONDO disease and stays unmapped too, so
Gentrex never guesses a diagnosis.

### HPO terms

The HPO index contains the 45,178 labels and synonyms of the HPO terms that
aren't deprecated, embedded by each model in `normalize.hpo.models`. Gentrex
embeds each clinical feature with the same models and compares it with every
name by cosine similarity. A term can have several names, so each term scores
the similarity of its closest name. Features and names are both lowercased
first, because EmbeddingGemma 2 treats "Ataxia" and "ataxia" as different
text.

SapBERT learned which names mean the same biomedical concept, including many
abbreviations. EmbeddingGemma 2 learned general language. Their scores lie on
different scales, so Gentrex turns each model's term scores into z-scores and
adds those. A z-score says how far a score lies above the model's average for
this feature, in units of the model's spread. A term that both models score
well above average comes first, and a model that is far surer of one term
than of the others counts more. The 5 terms with the highest sums
(`normalize.hpo.top_k`) become the `candidates`.

EmbeddingGemma 2 is trained with task prompts, short texts put before each
input. Gentrex gives it the prompt `SentenceSimilarity`, which puts
"task: sentence similarity | query: " before every feature and every HPO
name. With the prompt, the model put the experts' term among its first 5
terms for 81.9% of the GSC+ mentions, and without it for 79.7%.

uv.lock pins the versions of sentence-transformers, PyTorch and torchvision,
so the embeddings don't change when a new version comes out.

A feature that the patient doesn't have, with `present` set to `false`, gets
an HPO term too, because the term describes the feature. The `present` flag
stays in `data.patient_phenotypes`.

## Settings

The settings are under `normalize` in
[`src/gentrex/defaults/settings.yaml`](../../src/gentrex/defaults/settings.yaml):

| Setting | Default | What it does |
| --- | --- | --- |
| `hgnc_path` | `data/ontology/hgnc_complete_set_2026-10-06.txt` | The HGNC complete set from step 1. |
| `mondo_path` | `data/ontology/mondo-base.json` | The MONDO release from step 3. |
| `hpo.models` | SapBERT, and EmbeddingGemma 2 with the prompt `SentenceSimilarity` | The sentence-transformers models that embed the HPO names and the clinical features, each with its `name` on Hugging Face and an optional `prompt`. After you change them, build the index again (step 2). |
| `hpo.path` | `data/ontology/hpo-v2026-09-01.npz` | The HPO index from step 2. |
| `hpo.top_k` | `5` | The number of terms kept in `candidates` for each feature. The four after the match are alternatives for when you check it, because the right term is sometimes a close second. |

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report has a record without an error. | Nothing. |
| 1 | A file that `gentrex normalize` needs is missing, unreadable or doesn't match the settings, some reports have an error, or the run stopped with a traceback. The end of the output says which. | See below. |

If a file is missing, unreadable or doesn't match the settings, Gentrex stops
before it writes anything:

| Message | What to do |
| --- | --- |
| `results/extract/latest/extractions.jsonl not found` | Run `gentrex extract` first, or name a run of `gentrex extract` with `--input`. |
| `data/ontology/hgnc_complete_set_2026-10-06.txt not found` | Do step 1. |
| `lacks columns: alias_symbol, hgnc_id, prev_symbol, symbol` | The file at `normalize.hgnc_path` isn't the HGNC complete set, for example a web page saved in its place. Download it again as in step 1. |
| `data/ontology/mondo-base.json not found` | Do step 3. |
| `data/ontology/hpo-v2026-09-01.npz not found` | Do step 2, or run with `--no-hpo`. |
| `No module named 'sentence_transformers'` or `requires the Torchvision library` | Run `gentrex normalize` with `uv run --extra hpo`, as in step 4. |
| `the index ... was built with ..., but settings.yaml names ...` | `normalize.hpo.models` changed after the index was built, or an older version of Gentrex built the index. Build the index again as in step 2. |

A report with an error still gets a record. Its `error` field says what went
wrong:

- An error from `gentrex extract`, like a failed request, is copied over. If
  the record from `gentrex extract` has no data, `normalized` is `null`.
- If normalizing failed, the error contains `normalize:` and the reason. Then
  `normalized` is `null`, and `data` is kept for you to check.

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
