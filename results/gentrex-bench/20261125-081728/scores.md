# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-081728/native`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 75.0% | 70.0% to 80.0% |
| Reports with every value right | 12.0% | 8.7% to 16.0% |
| MRN and date of birth both right | 82.0% | 77.7% to 86.3% |
| Value F1 (micro) | 94.3% | 93.7% to 94.8% |
| Field F1 (macro) | 93.4% | 88.4% to 94.6% |
| Exact-match value F1 | 92.1% | 91.5% to 92.7% |
| Value precision | 93.5% | 92.9% to 94.1% |
| Value recall | 95.0% | 94.5% to 95.6% |
| Variant detection F1 | 87.1% | 83.3% to 90.4% |
| Clinical variant F1 | 84.3% | 79.9% to 88.4% |
| Variant precision | 80.1% | 74.8% to 84.7% |
| Variant recall | 95.5% | 92.7% to 97.8% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 97.4% |
| Pathogenic / likely pathogenic clinical recall | 96.7% |
| Actionable ACMG F1 (P/LP vs. other) | 98.0% |
| Negative-report specificity | 54.9% |
| False-positive variant rate on negative reports | 41.8% |
| Ungrounded hallucination rate | 1.0% |
| Distractor entities copied | 47 |
| ACMG classification macro-F1 | 74.2% |
| Overall result macro-F1 | 95.5% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 4 |
| missed other variant | 8 |
| extra variant | 63 |
| actionable acmg flip | 6 |
| other acmg error | 1 |
| wrong zygosity or cn | 1 |
| wrong result or karyotype | 19 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 253 | 12 | 63 | 80.1% | 95.5% | 87.1% |
| Clinical features, by text | 705 | 53 | 62 | 91.9% | 93.0% | 92.5% |
| Clinical features, by HPO ID | 745 | 13 | 26 | 96.6% | 98.3% | 97.5% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 12 | distractor: 35, hallucination: 28 |
| Clinical features, by text | extract: 53 | hallucination: 50, distractor: 12 |
| Clinical features, by HPO ID | charged earlier: 13 | charged earlier: 23, normalize: 3 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 0 | 0 | 0 |
| `gentrex select` | 0 | 0 | 0 |
| `gentrex extract` | 196 | 233 | 337 |
| `gentrex normalize` | 0 | 14 | 3 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 705 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 12 | 19 | 100.0% | 63.2% |
| `hgvs_invalid` | 316 | 6 | 63 | 0.0% | 0.0% |
| `not_in_pages` | 6173 | 16 | 506 | 81.2% | 2.6% |

A person who looks at every report with a flag looks at 31 of 300 reports, and finds 16 of the 75 reports that count as wrong.

## Pages

