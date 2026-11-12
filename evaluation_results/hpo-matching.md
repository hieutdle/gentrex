# HPO matching results

These are the results of
[`evaluation/hpo_normalization.py`](../evaluation/hpo_normalization.py) from
21 October 2026, on a laptop with an Apple M5 Pro. The run tested the setup
that Gentrex uses, SapBERT and EmbeddingGemma 2 combined, and four other
setups on 939 phenotype mentions from GSC+, each with the HPO terms that
experts gave it. [Evaluate HPO matching](../evaluation/hpo-matching.md)
explains the test set, the setups and the measures. All numbers are in
[hpo_normalization.md](hpo_normalization.md), and the details of the run in
[hpo_normalization.json](hpo_normalization.json).

## Summary

- The current setup's first term was the experts' term for 67.1% of the
  mentions, and the experts' term was among its 5 candidates for 86.0%.
- The combination did better than either model alone, on both measures.
- EmbeddingGemma 2 does better with its prompt than without it.
- Whether the two models agree is a strong signal. When they scored the same
  term highest, the match was right for 78.5% of the mentions, and when they
  disagreed, for 36.1%.
- Adding BM25 made the results much worse.

## Main results

| Setup | Top 1 | Top 1, different wording | Top 5 | Top 5, different wording | Compared with the current setup |
| --- | --- | --- | --- | --- | --- |
| SapBERT + EmbeddingGemma 2 (current) | 67.1% | 53.8% | 86.0% | 80.2% | |
| SapBERT alone | 64.5% | 50.0% | 83.8% | 77.0% | Worse (p = 0.004 and 0.001). |
| EmbeddingGemma 2 alone | 63.5% | 48.4% | 81.9% | 74.6% | Worse (p < 0.001). |
| EmbeddingGemma 2 alone, without its prompt | 62.6% | 47.1% | 79.7% | 71.1% | Worse (p < 0.001). |
| Current + BM25 | 57.5% | 39.5% | 75.9% | 66.0% | Worse (p < 0.001). |

"Different wording" counts only the 626 mentions that aren't written exactly
like an HPO label or synonym.

## What this means for Gentrex

Combining the models' similarities works. The two models score on different
scales, so `gentrex normalize`
[turns each model's scores into z-scores](../docs/user-guide/normalize.md#hpo-terms)
before it adds them. An earlier version combined the models' ranks instead
and got 65.7% for the first term and 84.2% for the 5 candidates, no better
than SapBERT alone.

Use the agreement flag to decide what to check first. `gentrex normalize`
marks each match with `models_agree`. The models disagreed on 26.8% of the
mentions, and only 36.1% of those matches were right, so a reviewer saves the
most time by checking them first.

Keep the prompt. With the `SentenceSimilarity` prompt, EmbeddingGemma 2 put
the experts' term among its first 5 terms for 81.9% of the mentions, and
without it for 79.7%.

Don't add BM25. It scores names by the words they share with the mention.
Many HPO names share general words like "abnormality", and BM25 can't tell
that "ataxic" and "ataxia" mean the same thing.

The setup takes a few minutes, once. On this laptop's CPU, building the HPO
index took 5.5 minutes, and each clinical feature took about 40 ms after
that. The two models take 1.8 GB of disk.

The first term still has room to improve. For 70.6% of the mentions, at least
one of the two models scored the experts' term highest, and the two models'
first 5 terms held it for 88.6%, in 7.2 terms on average. A better way to
choose among the candidates could gain a few more points. In the
OntologyAligner study (arXiv 2609.10055), a large language model that chose
among the candidates raised the share of right first terms by about 4 points
on seven HPO test sets. Gentrex already runs Gemma 4 31B in
`gentrex extract`, so this could be tried on Minerva.

## Examples

[hpo_normalization.md](hpo_normalization.md) lists mentions where SapBERT
alone and the current setup choose different first terms. Combining the
models fixes more mentions than it breaks, but it does both:

| Mention | Experts' term | SapBERT alone | Current setup |
| --- | --- | --- | --- |
| abnormal overlying skin | Abnormality of the skin | Abnormal skin morphology | Abnormality of the skin |
| branchial arches | Branchial anomaly | Common origin of the right brachiocephalic artery and left common carotid artery | Branchial anomaly |
| BDA1 | Type A1 brachydactyly | Type A1 brachydactyly | Decreased level of thrombomodulin |
| ataxic | Ataxia | Ataxia | Gait ataxia |

SapBERT resolves abbreviations like BDA1 well, because it learned from the
synonyms in UMLS. EmbeddingGemma 2 can rate a wrong term high enough to win.
In both broken examples the models disagreed, so `models_agree` marks the
match for a check.

## Limits

- GSC+ comes from PubMed abstracts, not from genetic test reports. Reports may
  be worded differently, so a test on report features with known HPO terms
  would be stronger.
- Top 1 counts a neighboring HPO term as wrong, even when a clinician would
  accept it. For 20 of the 313 mentions written exactly like an HPO name, the
  experts chose a different term, so no method that matches names can get
  them right.
- With 939 mentions, differences of about one point are within chance. The
  p-values say which differences are not.
- The speeds come from one laptop. They show how the setups compare, not how
  long a run takes on another machine.
