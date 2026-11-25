# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-065654/native`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 76.0% | 71.0% to 80.7% |
| Reports with every value right | 11.3% | 8.0% to 15.3% |
| MRN and date of birth both right | 91.3% | 88.0% to 94.7% |
| Value F1 (micro) | 94.6% | 94.0% to 95.1% |
| Field F1 (macro) | 94.0% | 89.1% to 95.2% |
| Exact-match value F1 | 92.3% | 91.7% to 92.9% |
| Value precision | 94.1% | 93.5% to 94.7% |
| Value recall | 95.0% | 94.4% to 95.6% |
| Variant detection F1 | 87.6% | 83.9% to 90.8% |
| Clinical variant F1 | 85.2% | 80.8% to 89.1% |
| Variant precision | 80.6% | 75.4% to 85.2% |
| Variant recall | 95.9% | 93.2% to 98.1% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 98.0% |
| Pathogenic / likely pathogenic clinical recall | 98.0% |
| Actionable ACMG F1 (P/LP vs. other) | 98.0% |
| Negative-report specificity | 54.9% |
| False-positive variant rate on negative reports | 41.8% |
| Ungrounded hallucination rate | 1.0% |
| Distractor entities copied | 42 |
| ACMG classification macro-F1 | 74.2% |
| Overall result macro-F1 | 95.7% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 3 |
| missed other variant | 8 |
| extra variant | 61 |
| actionable acmg flip | 6 |
| other acmg error | 1 |
| wrong zygosity or cn | 0 |
| wrong result or karyotype | 18 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 254 | 11 | 61 | 80.6% | 95.9% | 87.6% |
| Clinical features, by text | 704 | 54 | 63 | 91.8% | 92.9% | 92.3% |
| Clinical features, by HPO ID | 745 | 13 | 25 | 96.8% | 98.3% | 97.5% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 11 | distractor: 32, hallucination: 29 |
| Clinical features, by text | extract: 54 | hallucination: 53, distractor: 10 |
| Clinical features, by HPO ID | charged earlier: 13 | charged earlier: 23, normalize: 2 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 0 | 0 | 0 |
| `gentrex select` | 0 | 0 | 0 |
| `gentrex extract` | 217 | 216 | 295 |
| `gentrex normalize` | 0 | 13 | 2 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 704 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 11 | 18 | 100.0% | 61.1% |
| `hgvs_invalid` | 315 | 7 | 61 | 14.3% | 1.6% |
| `not_in_pages` | 6147 | 13 | 450 | 61.5% | 1.8% |

A person who looks at every report with a flag looks at 29 of 300 reports, and finds 15 of the 72 reports that count as wrong.

## Pages

