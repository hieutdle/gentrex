# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-071422/scan`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 85.0% | 81.0% to 88.7% |
| Reports with every value right | 8.7% | 5.7% to 12.0% |
| MRN and date of birth both right | 100.0% | 100.0% to 100.0% |
| Value F1 (micro) | 95.1% | 94.6% to 95.6% |
| Field F1 (macro) | 94.5% | 93.3% to 95.3% |
| Exact-match value F1 | 93.2% | 92.7% to 93.7% |
| Value precision | 94.7% | 94.1% to 95.2% |
| Value recall | 95.5% | 95.0% to 96.0% |
| Variant detection F1 | 90.5% | 87.4% to 93.2% |
| Clinical variant F1 | 88.0% | 84.1% to 91.5% |
| Variant precision | 83.7% | 79.0% to 88.1% |
| Variant recall | 98.5% | 96.9% to 99.6% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 98.0% |
| Pathogenic / likely pathogenic clinical recall | 98.0% |
| Actionable ACMG F1 (P/LP vs. other) | 98.0% |
| Negative-report specificity | 62.6% |
| False-positive variant rate on negative reports | 37.4% |
| Ungrounded hallucination rate | 0.9% |
| Distractor entities copied | 43 |
| ACMG classification macro-F1 | 74.2% |
| Overall result macro-F1 | 99.7% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 3 |
| missed other variant | 1 |
| extra variant | 51 |
| actionable acmg flip | 6 |
| other acmg error | 1 |
| wrong zygosity or cn | 0 |
| wrong result or karyotype | 4 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 261 | 4 | 51 | 83.7% | 98.5% | 90.5% |
| Clinical features, by text | 704 | 54 | 62 | 91.9% | 92.9% | 92.4% |
| Clinical features, by HPO ID | 744 | 14 | 23 | 97.0% | 98.2% | 97.6% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 4 | distractor: 33, hallucination: 18 |
| Clinical features, by text | extract: 52, transcribe: 2 | hallucination: 52, distractor: 10 |
| Clinical features, by HPO ID | charged earlier: 14 | charged earlier: 22, normalize: 1 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 3 | 2 | 0 |
| `gentrex select` | 1 | 15 | 0 |
| `gentrex extract` | 197 | 174 | 269 |
| `gentrex normalize` | 0 | 0 | 1 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 704 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 0 | 4 | n/a | 0.0% |
| `hgvs_invalid` | 312 | 6 | 51 | 0.0% | 0.0% |
| `not_in_pages` | 6152 | 11 | 385 | 81.8% | 2.3% |

A person who looks at every report with a flag looks at 15 of 300 reports, and finds 0 of the 45 reports that count as wrong.

## Pages

