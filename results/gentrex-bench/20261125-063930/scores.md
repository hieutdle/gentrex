# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-063930/native`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 78.0% | 73.3% to 82.7% |
| Reports with every value right | 11.7% | 8.3% to 15.7% |
| MRN and date of birth both right | 90.3% | 87.0% to 93.7% |
| Value F1 (micro) | 94.6% | 94.1% to 95.1% |
| Field F1 (macro) | 94.0% | 89.1% to 95.2% |
| Exact-match value F1 | 92.4% | 91.8% to 92.9% |
| Value precision | 94.2% | 93.6% to 94.7% |
| Value recall | 95.0% | 94.5% to 95.6% |
| Variant detection F1 | 88.3% | 84.7% to 91.5% |
| Clinical variant F1 | 85.9% | 81.6% to 89.8% |
| Variant precision | 81.9% | 77.0% to 86.4% |
| Variant recall | 95.9% | 93.2% to 98.1% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 98.0% |
| Pathogenic / likely pathogenic clinical recall | 98.0% |
| Actionable ACMG F1 (P/LP vs. other) | 98.0% |
| Negative-report specificity | 60.4% |
| False-positive variant rate on negative reports | 36.3% |
| Ungrounded hallucination rate | 1.1% |
| Distractor entities copied | 37 |
| ACMG classification macro-F1 | 74.2% |
| Overall result macro-F1 | 95.9% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 3 |
| missed other variant | 8 |
| extra variant | 56 |
| actionable acmg flip | 6 |
| other acmg error | 1 |
| wrong zygosity or cn | 0 |
| wrong result or karyotype | 17 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 254 | 11 | 56 | 81.9% | 95.9% | 88.3% |
| Clinical features, by text | 701 | 57 | 64 | 91.6% | 92.5% | 92.1% |
| Clinical features, by HPO ID | 742 | 16 | 26 | 96.6% | 97.9% | 97.2% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 11 | distractor: 27, hallucination: 29 |
| Clinical features, by text | extract: 57 | hallucination: 54, distractor: 10 |
| Clinical features, by HPO ID | charged earlier: 16 | charged earlier: 24, normalize: 2 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 0 | 0 | 0 |
| `gentrex select` | 0 | 0 | 0 |
| `gentrex extract` | 217 | 214 | 294 |
| `gentrex normalize` | 0 | 12 | 2 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 701 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 10 | 17 | 100.0% | 58.8% |
| `hgvs_invalid` | 310 | 8 | 56 | 25.0% | 3.6% |
| `not_in_pages` | 6147 | 13 | 450 | 61.5% | 1.8% |

A person who looks at every report with a flag looks at 29 of 300 reports, and finds 14 of the 66 reports that count as wrong.

## Pages

