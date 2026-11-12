# Evaluate HPO matching

`gentrex normalize`
[matches each clinical feature to an HPO term](../docs/user-guide/normalize.md#hpo-terms)
by comparing embeddings. The script in this folder measures how often that
match is right, and how the current setup compares with each of its two
models alone and with BM25 added.
Its test set is GSC+, a public corpus in which experts marked 2,122 phenotype
mentions in 228 PubMed abstracts and gave each one its HPO term.

Run the script when you change `normalize.hpo.models` in settings.yaml or the
way `gentrex normalize` ranks HPO terms. The results of the last run, and what
they mean for Gentrex, are in
[evaluation_results/hpo-matching.md](../evaluation_results/hpo-matching.md).

## Before you start

You need:

- Gentrex installed
  ([Transcribe PDF pages](../docs/user-guide/transcribe.md#step-1-install)).
- The HPO release `data/ontology/hp-base.json`, from step 2 of
  [Normalize report data](../docs/user-guide/normalize.md#step-2-build-the-hpo-index).
- About 3 GB of free disk for the packages that the script installs and the
  two models it downloads from Hugging Face.
- About 15 minutes. The last run took 10 minutes on a laptop with an
  Apple M5 Pro. Without a GPU, everything runs on the CPU and takes longer.

GSC+ contains no patient data, so the script can run on any machine.

## Step 1: Download GSC+

GSC+ comes with PhenoTagger, the NCBI's phenotype tagger, in a zip file of its
test sets. Download the file from a fixed version of PhenoTagger, so that
every run reads the same test set, and unpack it into `data/evaluation/`:

```bash
mkdir -p data/evaluation
curl -f -L -o data/evaluation/phenotagger-corpus.zip \
  https://raw.githubusercontent.com/ncbi-nlp/PhenoTagger/10f8ee3e1ea4c26fb44c47df28a555082748ebf2/data/corpus.zip
unzip -o data/evaluation/phenotagger-corpus.zip -d data/evaluation
```

Only the two GSC+ files in it are read,
`data/evaluation/corpus/GSC/GSCplus_dev_gold.tsv` and `GSCplus_test_gold.tsv`.

## Step 2: Run

```bash
uv run --extra hpo --group evaluation python evaluation/hpo_normalization.py
```

`--extra hpo` installs sentence-transformers, PyTorch and torchvision, as for
`gentrex normalize`, and `--group evaluation` adds scipy for the significance
tests. The script prints a line after each step and ends with
`wrote evaluation_results/hpo_normalization.json and .md`.

## Check the result

A run writes two files to `evaluation_results/`:

| File | Contents |
| --- | --- |
| `hpo_normalization.md` | The results as tables: the accuracy of each setup, how often the two models of the current setup agree, the speed on the CPU, and mentions where the current setup and SapBERT alone disagree. |
| `hpo_normalization.json` | The same results, and the details of the run: the date, the machine, the package versions, the HPO release and a checksum of the GSC+ files. |

A new run replaces both files. When you commit them, update
[evaluation_results/hpo-matching.md](../evaluation_results/hpo-matching.md) to
match.

## How it works

### Test set

Each distinct mention counts once, with every HPO term the experts gave it.
Mentions that differ only in case or spacing count as one, which leaves 939.
Of these, 313 are written exactly like an HPO label or synonym. The other 626
are worded differently, and they show how well a setup handles wording that
HPO doesn't use. HPO has replaced some IDs since the experts annotated GSC+,
so the script maps each old ID to its current one.

### Setups

Each setup ranks the HPO terms for every mention, with each term once:

| Setup | What it does |
| --- | --- |
| The models in `normalize.hpo.models`, joined by `+` | `gentrex normalize` as set up, with SapBERT and EmbeddingGemma 2 combined. The script builds an HPO index and searches it with the code of `gentrex normalize`, on the CPU. |
| One of these models alone | The model's own ranking. A prompt shown in brackets after the name is put before every text, as `prompt` in settings.yaml does. |
| A model that has a prompt, without it | The same model with no prompt, for example `google/embeddinggemma-2` without `SentenceSimilarity`. |
| `<setup> + BM25` | The setup's scores with BM25 scores added, the way `gentrex normalize` adds the scores of its models. BM25 scores HPO names by the words they share with the mention, and a word that few names contain counts more. |

The other setups embed, score and combine with the same code, but without the
index file. The script checks that combining the scores of the two models
gives the same terms as the search of `gentrex normalize`.

### Measures

- **Top 1** is the share of mentions whose first term is one that the experts
  gave.
- **Top 5** is the share of mentions with a term the experts gave among the
  first 5 terms, the `candidates` that `gentrex normalize` writes for each
  feature.
- **Top 10** counts the first 10 terms in the same way.
- **p** compares a setup with the current setup on the same mentions, with an
  exact McNemar test. The test looks only at the mentions that one of the two
  gets right and the other gets wrong. A p-value below 0.05 means that the
  difference is unlikely to be chance.

### Speed

Each model is timed on the CPU, where `gentrex normalize` runs.
"Index build" is the time to embed all 45,178 HPO names, and "per clinical
feature" the time to rank the terms for one feature. For the setup from
settings.yaml, both are measured through `gentrex normalize`. It ranks 50
terms here instead of 5, so it's slightly faster in practice. The times of the
single models come from a sample of names and mentions.

## Evaluate other models

To evaluate other models, change `normalize.hpo.models` in settings.yaml and
run the script again. It takes the models and their prompts from that
setting. You don't need to build an HPO index first, because the script builds
its own.