The run read 1682 pages and sent 0 of them to OCR. The reports state 8555 values, and 8131 of them are right in the records. Lost were 0 in `gentrex transcribe`, 0 in `gentrex select`, 424 in `gentrex extract`. The records hold 337 values that no report states.

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 83.3% | 89.4% | 83.3% | 6 | 44 | 0 |
| `submitter_patient_id` | 300 | 99.7% | 97.1% | 99.7% | 0 | 1 | 0 |
| `lab_accession_number` | 300 | 60.0% | 70.2% | 60.0% | 87 | 0 | 33 |
| `date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 98.7% | 98.8% | 97.7% | 1 | 0 | 3 |
| `collection_date` | 300 | 93.3% | 93.7% | 93.3% | 1 | 3 | 16 |
| `received_date` | 300 | 92.7% | 93.4% | 92.7% | 3 | 4 | 15 |
| `test_name` | 300 | 93.7% | 93.7% | 76.3% | 0 | 0 | 19 |
| `test_type` | 300 | 83.3% | 83.3% | 83.3% | 0 | 0 | 50 |
| `test_started_date` | 300 | 96.7% | 92.6% | 96.7% | 3 | 0 | 7 |
| `report_date` | 300 | 92.0% | 91.5% | 92.0% | 0 | 0 | 24 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 92.7% | 92.7% | 56.0% | 0 | 0 | 22 |
| `lab_name` | 300 | 99.3% | 99.3% | 99.3% | 0 | 0 | 2 |
| `genome_build` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `normalized.collection_date` | 300 | 97.0% | 97.6% | 97.0% | 1 | 3 | 5 |
| `normalized.received_date` | 300 | 96.7% | 97.7% | 96.7% | 3 | 4 | 3 |
| `normalized.test_started_date` | 300 | 99.0% | 98.7% | 99.0% | 3 | 0 | 0 |
| `normalized.report_date` | 300 | 96.0% | 95.8% | 96.0% | 0 | 0 | 12 |
| `normalized.specimen_type` | 300 | 99.7% | 99.8% | 99.7% | 1 | 0 | 0 |
| `normalized.overall_result` | 300 | 93.7% | 94.0% | 93.7% | 2 | 0 | 17 |
| `variants.page` | 253 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.gene_symbol` | 253 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 253 | 98.8% | 99.3% | 98.8% | 3 | 0 | 0 |
| `variants.hgvs_c` | 253 | 97.6% | 98.6% | 97.6% | 0 | 6 | 0 |
| `variants.hgvs_p` | 253 | 100.0% | 100.0% | 95.3% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 253 | 89.7% | 73.5% | 89.7% | 0 | 26 | 0 |
| `variants.chromosomal_position` | 253 | 94.5% | 93.2% | 94.5% | 1 | 13 | 0 |
| `variants.copy_number` | 253 | 99.6% | 97.0% | 99.6% | 0 | 0 | 1 |
| `variants.classification_raw` | 253 | 88.9% | 90.2% | 87.8% | 0 | 7 | 21 |
| `variants.classification` | 253 | 97.2% | 98.6% | 97.2% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 253 | 99.6% | 99.8% | 99.6% | 0 | 1 | 0 |
| `variants.zygosity` | 253 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 253 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.parental_origin` | 253 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 253 | 91.7% | 92.6% | 90.9% | 0 | 8 | 13 |
| `variants.mode_of_inheritance_raw` | 253 | 95.3% | 96.9% | 94.1% | 10 | 0 | 2 |
| `variants.mode_of_inheritance` | 253 | 95.7% | 97.3% | 95.7% | 10 | 0 | 1 |
| `variants.is_secondary_finding` | 253 | 99.6% | 98.7% | 30.4% | 0 | 0 | 1 |
| `variants.variant_type_raw` | 253 | 64.4% | 61.9% | 64.4% | 0 | 90 | 0 |
| `normalized.variants.hgnc_id` | 253 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 253 | 96.4% | 97.5% | 96.4% | 6 | 1 | 2 |
| `patient_phenotypes.present` | 705 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 210 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 71.2% |
| challenge: family_history | 51 | 82.3% |
| challenge: late_page | 52 | 80.8% |
| challenge: missing_values | 52 | 76.9% |
| challenge: negated_features | 51 | 68.6% |
| challenge: similar_ids | 52 | 69.2% |
| challenge: split_table | 49 | 79.6% |
| challenge: unusual_notation | 51 | 70.6% |
| kind: array | 36 | 75.0% |
| kind: carrier | 48 | 77.1% |
| kind: exome | 51 | 76.5% |
| kind: karyotype | 15 | 33.3% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 90.0% |
| kind: repeat | 15 | 26.7% |
| kind: single_gene | 27 | 96.3% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 81.0% |
| lab: carrier-banner | 12 | 75.0% |
| lab: carrier-grid | 12 | 83.3% |
| lab: chart | 12 | 100.0% |
| lab: dx-banner | 17 | 100.0% |
| lab: enterprise | 17 | 0.0% |
| lab: exome-box | 13 | 100.0% |
| lab: exome-findings | 13 | 61.5% |
| lab: findings-grid | 17 | 100.0% |
| lab: genome-card | 13 | 46.2% |
| lab: graybar-panel | 17 | 100.0% |
| lab: karyotype | 15 | 33.3% |
| lab: lis-printout | 12 | 66.7% |
| lab: microarray-printout | 17 | 58.8% |
| lab: one-page | 12 | 91.7% |
| lab: patient-page | 12 | 75.0% |
| lab: results-statement | 18 | 66.7% |
| lab: screen-badge | 12 | 75.0% |
| lab: snp-array | 17 | 88.2% |
| lab: summary-line | 18 | 72.2% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 83.3% |
| laboratory: Aqua Genetics | 60 | 85.0% |
| laboratory: Bronze Clinical Genomics | 60 | 76.7% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 49.3% |
| laboratory: Navy Genomic Laboratory | 24 | 83.3% |
| laboratory: Plum Genetics | 30 | 83.3% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 78.6% |
| pages: 3 | 26 | 65.4% |
| pages: 4 or more | 258 | 75.6% |
| scenario: carrier | 41 | 82.9% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 83.3% |
| scenario: negative | 80 | 62.5% |
| scenario: positive | 92 | 71.7% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 0.0% |
| scenario: vus_only | 43 | 97.7% |
| variants: 0 | 91 | 54.9% |
| variants: 1 | 153 | 85.0% |
| variants: 2 or more | 56 | 80.4% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 167.3 | 0 | 0 | 0 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 382.8 | 300 | 1748104 | 146619 |
| `gentrex normalize` |  | 47.7 | 0 | 0 | 0 |

The run read 300 PDFs. That is 1993 seconds and 0.51 GPU-hours per 1,000 PDFs.

The model servers took 325 seconds more to start, which these numbers leave out.
