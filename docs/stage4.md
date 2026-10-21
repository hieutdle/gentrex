# Stage 4: Normalize report data

Stage 4 turns the values that stage 3 copied from each report into standard
values, so that you can compare and count reports from different
laboratories. A date printed as `29-JUN-1984` becomes `1984-06-29`. The result
"POSITIVE: One pathogenic variant and one VUS were identified." becomes the
category `positive`. Each variant's gene gets its approved HGNC symbol and ID,
and each of the patient's clinical features gets the closest term of the Human
Phenotype Ontology (HPO), which two embedding models find together.
[Stage 5](stage5.md) then loads the records into a PostgreSQL database.

Stage 4 reads `extractions.jsonl` from a stage 3 run and writes
`normalized.jsonl`, with one line per report, to `results/normalize/`. Each
line keeps the stage 3 record unchanged and adds the standard values next to
it. Stage 4 needs no model server and no GPU. It runs on the CPU and
normalizes a few hundred reports in a minute or two.

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](stage1.md#step-1-install).
- A finished stage 3 run, in `results/extract/`.
- About 300 MB of free disk in `data/ontology/`, for the HGNC complete set,
  the HPO release and the HPO index.
- About 3 GB of free disk for sentence-transformers, PyTorch and the two
  embedding models. sentence-transformers and PyTorch are the Python packages
  that stage 4 uses to find HPO terms. Step 2 installs them.

On Mount Sinai's Minerva cluster, start an interactive session first, as
[Stage 4 on Minerva](minerva.md#stage-4-normalize-report-data) shows. Then
follow the steps below in that session.

## Step 1: Download the HGNC complete set

Stage 4 looks up each gene symbol in the HGNC complete set. This file lists
every human gene symbol that the HUGO Gene Nomenclature Committee approved,
with its HGNC ID, aliases and previous symbols. Download the snapshot of 6
October 2026 into `data/ontology/`:

```bash
mkdir -p data/ontology
curl -f -o data/ontology/hgnc_complete_set_2026-10-06.txt \
  https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/hgnc_complete_set_2026-10-06.txt
```

`-o` names the file that curl writes. `-f` makes curl stop with an error if
the download fails. Without it, curl would save the server's error page
under the file's name.

The file is tab-separated and about 17 MB. HGNC keeps its quarterly
snapshots, so this file gives the same symbols in every later run.
`normalize.hgnc_path` in settings.yaml names the file. To use a newer
snapshot, download it and change `hgnc_path` to its name.

## Step 2: Build the HPO index

Stage 4 finds the HPO term for a clinical feature by comparing embeddings. An
embedding is a list of numbers that a model computes for a text, so that texts
with similar meanings get similar lists. The HPO index is one file that holds
the embeddings of all HPO labels and synonyms. [Terms](../README.md#terms) in
the README explains these words further.

First, download the HPO release of 1 September 2026:

```bash
curl -f -L -o data/ontology/hp-base.json \
  https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01/hp-base.json
```

`-L` follows GitHub's redirect to the address that serves the file. `-f` and
`-o` work as in step 1. Keep the file after building the index, because
[stage 5](stage5.md) reads the HPO hierarchy from it.

Then build the index from it:

```bash
uv run --extra hpo python scripts/build_hpo_index.py data/ontology/hp-base.json
```

The script prints `wrote 45178 names to data/ontology/hpo-v2026-09-01.npz`.
It takes about 6 minutes on a laptop CPU, because it embeds every name with
two models. The file it writes is the one that `normalize.hpo.path` in
settings.yaml names. The script works like this:

- It makes one name for each HPO label and one for each synonym. It leaves
  out deprecated terms, because HPO no longer uses them.
- It computes the embedding of each name with each model in
  `normalize.hpo.models` in settings.yaml. By default, these are SapBERT, a
  biomedical model of about 440 MB that learned which names mean the same
  concept, and EmbeddingGemma 2, a general model of about 1.4 GB from Google.
  sentence-transformers downloads both from Hugging Face on the first run.
- It lowercases every name first, because EmbeddingGemma 2 treats "Ataxia"
  and "ataxia" as different text. Stage 4 lowercases the clinical features
  in the same way.
- It saves the names, the embeddings from each model, and the models' names
  and prompts in one NumPy file. Stage 4 embeds each clinical feature with
  the same models and prompts, so that the feature's embeddings can be
  compared with the names' embeddings. If the index was built with other
  models or prompts, stage 4 stops with a message like
  `the index ... was built with ..., but settings.yaml names ...`, because
  embeddings from different models can't be compared.
- `--extra hpo` installs sentence-transformers, PyTorch and torchvision into
  Gentrex's `.venv` folder the first time. EmbeddingGemma 2 needs torchvision
  to load, even for text. Only this script and stage 4 need these packages,
  so Gentrex lists them in pyproject.toml as an optional extra named `hpo`.
  uv installs an extra only for a command that names it. uv.lock fixes the
  versions of these packages, so the embeddings don't change when a new
  version comes out. Stage 4's command in step 3 has the same option.

Running the script again replaces the index. To try other
sentence-transformers models, change `normalize.hpo.models` in settings.yaml
and build the index again.

To normalize without HPO terms, skip this step and run stage 4 with
`--no-hpo` in step 3.

## Step 3: Run

```bash
uv run --extra hpo gentrex stage4
```

This reads the newest finished stage 3 run, `results/extract/latest`, and
writes a new folder named after the time the run started, such as
`results/normalize/20261019-030000/`. To read another stage 3 run:

```bash
uv run --extra hpo gentrex stage4 --input results/extract/20261014-150000
```

To run without the HPO index:

```bash
uv run gentrex stage4 --no-hpo
```

The clinical features then get no HPO terms. This command needs no
`--extra hpo`, because it embeds nothing.

Gentrex first loads the two embedding models, which print a few lines of
their own. Then Gentrex prints one line per report. The last line counts the reports
written and the reports with an error.

## Check the result

Each run folder holds three files:

| File | Contents |
| --- | --- |
| `normalized.jsonl` | One record per report. |
| `run.yaml` | The command, the stage 3 run that was read and the settings, including the embedding models. It also records the checksum of the HGNC complete set (`hgnc_sha256`), so you can tell which version of it a run used. |
| `log.txt` | What Gentrex printed during the run. |

`results/normalize/latest` points to the newest finished run.
[Runs and results](../README.md#runs-and-results) explains run folders and
`latest`.

`normalized.jsonl` has one line per report, in the order of the stage 3
records. Each line is a JSON object with the fields of a stage 3 record and
one more, `normalized`. Shortened and spread over several lines, a record
looks like this:

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
      {"gene_symbol": "BRCA2", "classification": "pathogenic"},
      {"gene_symbol": "ATM", "classification": "uncertain_significance"}
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
      {"gene_symbol": "BRCA2", "hgnc_id": "HGNC:1101", "gene_status": "approved"},
      {"gene_symbol": "ATM", "hgnc_id": "HGNC:795", "gene_status": "approved"}
    ]
  },
  "error": null
}
```

A field in `normalized` has the name of the `data` field it comes from, or
that name without `_raw`. `overall_result_basis` and `overall_result_conflict`
have no `data` field, because they describe how stage 4 chose
`overall_result`. Lists keep their order, so `normalized.variants[0]` belongs
to `data.variants[0]`.

| Field | Meaning |
| --- | --- |
| `date_of_birth`, `collection_date`, `received_date`, `test_started_date`, `report_date` | The date as YYYY-MM-DD. It is `null` if the report gives no date, or if Gentrex can't read the printed one. |
| `specimen_type` | `buccal_swab`, `whole_blood`, `saliva`, `bone_marrow`, `amniotic_fluid`, `chorionic_villus`, `fibroblast` or `tissue`. It is `null` if no category fits, or if more than one does. |
| `overall_result` | `positive`, `negative`, `uncertain`, `carrier` or `inconclusive`. It is `null` if neither the result statement nor the classifications give a category. |
| `overall_result_basis` | `wording` if the category comes from the result statement, `overall_result_raw`. `variants` if it comes from the variants' classifications. `null` if `overall_result` is `null`. |
| `overall_result_conflict` | `true` if the result statement and the classifications give different categories. Check these reports against their PDFs. |
| `patient_phenotypes` | One HPO match per clinical feature, or `null` when stage 4 ran with `--no-hpo`. |
| `variants` | One entry per variant, with the approved symbol, the HGNC ID and `gene_status`. |

Each HPO match has these fields:

| Field | Meaning |
| --- | --- |
| `hpo_id`, `label` | The matched HPO term and its label. It is the first of the `candidates`. |
| `models_agree` | `true` if both models score the same term highest. `false` marks a match to check first, because such matches are more often wrong. |
| `candidates` | The 5 terms with the highest combined score, best first. For each model, `models` gives the label or synonym of the term that came closest to the feature (`name`), and how close it came (`similarity`). |

`similarity` is the cosine similarity of the embeddings of the feature and
that name. It is 1.0 when the feature is written exactly like an HPO name,
apart from upper and lower case, and lower the more the two differ. Each
model has its own scale, so compare a similarity only with others from the
same model. For the feature "Breast carcinoma", the term "Carcinoma" has a
similarity of 0.65 with SapBERT and 0.96 with EmbeddingGemma 2.

The feature "history of hypotonia" matched Hypotonia, and both models scored
it highest. The feature "seizures since infancy" matched Neonatal seizure,
which is too specific, because infancy lasts beyond the first 4 weeks of
life. There the models disagreed, so `models_agree` is `false`, and the
candidates include the broader term Seizure.

On GSC+, a public test set of 939 phenotype mentions that experts mapped to
HPO, the match was the experts' term for 67.1% of the mentions. The experts'
term was among the 5 candidates for 86.0%. Where the models agreed, the match
was right for 78.5% of the mentions, and where they disagreed, for 36.1%.
[Evaluation results](../evaluation_results/README.md) has the details.

`gene_status` says how the symbol matched:

| `gene_status` | Meaning |
| --- | --- |
| `approved` | The symbol is the gene's approved symbol. |
| `alias`, `previous` | The symbol is an alias or a previous symbol of exactly one gene, whose approved symbol is given. `alias_or_previous` means it is both. |
| `ambiguous` | The symbol is an alias or previous symbol of several genes. Gentrex can't tell which one the report meant, so it gives none. |
| `unmapped` | The symbol is not in the HGNC complete set. |
| `missing` | The variant has no gene symbol. |

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

Stage 4 takes the category from the laboratory's own result statement,
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

Stage 4 ignores the statement from the word "secondary" on, because a
secondary finding doesn't change the primary result. Besides the category
words, "pathogenic variant" counts as positive, and "VUS" and "unknown
significance" count as uncertain. "No" or "not" followed within six words by
"variants" counts as negative, and so does "not a carrier". In "No pathogenic
or likely pathogenic variants were identified.", the negative wording starts
first, so the statement is negative.

When the statement names no category, the classifications of the primary
findings decide. A pathogenic or likely pathogenic variant makes the report
positive. Without one, a VUS makes it uncertain. A report whose classified
variants are all benign or likely benign is negative. Variants with
`is_secondary_finding` set to `true` don't count. A report without variants,
or without classifications, gets `null`, so that a failed extraction doesn't
look like a negative result.

`overall_result_conflict` compares the two ways for the categories that both
can give: positive, negative and uncertain. Carrier and inconclusive are not
compared, because the classifications can't express them.

### Dates

Stage 4 reads dates printed like `2026-08-27`, `08/27/2026`, `27-AUG-2026`,
`27-August-2026`, `August 27, 2026` and `Aug 27, 2026`. A date in any other
format becomes `null` instead of a guess.

Dates with slashes are read month first, as US laboratories print them. A
date printed day first, such as `27/08/2026`, becomes `null`, because 27 is
not a month. But `06/08/2026` printed day first is read as June 8, so check
the dates of reports from laboratories that print the day first.

### Specimen

Each category has a rule that looks for its words, such as "blood",
"saliva", "buccal" or "cheek swab". A specimen gets a category only if
exactly one rule matches, so "Blood and saliva" gets `null`.

### Genes

Stage 4 looks up each symbol among the approved symbols of the HGNC complete
set first, and then among the aliases and previous symbols. Upper and lower case
don't matter.

### HPO terms

Stage 4 lowercases each clinical feature and embeds it with each model in
`normalize.hpo.models`, the models that built the HPO index. With each model,
it compares the feature's embedding with the embeddings of all 45,178 HPO
labels and synonyms, by cosine similarity. Several names can belong to one
term, so each term scores the similarity of its closest name.

SapBERT learned which names mean the same biomedical concept, including many
abbreviations. EmbeddingGemma 2 learned general language. The two models
score on different scales, so stage 4 puts their scores on a common scale
before it adds them. For each model, it turns every term's score into a
z-score, which says how far the score lies above that model's average for
this feature, in units of the model's spread. Then it adds each term's two
z-scores. A term that both models score well above their average comes
first, and a model that is far surer of one term than of the others counts
more. The 5 terms with the highest sums (`normalize.hpo.top_k`) become the
`candidates`.

EmbeddingGemma 2 is trained with task prompts, short texts put before each
input. Stage 4 gives it the prompt `SentenceSimilarity`, which puts
"task: sentence similarity | query: " before every feature and every HPO
name. With the prompt, the model put the experts' term among its first 5
terms for 81.9% of the GSC+ mentions, and without it for 79.7%.

A feature that the patient doesn't have, with `present` set to `false`, gets
an HPO term too, because the term names the feature. The `present` flag stays
in `data.patient_phenotypes`.

## Settings

The settings of stage 4 are in
[`src/gentrex/defaults/settings.yaml`](../src/gentrex/defaults/settings.yaml),
under `normalize`:

| Setting | Default | What it does |
| --- | --- | --- |
| `hgnc_path` | `data/ontology/hgnc_complete_set_2026-10-06.txt` | The HGNC complete set from step 1. |
| `hpo.models` | SapBERT, and EmbeddingGemma 2 with the prompt `SentenceSimilarity` | The sentence-transformers models that embed the HPO names and the clinical features, each with its `name` on Hugging Face and an optional `prompt`. After changing them, build the index again as in step 2. |
| `hpo.path` | `data/ontology/hpo-v2026-09-01.npz` | The HPO index from step 2. The HPO release in its name ends up in `run.yaml`, with the other settings. |
| `hpo.top_k` | `5` | The number of terms kept in `candidates` for each feature. The four after the match are alternatives for when you check it, because the right term is sometimes a close second. |

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report has a record without an error. | Nothing. |
| 1 | A file that stage 4 needs is missing, unreadable or doesn't match the settings, some reports have an error, or the run stopped with a traceback. The end of the output says which. | See below. |

If a file is missing, unreadable or doesn't match the settings, stage 4 stops
before it writes anything:

| Message | What to do |
| --- | --- |
| `results/extract/latest/extractions.jsonl not found` | Run stage 3 first, or name a stage 3 run with `--input`. |
| `data/ontology/hgnc_complete_set_2026-10-06.txt not found` | Do step 1. |
| `lacks columns: alias_symbol, hgnc_id, prev_symbol, symbol` | The file that `normalize.hgnc_path` names is not the HGNC complete set, for example a web page saved in its place. Download it again as in step 1. |
| `data/ontology/hpo-v2026-09-01.npz not found` | Do step 2, or run with `--no-hpo`. |
| `No module named 'sentence_transformers'` or `requires the Torchvision library` | Run stage 4 with `uv run --extra hpo`, as in step 3. |
| `the index ... was built with ..., but settings.yaml names ...` | `normalize.hpo.models` changed after the index was built, or an older version of Gentrex built the index. Build the index again as in step 2. |

A report with an error still gets a record. Its `error` field says what went
wrong:

- A stage 3 error, such as a failed request, is copied over. If stage 3
  extracted no data, `normalized` is `null`.
- If normalizing failed, the error contains `stage 4:` and the reason. Then
  `normalized` is `null`, and `data` is kept for you to check.
