# Scores

300 reports, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261125-074947/fax`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 84.7% | 80.7% to 88.7% |
| Reports with every value right | 10.0% | 6.7% to 13.7% |
| MRN and date of birth both right | 100.0% | 100.0% to 100.0% |
| Value F1 (micro) | 95.0% | 94.5% to 95.5% |
| Field F1 (macro) | 94.4% | 93.2% to 95.3% |
| Exact-match value F1 | 93.1% | 92.5% to 93.6% |
| Value precision | 94.7% | 94.1% to 95.2% |
| Value recall | 95.3% | 94.8% to 95.9% |
| Variant detection F1 | 90.4% | 87.3% to 93.2% |
| Clinical variant F1 | 88.0% | 84.1% to 91.5% |
| Variant precision | 83.9% | 79.2% to 88.2% |
| Variant recall | 98.1% | 96.2% to 99.6% |

## Clinical safety and grounding

| Measure | Value |
| --- | --- |
| Pathogenic / likely pathogenic variant recall | 97.4% |
| Pathogenic / likely pathogenic clinical recall | 97.4% |
| Actionable ACMG F1 (P/LP vs. other) | 97.7% |
| Negative-report specificity | 64.8% |
| False-positive variant rate on negative reports | 35.2% |
| Ungrounded hallucination rate | 0.8% |
| Distractor entities copied | 43 |
| ACMG classification macro-F1 | 98.8% |
| Overall result macro-F1 | 99.3% |

| Clinical error type | Count |
| --- | --- |
| missed pathogenic variant | 4 |
| missed other variant | 1 |
| extra variant | 50 |
| actionable acmg flip | 7 |
| other acmg error | 0 |
| wrong zygosity or cn | 0 |
| wrong result or karyotype | 6 |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 260 | 5 | 50 | 83.9% | 98.1% | 90.4% |
| Clinical features, by text | 704 | 54 | 62 | 91.9% | 92.9% | 92.4% |
| Clinical features, by HPO ID | 743 | 15 | 24 | 96.9% | 98.0% | 97.4% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | extract: 4, transcribe: 1 | distractor: 33, hallucination: 17 |
| Clinical features, by text | extract: 52, transcribe: 2 | hallucination: 52, distractor: 10 |
| Clinical features, by HPO ID | charged earlier: 15 | charged earlier: 23, normalize: 1 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 10 | 13 | 0 |
| `gentrex select` | 3 | 15 | 0 |
| `gentrex extract` | 198 | 166 | 268 |
| `gentrex normalize` | 0 | 2 | 1 |

## Checks

The checks of Gentrex flag values for a person to look at. Precision is the share of the flagged values that are wrong, and recall the share of the wrong values that are flagged.

| Check | Values | Flagged | Wrong | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| `hpo_models_disagree` | 704 | 0 | 0 | n/a | n/a |
| `result_conflict` | 300 | 2 | 6 | 100.0% | 33.3% |
| `hgvs_invalid` | 310 | 6 | 50 | 0.0% | 0.0% |
| `not_in_pages` | 6137 | 5 | 381 | 100.0% | 1.3% |

A person who looks at every report with a flag looks at 12 of 300 reports, and finds 4 of the 46 reports that count as wrong.

## Pages

The run read 1682 pages and sent 1682 of them to OCR. OCR wrote 99.6% of the words of those pages, and 94.1% of its words are on the pages. `gentrex select` kept 839 pages. The reports state 8594 values, and 8193 of them are right in the records. Lost were 23 in `gentrex transcribe`, 18 in `gentrex select`, 360 in `gentrex extract`. The records hold 268 values that no report states.

## Fields

| Field | Values | Accuracy | F1 | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `submitter_patient_id` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `lab_accession_number` | 300 | 61.7% | 72.5% | 61.7% | 90 | 0 | 25 |
| `date_of_birth` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `sex` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 300 | 99.7% | 99.7% | 99.7% | 0 | 0 | 1 |
| `collection_date` | 300 | 96.7% | 96.5% | 96.7% | 0 | 0 | 10 |
| `received_date` | 300 | 95.0% | 96.2% | 95.0% | 6 | 3 | 6 |
| `test_name` | 300 | 99.0% | 99.0% | 88.7% | 0 | 0 | 3 |
| `test_type` | 300 | 83.3% | 83.3% | 83.3% | 0 | 0 | 50 |
| `test_started_date` | 300 | 99.7% | 99.6% | 99.7% | 1 | 0 | 0 |
| `report_date` | 300 | 96.0% | 95.8% | 96.0% | 0 | 0 | 12 |
| `karyotype` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 300 | 90.7% | 90.7% | 57.0% | 0 | 0 | 28 |
| `lab_name` | 300 | 93.0% | 93.5% | 93.0% | 3 | 0 | 18 |
| `genome_build` | 300 | 89.0% | 91.3% | 89.0% | 33 | 0 | 0 |
| `normalized.date_of_birth` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.collection_date` | 300 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.received_date` | 300 | 96.7% | 98.0% | 96.7% | 6 | 3 | 1 |
| `normalized.test_started_date` | 300 | 99.7% | 99.6% | 99.7% | 1 | 0 | 0 |
| `normalized.report_date` | 300 | 97.7% | 97.5% | 97.7% | 0 | 0 | 7 |
| `normalized.specimen_type` | 300 | 99.7% | 99.8% | 99.7% | 1 | 0 | 0 |
| `normalized.overall_result` | 300 | 98.0% | 98.7% | 98.0% | 4 | 0 | 2 |
| `variants.page` | 260 | 91.1% | 91.1% | 91.1% | 0 | 0 | 23 |
| `variants.gene_symbol` | 260 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 260 | 95.4% | 97.3% | 95.4% | 12 | 0 | 0 |
| `variants.hgvs_c` | 260 | 97.7% | 98.6% | 97.7% | 0 | 6 | 0 |
| `variants.hgvs_p` | 260 | 100.0% | 100.0% | 94.6% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 260 | 90.0% | 77.2% | 90.0% | 0 | 26 | 0 |
| `variants.chromosomal_position` | 260 | 94.6% | 93.3% | 94.6% | 0 | 13 | 1 |
| `variants.copy_number` | 260 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 260 | 93.8% | 95.0% | 90.4% | 0 | 7 | 9 |
| `variants.classification` | 260 | 97.3% | 98.6% | 97.3% | 0 | 7 | 0 |
| `variants.zygosity_raw` | 260 | 100.0% | 100.0% | 96.9% | 0 | 0 | 0 |
| `variants.zygosity` | 260 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.parental_origin_raw` | 260 | 98.9% | 76.2% | 98.9% | 0 | 1 | 2 |
| `variants.parental_origin` | 260 | 99.6% | 95.2% | 99.6% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 260 | 95.4% | 96.4% | 95.4% | 0 | 7 | 5 |
| `variants.mode_of_inheritance_raw` | 260 | 99.6% | 99.6% | 99.6% | 0 | 0 | 1 |
| `variants.mode_of_inheritance` | 260 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.is_secondary_finding` | 260 | 100.0% | 100.0% | 29.6% | 0 | 0 | 0 |
| `variants.variant_type_raw` | 260 | 67.3% | 63.2% | 67.3% | 0 | 85 | 0 |
| `normalized.variants.hgnc_id` | 260 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| `normalized.variants.disease_id` | 260 | 98.9% | 99.1% | 98.9% | 2 | 0 | 1 |
| `patient_phenotypes.present` | 704 | 99.6% | 99.8% | 99.6% | 3 | 0 | 0 |
| `normalized.variants.clinvar_variation_id` | 209 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| challenge: distractor_variants | 52 | 90.4% |
| challenge: family_history | 51 | 86.3% |
| challenge: late_page | 52 | 82.7% |
| challenge: missing_values | 52 | 82.7% |
| challenge: negated_features | 51 | 80.4% |
| challenge: similar_ids | 52 | 78.8% |
| challenge: split_table | 49 | 95.9% |
| challenge: unusual_notation | 51 | 82.3% |
| kind: array | 36 | 97.2% |
| kind: carrier | 48 | 89.6% |
| kind: exome | 51 | 100.0% |
| kind: karyotype | 15 | 40.0% |
| kind: methylation | 6 | 66.7% |
| kind: mito | 12 | 100.0% |
| kind: panel | 60 | 96.7% |
| kind: repeat | 15 | 40.0% |
| kind: single_gene | 27 | 96.3% |
| kind: sma | 9 | 0.0% |
| kind: targeted | 21 | 61.9% |
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
| lab: karyotype | 15 | 40.0% |
| lab: lis-printout | 12 | 66.7% |
| lab: microarray-printout | 17 | 94.1% |
| lab: one-page | 12 | 100.0% |
| lab: patient-page | 12 | 100.0% |
| lab: results-statement | 18 | 88.9% |
| lab: screen-badge | 12 | 100.0% |
| lab: snp-array | 17 | 100.0% |
| lab: summary-line | 18 | 83.3% |
| lab: summary-sidebar | 12 | 100.0% |
| lab: teal-banner | 12 | 100.0% |
| laboratory: Apricot Reference Laboratories | 24 | 62.5% |
| laboratory: Aqua Genetics | 60 | 100.0% |
| laboratory: Bronze Clinical Genomics | 60 | 96.7% |
| laboratory: Indigo Genetic Testing | 29 | 93.1% |
| laboratory: Lilac Molecular Laboratory | 73 | 58.9% |
| laboratory: Navy Genomic Laboratory | 24 | 100.0% |
| laboratory: Plum Genetics | 30 | 90.0% |
| pages: 1 | 2 | 100.0% |
| pages: 2 | 14 | 85.7% |
| pages: 3 | 26 | 73.1% |
| pages: 4 or more | 258 | 85.7% |
| scenario: carrier | 41 | 90.2% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 24 | 100.0% |
| scenario: negative | 80 | 73.8% |
| scenario: positive | 92 | 77.2% |
| scenario: secondary_finding | 11 | 100.0% |
| scenario: upd | 7 | 100.0% |
| scenario: vus_only | 43 | 100.0% |
| variants: 0 | 91 | 64.8% |
| variants: 1 | 153 | 92.2% |
| variants: 2 or more | 56 | 96.4% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 812.5 | 1682 | 5298300 | 992634 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 41.0 | 5046 | 3320146 | 5046 |
| `gentrex extract` | google/gemma-4-26B-A4B-it | 352.2 | 300 | 1461853 | 144404 |
| `gentrex normalize` |  | 47.5 | 0 | 0 | 0 |

The run read 300 PDFs. That is 4177 seconds and 1.12 GPU-hours per 1,000 PDFs.

The model servers took 335 seconds more to start, which these numbers leave out.
