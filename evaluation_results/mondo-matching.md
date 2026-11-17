# MONDO matching results

These are the results of
[`evaluation/mondo_normalization.py`](../evaluation/mondo_normalization.py)
from 17 November 2026. The run looked up 9,278 condition names from ClinVar
in MONDO, as `gentrex normalize` does, and compared each match with the
MONDO ID that ClinVar gives the name.
[Evaluate MONDO matching](../evaluation/mondo-matching.md) explains the test
set and the measures. All numbers are in
[mondo_normalization.md](mondo_normalization.md), and the details of the run
in [mondo_normalization.json](mondo_normalization.json).

## Summary

- The lookup found ClinVar's disease for 95.2% of the names.
- Counted by variant, it found 88.0%. One name without a match, "Hereditary
  cancer-predisposing syndrome", is on 216,347 variants.
- A wrong disease is rare. 0.2% of the names got another ID than ClinVar's.
- 4.5% of the names got no disease.

## Main results

| Outcome | Distinct names | Weighted by variants |
| --- | --- | --- |
| Same ID as ClinVar | 95.2% | 88.0% |
| Another ID | 0.2% | 0.1% |
| Ambiguous | 0.0% | 0.0% |
| No match | 4.5% | 11.9% |

Of the names with the right ID, 94.8% are the disease's MONDO label and 5.2%
one of its exact synonyms.

## What this means for Gentrex

The lookup rarely gives a wrong disease, so a MONDO ID in a record can be
trusted. What it misses, it leaves without an ID, and `disease_status` says
so.

More synonyms would close little of the gap. Of the 422 names without a
match, 33 are related synonyms of their disease in MONDO, and 384 aren't
among its synonyms at all. "Polycystic kidney disease, adult type" is an
example, for autosomal dominant polycystic kidney disease. Finding these
needs something other than the names, such as the embeddings that
`gentrex normalize` already uses for HPO terms.

Names that count many variants matter most. Without "Hereditary
cancer-predisposing syndrome", the share by variant rises from 88.0% to
95.2%.

## Limits

- ClinVar prints the preferred name of each condition in MedGen, and MONDO
  takes many of its labels and synonyms from the same sources. Reports word
  diseases more freely, as in "CFTR-related disorders", so the share on real
  reports is likely lower.
- The MONDO ID is ClinVar's own mapping. Where it is wrong, a right match
  counts as another ID.
- A name counts once however many variants have it. The second column
  weighs by ClinVar's variants, not by how often a laboratory reports them.
