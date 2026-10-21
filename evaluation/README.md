# Evaluate HPO matching

Stage 4 matches each clinical feature to an HPO term by comparing
[embeddings](../README.md#terms), as
[stage 4](../docs/stage4.md#hpo-terms) describes. The script in this folder
measures how often that match is right. It also compares the current setup
with each of its two models alone, and with BM25 added. It reads GSC+, a public test set in which experts
marked 2,122 phenotype mentions in 228 PubMed abstracts and gave each one its
HPO term. It writes the results to `evaluation_results/`.

Run it when you change `normalize.hpo.models` in settings.yaml, or the way
stage 4 ranks HPO terms. The results of the last run,
and what they mean for Gentrex, are in
[evaluation_results/README.md](../evaluation_results/README.md).

## Before you start

You need:

- Gentrex installed, as in [stage 1, step 1](../docs/stage1.md#step-1-install).
- The HPO release `data/ontology/hp-base.json`, from
  [stage 4, step 2](../docs/stage4.md#step-2-build-the-hpo-index).
- About 3 GB of free disk for the two models that the script downloads from
  Hugging Face and the packages it installs.
- About 15 minutes. The last run took 10 minutes on a laptop with an
  Apple M5 Pro. Without a GPU, the script computes everything on the CPU, and
  the run takes longer.

GSC+ holds no patient data, so the script can run on any machine.

## Step 1: Download GSC+

GSC+ comes with PhenoTagger, a phenotype tagger from the NCBI, in a zip file
of its test sets. Download the file from a fixed version of PhenoTagger, so
that every run reads the same test set, and unpack it into
`data/evaluation/`:

```bash
mkdir -p data/evaluation
curl -f -L -o data/evaluation/phenotagger-corpus.zip \
  https://raw.githubusercontent.com/ncbi-nlp/PhenoTagger/10f8ee3e1ea4c26fb44c47df28a555082748ebf2/data/corpus.zip
unzip -o data/evaluation/phenotagger-corpus.zip -d data/evaluation
```

`-f` makes curl stop with an error if the download fails, and `-L` follows
GitHub's redirect. The script reads the two GSC+ files,
`data/evaluation/corpus/GSC/GSCplus_dev_gold.tsv` and `GSCplus_test_gold.tsv`.

## Step 2: Run

```bash
uv run --extra hpo --group evaluation python evaluation/hpo_normalization.py
```

`--extra hpo` installs sentence-transformers, PyTorch and torchvision, as
for stage 4. `--group evaluation` adds scipy, which computes the significance
tests. Both are listed in pyproject.toml. The script prints a line after each
step and ends with `wrote evaluation_results/hpo_normalization.json and .md`.

## Check the result

The script writes two files to `evaluation_results/`:

| File | Contents |
| --- | --- |
| `hpo_normalization.md` | The results as tables: the accuracy of each setup, how often the two models of the current setup agree, the speed on the CPU, and mentions where the current setup and SapBERT alone disagree. |
| `hpo_normalization.json` | The same results, and the details of the run: the date, the machine, the package versions, the HPO release and a checksum of the GSC+ files. |

A new run replaces both files. When you commit them, update
[evaluation_results/README.md](../evaluation_results/README.md) to match.

## How it works

### Test set

The script counts each distinct mention once, with every HPO term the experts
gave it. Mentions that differ only in upper and lower case or in spacing count
as one. That leaves 939 mentions. 313 of them are written exactly like an HPO
label or synonym. The other 626 are worded differently, and they show how well
a setup handles wording that HPO doesn't use. HPO has replaced some IDs since
the experts annotated GSC+, so the script maps each old ID to its current one.

### Setups

Each setup ranks the HPO terms for every mention, with each term once:

| Setup | What it does |
| --- | --- |
| The models that settings.yaml names, joined by `+` | Stage 4 as it is set up, with SapBERT and EmbeddingGemma 2 combined. The script builds the HPO index and searches it with Gentrex's own code, on the CPU. |
| One of these models alone | The model's own ranking. A prompt in brackets is put before every text, as `prompt` in settings.yaml does. |
| A model that has a prompt, without it | The same model with no prompt, such as `google/embeddinggemma-2` without `SentenceSimilarity`. |
| `<setup> + BM25` | Adds BM25 scores to the setup's scores, the way stage 4 adds the scores of its models. BM25 scores HPO names by the words they share with the mention, and a word that few names contain counts more. |

Every setup uses Gentrex's own code to embed, score and combine. Only the
setup from settings.yaml runs through the index file and the search of stage
4, and the script checks that its terms match the combined scores of its
models.

### Measures

- **Top 1** is the share of mentions whose first term is one that the experts
  gave.
- **Top 5** is the share of mentions with the experts' term among the first 5
  terms. These are the `candidates` that stage 4 writes for each feature.
  **Top 10** counts the first 10 terms in the same way.
- **p** compares a setup with the current setup on the same mentions, with an
  exact McNemar test. The test looks only at the mentions that one of the two
  gets right and the other gets wrong. A p-value below 0.05 means that the
  difference is unlikely to be chance.

### Speed

The script times each model on the CPU, because stage 4 runs there. "Index
build" is the time to embed all 45,178 HPO names. "Per clinical feature" is
the time to rank the terms for one feature. For the setup from settings.yaml,
both are measured through stage 4, which ranks 50 terms here instead of 5,
so stage 4 is slightly faster in practice. For the single models, the times
come from a sample of names and mentions.

## Evaluate other models

The script evaluates the models that `normalize.hpo.models` in settings.yaml
names, with their prompts. To evaluate other models, change that setting and
run the script again. The script builds its own HPO index, so you don't need
to build one first.