The run read 1682 pages and sent 0 of them to OCR. `gentrex select` kept 867 pages. The reports state 8565 values, and 8137 of them are right in the records. Lost were 0 in `gentrex transcribe`, 0 in `gentrex select`, 428 in `gentrex extract`. The records hold 295 values that no report states.

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 92.7% | 94.9% | 92.7% | 2 | 19 | 1 |
| `submitter_patient_id` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `lab_accession_number` | 300 | 61.7% | 72.1% | 61.7% | 87 | 0 | 28 |
| `date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 98.3% | 98.4% | 97.7% | 1 | 0 | 4 |
| `collection_date` | 300 | 93.7% | 93.7% | 93.7% | 0 | 2 | 17 |
| `received_date` | 300 | 93.0% | 93.9% | 93.0% | 4 | 4 | 13 |
| `test_name` | 300 | 96.3% | 96.3% | 77.7% | 0 | 0 | 11 |
| `test_type` | 300 | 83.7% | 83.7% | 83.7% | 0 | 0 | 49 |
| `test_started_date` | 300 | 98.7% | 96.6% | 98.7% | 0 | 0 | 4 |
| `report_date` | 300 | 92.0% | 91.5% | 92.0% | 0 | 0 | 24 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 93.3% | 93.3% | 56.3% | 0 | 0 | 20 |
| `lab_name` | 300 | 99.0% | 99.0% | 99.0% | 0 | 0 | 3 |
| `genome_build` | 300 | 89.0% | 91.3% | 89.0% | 33 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `normalized.collection_date` | 300 | 97.3% | 97.6% | 97.3% | 0 | 2 | 6 |
| `normalized.received_date` | 300 | 97.0% | 98.2% | 97.0% | 4 | 4 | 1 |
| `normalized.test_started_date` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.report_date` | 300 | 96.0% | 95.8% | 96.0% | 0 | 0 | 12 |
| `normalized.specimen_type` | 300 | 99.3% | 99.6% | 99.3% | 2 | 0 | 0 |
| `normalized.overall_result` | 300 | 94.0% | 94.3% | 94.0% | 2 | 0 | 16 |
| `variants.page` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.gene_symbol` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 254 | 99.2% | 99.6% | 99.2% | 2 | 0 | 0 |
| `variants.hgvs_c` | 254 | 97.6% | 98.6% | 97.6% | 0 | 6 | 0 |
| `variants.hgvs_p` | 254 | 100.0% | 100.0% | 94.1% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 254 | 92.9% | 80.0% | 92.9% | 0 | 18 | 0 |
| `variants.chromosomal_position` | 254 | 93.7% | 92.2% | 93.7% | 3 | 13 | 0 |
| `variants.copy_number` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 254 | 89.8% | 91.0% | 87.8% | 0 | 7 | 19 |
| `variants.classification` | 254 | 97.2% | 98.6% | 97.2% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 254 | 99.6% | 99.6% | 99.6% | 0 | 0 | 1 |
| `variants.zygosity` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.parental_origin` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 254 | 92.5% | 92.8% | 91.7% | 0 | 5 | 14 |
| `variants.mode_of_inheritance_raw` | 254 | 95.7% | 96.7% | 94.5% | 7 | 0 | 4 |
| `variants.mode_of_inheritance` | 254 | 96.9% | 98.0% | 96.9% | 7 | 0 | 1 |
| `variants.is_secondary_finding` | 254 | 100.0% | 100.0% | 30.3% | 0 | 0 | 0 |
| `variants.variant_type_raw` | 254 | 65.3% | 62.4% | 65.3% | 0 | 88 | 0 |
| `normalized.variants.hgnc_id` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 254 | 96.9% | 97.8% | 96.9% | 6 | 0 | 2 |
| `patient_phenotypes.present` | 704 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 211 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 75.0% |
| challenge: family_history | 51 | 80.4% |
| challenge: late_page | 52 | 78.8% |
| challenge: missing_values | 52 | 78.8% |
| challenge: negated_features | 51 | 70.6% |
| challenge: similar_ids | 52 | 71.2% |
| challenge: split_table | 49 | 81.6% |
| challenge: unusual_notation | 51 | 68.6% |
| kind: array | 36 | 91.7% |
| kind: carrier | 48 | 79.2% |
| kind: exome | 51 | 78.4% |
| kind: karyotype | 15 | 26.7% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 90.0% |
| kind: repeat | 15 | 26.7% |
| kind: single_gene | 27 | 96.3% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 61.9% |
| lab: carrier-banner | 12 | 75.0% |
| lab: carrier-grid | 12 | 83.3% |
| lab: chart | 12 | 66.7% |
| lab: dx-banner | 17 | 100.0% |
| lab: enterprise | 17 | 0.0% |
| lab: exome-box | 13 | 100.0% |
| lab: exome-findings | 13 | 69.2% |
| lab: findings-grid | 17 | 100.0% |
| lab: genome-card | 13 | 46.2% |
| lab: graybar-panel | 17 | 100.0% |
| lab: karyotype | 15 | 26.7% |
| lab: lis-printout | 12 | 66.7% |
| lab: microarray-printout | 17 | 88.2% |
| lab: one-page | 12 | 91.7% |
| lab: patient-page | 12 | 83.3% |
| lab: results-statement | 18 | 66.7% |
| lab: screen-badge | 12 | 75.0% |
| lab: snp-array | 17 | 94.1% |
| lab: summary-line | 18 | 72.2% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 66.7% |
| laboratory: Aqua Genetics | 60 | 86.7% |
| laboratory: Bronze Clinical Genomics | 60 | 78.3% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 54.8% |
| laboratory: Navy Genomic Laboratory | 24 | 87.5% |
| laboratory: Plum Genetics | 30 | 83.3% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 78.6% |
| pages: 3 | 26 | 65.4% |
| pages: 4 or more | 258 | 76.7% |
| scenario: carrier | 41 | 85.4% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 87.5% |
| scenario: negative | 80 | 62.5% |
| scenario: positive | 92 | 72.8% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 0.0% |
| scenario: vus_only | 43 | 97.7% |
| variants: 0 | 91 | 54.9% |
| variants: 1 | 153 | 86.3% |
| variants: 2 or more | 56 | 82.1% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 166.6 | 0 | 0 | 0 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 39.1 | 5046 | 2908084 | 5046 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 351.8 | 300 | 1359126 | 146011 |
| `gentrex normalize` |  | 48.0 | 0 | 0 | 0 |

The run read 300 PDFs. That is 2018 seconds and 0.52 GPU-hours per 1,000 PDFs.

The model servers took 365 seconds more to start, which these numbers leave out.
