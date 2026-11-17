# MONDO matching on ClinVar's condition names

Written by `evaluation/mondo_normalization.py` on 2026-11-17, from `variant_summary_2026-11.txt.gz` and MONDO 2026-11-03. The test set has 9,278 distinct condition names with a current MONDO ID, on 2,847,782 variants. 3 more names have an ID that MONDO no longer uses and are left out.

| Outcome | Distinct names | Weighted by variants |
| --- | --- | --- |
| same ID | 95.2% | 88.0% |
| other ID | 0.2% | 0.1% |
| ambiguous | 0.0% | 0.0% |
| unmapped | 4.5% | 11.9% |

Of the names that got ClinVar's ID, 94.8% are the disease's MONDO label and 5.2% one of its exact synonyms.

## Most frequent names without a match

| Name | ClinVar's ID | Variants |
| --- | --- | --- |
| Hereditary cancer-predisposing syndrome | MONDO:0015356 | 216,347 |
| Jeune thoracic dystrophy | MONDO:0018770 | 4,698 |
| Polycystic kidney disease, adult type | MONDO:0008263 | 4,502 |
| Primary dilated cardiomyopathy | MONDO:0005021 | 4,048 |
| Cardiac arrhythmia | MONDO:0007263 | 4,033 |
| Malignant lymphoma, large B-cell, diffuse | MONDO:0018905 | 3,697 |
| Oto-palato-digital syndrome, type II | MONDO:0010571 | 3,142 |
| Microcephaly, normal intelligence and immunodeficiency | MONDO:0009623 | 3,106 |
| Progressive sclerosing poliodystrophy | MONDO:0008758 | 3,024 |
| Walker-Warburg congenital muscular dystrophy | MONDO:0000171 | 2,613 |
| Hereditary pheochromocytoma and paraganglioma | MONDO:0017366 | 2,521 |
| Primary familial hypertrophic cardiomyopathy | MONDO:0024573 | 2,359 |
| Congenital hyperammonemia, type I | MONDO:0009376 | 2,043 |
| Deficiency of alpha-mannosidase | MONDO:0009561 | 1,836 |
| Cutis laxa, X-linked | MONDO:0010572 | 1,666 |

## Most frequent names with another ID

| Name | ClinVar's ID | Gentrex's ID | Variants |
| --- | --- | --- | --- |
| Histiocytic medullary reticulosis | MONDO:0011338 | MONDO:0004612 | 689 |
| Hypohidrotic X-linked ectodermal dysplasia | MONDO:0010585 | MONDO:0016535 | 571 |
| ALG2-congenital disorder of glycosylation | MONDO:0011933 | MONDO:1060320 | 312 |
| Kartagener syndrome | MONDO:0009484 | MONDO:0016575 | 249 |
| Myosin storage myopathy | MONDO:0008409 | MONDO:0018889 | 231 |
| Premature ovarian failure | MONDO:0005387 | MONDO:0001119 | 168 |
| Euthyroid goiter | MONDO:0007681 | MONDO:0001658 | 135 |
| Mucopolysaccharidosis, MPS-I-S | MONDO:0011760 | MONDO:0011759 | 120 |
| Aarskog syndrome | MONDO:0010589 | MONDO:0021005 | 102 |
| Congenital central hypoventilation | MONDO:0800031 | MONDO:0800026 | 88 |
| Mesangiocapillary glomerulonephritis | MONDO:0002461 | MONDO:0018904 | 31 |
| Nephroblastoma | MONDO:0006058 | MONDO:0019004 | 19 |
| Symphalangism-brachydactyly syndrome | MONDO:0008519 | MONDO:0017923 | 12 |
| Familial chronic mucocutaneous candidiasis | MONDO:0013140 | MONDO:0015279 | 7 |
| Xeroderma pigmentosum group G/Cockayne syndrome | MONDO:0800314 | MONDO:0010216 | 4 |