The run read 1682 pages and sent 0 of them to OCR. `gentrex select` kept 865 pages. The reports state 8562 values, and 8136 of them are right in the records. Lost were 0 in `gentrex transcribe`, 0 in `gentrex select`, 426 in `gentrex extract`. The records hold 294 values that no report states.

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 91.7% | 94.2% | 91.7% | 2 | 22 | 1 |
| `submitter_patient_id` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `lab_accession_number` | 300 | 62.0% | 72.0% | 62.0% | 83 | 0 | 31 |
| `date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 98.3% | 98.3% | 98.0% | 0 | 0 | 5 |
| `collection_date` | 300 | 94.0% | 94.1% | 94.0% | 0 | 2 | 16 |
| `received_date` | 300 | 93.0% | 93.9% | 93.0% | 4 | 4 | 13 |
| `test_name` | 300 | 96.3% | 96.3% | 78.0% | 0 | 0 | 11 |
| `test_type` | 300 | 84.7% | 84.7% | 84.7% | 0 | 0 | 46 |
| `test_started_date` | 300 | 98.3% | 95.7% | 98.3% | 0 | 0 | 5 |
| `report_date` | 300 | 92.0% | 91.5% | 92.0% | 0 | 0 | 24 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 93.3% | 93.3% | 56.3% | 0 | 0 | 20 |
| `lab_name` | 300 | 99.0% | 99.0% | 99.0% | 0 | 0 | 3 |
| `genome_build` | 300 | 88.7% | 91.0% | 88.7% | 34 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 98.7% | 99.3% | 98.7% | 4 | 0 | 0 |
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
| `variants.hgvs_p` | 254 | 100.0% | 100.0% | 94.1% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 254 | 92.5% | 79.1% | 92.5% | 0 | 19 | 0 |
| `variants.chromosomal_position` | 254 | 93.7% | 92.2% | 93.7% | 3 | 13 | 0 |
| `variants.copy_number` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 254 | 90.5% | 91.8% | 88.6% | 0 | 7 | 17 |
| `variants.classification` | 254 | 97.2% | 98.6% | 97.2% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 254 | 99.6% | 99.6% | 99.6% | 0 | 0 | 1 |
| `variants.zygosity` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.parental_origin` | 254 | 99.6% | 85.7% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 254 | 92.1% | 92.6% | 91.3% | 0 | 6 | 14 |
| `variants.mode_of_inheritance_raw` | 254 | 96.1% | 97.1% | 94.9% | 7 | 0 | 3 |
| `variants.mode_of_inheritance` | 254 | 96.9% | 98.0% | 96.9% | 7 | 0 | 1 |
| `variants.is_secondary_finding` | 254 | 100.0% | 100.0% | 30.3% | 0 | 0 | 0 |
| `variants.variant_type_raw` | 254 | 66.1% | 62.9% | 66.1% | 0 | 86 | 0 |
| `normalized.variants.hgnc_id` | 254 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 254 | 96.9% | 97.8% | 96.9% | 6 | 0 | 2 |
| `patient_phenotypes.present` | 701 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 211 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 76.9% |
| challenge: family_history | 51 | 82.3% |
| challenge: late_page | 52 | 78.8% |
| challenge: missing_values | 52 | 84.6% |
| challenge: negated_features | 51 | 72.5% |
| challenge: similar_ids | 52 | 71.2% |
| challenge: split_table | 49 | 83.7% |
| challenge: unusual_notation | 51 | 72.5% |
| kind: array | 36 | 94.4% |
| kind: carrier | 48 | 81.2% |
| kind: exome | 51 | 78.4% |
| kind: karyotype | 15 | 26.7% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 91.7% |
| kind: repeat | 15 | 33.3% |
| kind: single_gene | 27 | 96.3% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 71.4% |
| lab: carrier-banner | 12 | 83.3% |
| lab: carrier-grid | 12 | 83.3% |
| lab: chart | 12 | 75.0% |
| lab: dx-banner | 17 | 100.0% |
| lab: enterprise | 17 | 0.0% |
| lab: exome-box | 13 | 100.0% |
| lab: exome-findings | 13 | 69.2% |
| lab: findings-grid | 17 | 100.0% |
| lab: genome-card | 13 | 46.2% |
| lab: graybar-panel | 17 | 100.0% |
| lab: karyotype | 15 | 26.7% |
| lab: lis-printout | 12 | 75.0% |
| lab: microarray-printout | 17 | 88.2% |
| lab: one-page | 12 | 91.7% |
| lab: patient-page | 12 | 83.3% |
| lab: results-statement | 18 | 72.2% |
| lab: screen-badge | 12 | 75.0% |
| lab: snp-array | 17 | 100.0% |
| lab: summary-line | 18 | 77.8% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 75.0% |
| laboratory: Aqua Genetics | 60 | 88.3% |
| laboratory: Bronze Clinical Genomics | 60 | 80.0% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 56.2% |
| laboratory: Navy Genomic Laboratory | 24 | 87.5% |
| laboratory: Plum Genetics | 30 | 86.7% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 78.6% |
| pages: 3 | 26 | 73.1% |
| pages: 4 or more | 258 | 78.3% |
| scenario: carrier | 41 | 85.4% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 87.5% |
| scenario: negative | 80 | 68.8% |
| scenario: positive | 92 | 73.9% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 0.0% |
| scenario: vus_only | 43 | 97.7% |
| variants: 0 | 91 | 60.4% |
| variants: 1 | 153 | 86.3% |
| variants: 2 or more | 56 | 83.9% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 167.6 | 0 | 0 | 0 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 39.9 | 5046 | 2908084 | 5046 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 350.3 | 300 | 1357891 | 145178 |
| `gentrex normalize` |  | 48.1 | 0 | 0 | 0 |

The run read 300 PDFs. That is 2020 seconds and 0.52 GPU-hours per 1,000 PDFs.

The model servers took 365 seconds more to start, which these numbers leave out.