The run read 1682 pages and sent 1682 of them to OCR. OCR wrote 99.7% of the words of those pages, and 92.8% of its words are on the pages. `gentrex select` kept 841 pages. The reports state 8606 values, and 8218 of them are right in the records. Lost were 5 in `gentrex transcribe`, 16 in `gentrex select`, 367 in `gentrex extract`. The records hold 269 values that no report states.

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `submitter_patient_id` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `lab_accession_number` | 300 | 61.7% | 72.4% | 61.7% | 89 | 0 | 26 |
| `date_of_birth` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `collection_date` | 300 | 96.3% | 96.2% | 96.3% | 0 | 0 | 11 |
| `received_date` | 300 | 95.3% | 95.4% | 95.3% | 0 | 2 | 12 |
| `test_name` | 300 | 99.7% | 99.7% | 89.7% | 0 | 0 | 1 |
| `test_type` | 300 | 83.7% | 83.7% | 83.7% | 0 | 0 | 49 |
| `test_started_date` | 300 | 99.7% | 99.6% | 99.7% | 1 | 0 | 0 |
| `report_date` | 300 | 96.0% | 95.8% | 96.0% | 0 | 0 | 12 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 90.7% | 90.7% | 56.3% | 0 | 0 | 28 |
| `lab_name` | 300 | 94.0% | 94.3% | 94.0% | 2 | 0 | 16 |
| `genome_build` | 300 | 89.3% | 91.6% | 89.3% | 32 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.collection_date` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.received_date` | 300 | 99.3% | 99.6% | 99.3% | 0 | 2 | 0 |
| `normalized.test_started_date` | 300 | 99.7% | 99.6% | 99.7% | 1 | 0 | 0 |
| `normalized.report_date` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.specimen_type` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.overall_result` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `variants.page` | 261 | 93.1% | 93.1% | 93.1% | 0 | 0 | 18 |
| `variants.gene_symbol` | 261 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 261 | 95.0% | 97.1% | 95.0% | 13 | 0 | 0 |
| `variants.hgvs_c` | 261 | 97.7% | 98.6% | 97.7% | 0 | 6 | 0 |
| `variants.hgvs_p` | 261 | 100.0% | 100.0% | 94.6% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 261 | 90.0% | 77.2% | 90.0% | 0 | 26 | 0 |
| `variants.chromosomal_position` | 261 | 94.2% | 92.4% | 94.2% | 0 | 13 | 2 |
| `variants.copy_number` | 261 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 261 | 94.2% | 95.4% | 90.0% | 0 | 7 | 8 |
| `variants.classification` | 261 | 97.3% | 98.6% | 97.3% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 261 | 100.0% | 100.0% | 97.7% | 0 | 0 | 0 |
| `variants.zygosity` | 261 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 261 | 98.9% | 76.2% | 98.9% | 0 | 1 | 2 |
| `variants.parental_origin` | 261 | 99.6% | 95.2% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 261 | 94.6% | 95.8% | 94.6% | 0 | 8 | 6 |
| `variants.mode_of_inheritance_raw` | 261 | 99.6% | 99.8% | 99.6% | 1 | 0 | 0 |
| `variants.mode_of_inheritance` | 261 | 99.6% | 99.8% | 99.6% | 1 | 0 | 0 |
| `variants.is_secondary_finding` | 261 | 100.0% | 100.0% | 29.5% | 0 | 0 | 0 |
| `variants.variant_type_raw` | 261 | 67.4% | 63.2% | 67.4% | 0 | 85 | 0 |
| `normalized.variants.hgnc_id` | 261 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 261 | 98.5% | 98.7% | 98.5% | 2 | 0 | 2 |
| `patient_phenotypes.present` | 704 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 210 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 90.4% |
| challenge: family_history | 51 | 88.2% |
| challenge: late_page | 52 | 78.8% |
| challenge: missing_values | 52 | 84.6% |
| challenge: negated_features | 51 | 86.3% |
| challenge: similar_ids | 52 | 76.9% |
| challenge: split_table | 49 | 100.0% |
| challenge: unusual_notation | 51 | 82.3% |
| kind: array | 36 | 97.2% |
| kind: carrier | 48 | 89.6% |
| kind: exome | 51 | 100.0% |
| kind: karyotype | 15 | 33.3% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 100.0% |
| kind: repeat | 15 | 40.0% |
| kind: single_gene | 27 | 100.0% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 57.1% |
| lab: carrier-banner | 12 | 75.0% |
| lab: carrier-grid | 12 | 83.3% |
| lab: chart | 12 | 58.3% |
| lab: dx-banner | 17 | 100.0% |
| lab: enterprise | 17 | 0.0% |
| lab: exome-box | 13 | 100.0% |
| lab: exome-findings | 13 | 100.0% |
| lab: findings-grid | 17 | 100.0% |
| lab: genome-card | 13 | 100.0% |
| lab: graybar-panel | 17 | 100.0% |
| lab: karyotype | 15 | 33.3% |
| lab: lis-printout | 12 | 66.7% |
| lab: microarray-printout | 17 | 94.1% |
| lab: one-page | 12 | 100.0% |
| lab: patient-page | 12 | 100.0% |
| lab: results-statement | 18 | 100.0% |
| lab: screen-badge | 12 | 100.0% |
| lab: snp-array | 17 | 100.0% |
| lab: summary-line | 18 | 83.3% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 62.5% |
| laboratory: Aqua Genetics | 60 | 100.0% |
| laboratory: Bronze Clinical Genomics | 60 | 100.0% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 57.5% |
| laboratory: Navy Genomic Laboratory | 24 | 100.0% |
| laboratory: Plum Genetics | 30 | 90.0% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 85.7% |
| pages: 3 | 26 | 73.1% |
| pages: 4 or more | 258 | 86.1% |
| scenario: carrier | 41 | 90.2% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 100.0% |
| scenario: negative | 80 | 71.2% |
| scenario: positive | 92 | 80.4% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 100.0% |
| scenario: vus_only | 43 | 100.0% |
| variants: 0 | 91 | 62.6% |
| variants: 1 | 153 | 92.8% |
| variants: 2 or more | 56 | 100.0% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 1236.4 | 1682 | 5298300 | 1016783 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 41.4 | 5046 | 3394171 | 5046 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 358.0 | 300 | 1487512 | 144527 |
| `gentrex normalize` |  | 47.3 | 0 | 0 | 0 |

The run read 300 PDFs. That is 5610 seconds and 1.51 GPU-hours per 1,000 PDFs.

The model servers took 360 seconds more to start, which these numbers leave out.
