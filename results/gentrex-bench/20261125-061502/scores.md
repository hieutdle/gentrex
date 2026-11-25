# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-061502/native`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 77.3% | 72.3% to 82.0% |
| Reports with every value right | 12.0% | 8.7% to 16.0% |
| MRN and date of birth both right | 90.7% | 87.3% to 93.7% |
| Value F1 (micro) | 94.6% | 94.1% to 95.1% |
| Field F1 (macro) | 94.0% | 89.1% to 95.2% |
| Exact-match value F1 | 92.4% | 91.8% to 92.9% |
| Value precision | 94.1% | 93.5% to 94.7% |
| Value recall | 95.1% | 94.5% to 95.6% |
| Variant detection F1 | 87.9% | 84.2% to 91.1% |
| Clinical variant F1 | 85.5% | 81.1% to 89.4% |
| Variant precision | 81.2% | 76.0% to 85.9% |
| Variant recall | 95.9% | 93.2% to 98.1% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 98.0% |
| Pathogenic / likely pathogenic clinical recall | 98.0% |
| Actionable ACMG F1 (P/LP vs. other) | 98.0% |
| Negative-report specificity | 58.2% |
| False-positive variant rate on negative reports | 38.5% |
| Ungrounded hallucination rate | 1.1% |
| Distractor entities copied | 40 |
| ACMG classification macro-F1 | 74.2% |
| Overall result macro-F1 | 95.9% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 3 |
| missed other variant | 8 |
| extra variant | 59 |
| actionable acmg flip | 6 |
| other acmg error | 1 |
| wrong zygosity or cn | 0 |
| wrong result or karyotype | 17 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 254 | 11 | 59 | 81.2% | 95.9% | 87.9% |
| Clinical features, by text | 704 | 54 | 64 | 91.7% | 92.9% | 92.3% |
| Clinical features, by HPO ID | 745 | 13 | 26 | 96.6% | 98.3% | 97.5% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 11 | distractor: 30, hallucination: 29 |
| Clinical features, by text | extract: 54 | hallucination: 54, distractor: 10 |
| Clinical features, by HPO ID | charged earlier: 13 | charged earlier: 24, normalize: 2 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 0 | 0 | 0 |
| `gentrex select` | 0 | 0 | 0 |
| `gentrex extract` | 214 | 214 | 298 |
| `gentrex normalize` | 0 | 12 | 2 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 704 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 10 | 17 | 100.0% | 58.8% |
| `hgvs_invalid` | 313 | 8 | 59 | 25.0% | 3.4% |
| `not_in_pages` | 6151 | 13 | 452 | 61.5% | 1.8% |

A person who looks at every report with a flag looks at 29 of 300 reports, and finds 16 of the 68 reports that count as wrong.

## Pages

The run read 1682 pages and sent 0 of them to OCR. `gentrex select` kept 871 pages. The reports state 8565 values, and 8142 of them are right in the records. Lost were 0 in `gentrex transcribe`, 0 in `gentrex select`, 423 in `gentrex extract`. The records hold 298 values that no report states.

The ways to choose pages, each on `google/gemma-4-26B-A4B-it`:

| Way to choose pages | Needed pages kept | Pages kept | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- | --- |
| `questions` | 99.3% | 51.8% | 39.7 | 5046 | 2908084 | 5046 |
| `one_question` | 98.9% | 47.4% | 16.3 | 1682 | 998516 | 1682 |
| `page_extract` | 99.3% | 54.9% | 314.1 | 1682 | 5883044 | 428427 |

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 91.7% | 94.2% | 91.7% | 2 | 22 | 1 |
| `submitter_patient_id` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `lab_accession_number` | 300 | 60.7% | 71.0% | 60.7% | 87 | 0 | 31 |
| `date_of_birth` | 300 | 99.0% | 99.5% | 99.0% | 3 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 98.0% | 98.1% | 97.7% | 1 | 0 | 5 |
| `collection_date` | 300 | 94.3% | 94.4% | 94.3% | 0 | 2 | 15 |
| `received_date` | 300 | 93.3% | 94.3% | 93.3% | 4 | 4 | 12 |
| `test_name` | 300 | 96.7% | 96.7% | 77.7% | 0 | 0 | 10 |
| `test_type` | 300 | 84.0% | 84.0% | 84.0% | 0 | 0 | 48 |
| `test_started_date` | 300 | 98.7% | 96.6% | 98.7% | 0 | 0 | 4 |
| `report_date` | 300 | 92.3% | 91.9% | 92.3% | 0 | 0 | 23 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 93.0% | 93.0% | 56.3% | 0 | 0 | 21 |
| `lab_name` | 300 | 99.0% | 99.0% | 99.0% | 0 | 0 | 3 |
| `genome_build` | 300 | 89.3% | 91.6% | 89.3% | 32 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 99.0% | 99.5% | 99.0% | 3 | 0 | 0 |
| `normalized.collection_date` | 300 | 97.7% | 97.9% | 97.7% | 0 | 2 | 5 |
| `normalized.received_date` | 300 | 97.0% | 98.2% | 97.0% | 4 | 4 | 1 |
| `normalized.test_started_date` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.report_date` | 300 | 96.0% | 95.8% | 96.0% | 0 | 0 | 12 |
| `normalized.specimen_type` | 300 | 99.3% | 99.6% | 99.3% | 2 | 0 | 0 |
| `normalized.overall_result` | 300 | 94.3% | 94.7% | 94.3% | 2 | 0 | 15 |
| `variants.page` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.gene_symbol` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 254 | 98.8% | 99.3% | 98.8% | 3 | 0 | 0 |
| `variants.hgvs_c` | 254 | 97.6% | 98.6% | 97.6% | 0 | 6 | 0 |
| `variants.hgvs_p` | 254 | 100.0% | 100.0% | 94.9% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 254 | 92.5% | 79.1% | 92.5% | 0 | 19 | 0 |
| `variants.chromosomal_position` | 254 | 93.7% | 92.2% | 93.7% | 3 | 13 | 0 |
| `variants.copy_number` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 254 | 89.8% | 91.0% | 87.8% | 0 | 7 | 19 |
| `variants.classification` | 254 | 97.2% | 98.6% | 97.2% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 254 | 99.6% | 99.6% | 99.6% | 0 | 0 | 1 |
| `variants.zygosity` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.parental_origin` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 254 | 92.9% | 93.3% | 92.1% | 0 | 5 | 13 |
| `variants.mode_of_inheritance_raw` | 254 | 96.1% | 96.9% | 94.9% | 6 | 0 | 4 |
| `variants.mode_of_inheritance` | 254 | 97.2% | 98.2% | 97.2% | 6 | 0 | 1 |
| `variants.is_secondary_finding` | 254 | 100.0% | 100.0% | 30.3% | 0 | 0 | 0 |
| `variants.variant_type_raw` | 254 | 65.3% | 62.4% | 65.3% | 0 | 88 | 0 |
| `normalized.variants.hgnc_id` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 254 | 96.9% | 97.8% | 96.9% | 5 | 1 | 2 |
| `patient_phenotypes.present` | 704 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 211 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 76.9% |
| challenge: family_history | 51 | 82.3% |
| challenge: late_page | 52 | 78.8% |
| challenge: missing_values | 52 | 80.8% |
| challenge: negated_features | 51 | 72.5% |
| challenge: similar_ids | 52 | 71.2% |
| challenge: split_table | 49 | 83.7% |
| challenge: unusual_notation | 51 | 74.5% |
| kind: array | 36 | 91.7% |
| kind: carrier | 48 | 79.2% |
| kind: exome | 51 | 78.4% |
| kind: karyotype | 15 | 33.3% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 91.7% |
| kind: repeat | 15 | 33.3% |
| kind: single_gene | 27 | 96.3% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 66.7% |
| lab: carrier-banner | 12 | 75.0% |
| lab: carrier-grid | 12 | 83.3% |
| lab: chart | 12 | 75.0% |
| lab: dx-banner | 17 | 100.0% |
| lab: enterprise | 17 | 0.0% |
| lab: exome-box | 13 | 100.0% |
| lab: exome-findings | 13 | 69.2% |
| lab: findings-grid | 17 | 100.0% |
| lab: genome-card | 13 | 46.2% |
| lab: graybar-panel | 17 | 100.0% |
| lab: karyotype | 15 | 33.3% |
| lab: lis-printout | 12 | 66.7% |
| lab: microarray-printout | 17 | 82.3% |
| lab: one-page | 12 | 91.7% |
| lab: patient-page | 12 | 83.3% |
| lab: results-statement | 18 | 72.2% |
| lab: screen-badge | 12 | 75.0% |
| lab: snp-array | 17 | 100.0% |
| lab: summary-line | 18 | 77.8% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 70.8% |
| laboratory: Aqua Genetics | 60 | 88.3% |
| laboratory: Bronze Clinical Genomics | 60 | 80.0% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 54.8% |
| laboratory: Navy Genomic Laboratory | 24 | 87.5% |
| laboratory: Plum Genetics | 30 | 86.7% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 78.6% |
| pages: 3 | 26 | 69.2% |
| pages: 4 or more | 258 | 77.9% |
| scenario: carrier | 41 | 85.4% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 87.5% |
| scenario: negative | 80 | 66.2% |
| scenario: positive | 92 | 73.9% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 0.0% |
| scenario: vus_only | 43 | 97.7% |
| variants: 0 | 91 | 58.2% |
| variants: 1 | 153 | 86.3% |
| variants: 2 or more | 56 | 83.9% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 168.9 | 0 | 0 | 0 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 39.7 | 5046 | 2908084 | 5046 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 343.6 | 300 | 1361452 | 145804 |
| `gentrex normalize` |  | 48.2 | 0 | 0 | 0 |

The run read 300 PDFs. That is 2001 seconds and 0.51 GPU-hours per 1,000 PDFs.

The model servers took 450 seconds more to start, which these numbers leave out.
