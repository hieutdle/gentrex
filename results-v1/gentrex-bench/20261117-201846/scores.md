# Scores

99 reports of the split `dev`, read from `/sc/arion/projects/gen-test-extraction-discovery/gentrex/results/gentrex-bench/20261117-201846/native`. 0 of them have no record.

## Main numbers

| Measure | Value | 95% interval |
| --- | --- | --- |
| Report accuracy | 88.9% | 81.8% to 93.9% |
| MRN and date of birth both right | 77.8% | 69.7% to 85.9% |
| Variant F1 | 96.0% | 92.7% to 98.8% |
| Variant precision | 92.3% | 86.4% to 97.6% |
| Variant recall | 100.0% | 100.0% to 100.0% |

## Variants and clinical features

|  | Matched | Missed | Extra | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Variants | 84 | 0 | 7 | 92.3% | 100.0% | 96.0% |
| Clinical features, by text | 273 | 0 | 21 | 92.9% | 100.0% | 96.3% |
| Clinical features, by HPO ID | 273 | 0 | 21 | 92.9% | 100.0% | 96.3% |

|  | Missed, by command | Extra, by cause |
| --- | --- | --- |
| Variants | none | hallucination: 6, distractor: 1 |
| Clinical features, by text | none | hallucination: 20, distractor: 1 |
| Clinical features, by HPO ID | none | charged earlier: 20, normalize: 1 |

## Where errors come from

| Command | Missed | Wrong | Extra |
| --- | --- | --- | --- |
| `gentrex transcribe` | 0 | 0 | 0 |
| `gentrex select` | 16 | 11 | 0 |
| `gentrex extract` | 40 | 58 | 172 |
| `gentrex normalize` | 6 | 0 | 1 |

## Values not in the pages

`gentrex extract` copied 2082 values and named 56 of them in `not_in_pages`. 5 of those were wrong or extra (8.9%). In all, 173 copied values were wrong or extra, so the check named 2.9% of them.

## Fields

| Field | Values | Accuracy | Exact | Missed | Extra | Wrong |
| --- | --- | --- | --- | --- | --- | --- |
| `mrn` | 99 | 79.8% | 79.8% | 19 | 1 | 0 |
| `submitter_patient_id` | 99 | 74.8% | 74.8% | 1 | 20 | 4 |
| `lab_accession_number` | 99 | 87.9% | 87.9% | 5 | 0 | 7 |
| `date_of_birth` | 99 | 98.0% | 98.0% | 1 | 0 | 1 |
| `sex` | 99 | 100.0% | 100.0% | 0 | 0 | 0 |
| `specimen_type` | 99 | 92.9% | 92.9% | 0 | 3 | 4 |
| `collection_date` | 99 | 100.0% | 100.0% | 0 | 0 | 0 |
| `received_date` | 99 | 91.9% | 91.9% | 8 | 0 | 0 |
| `test_name` | 99 | 85.9% | 85.9% | 0 | 0 | 14 |
| `test_type` | 99 | 93.9% | 93.9% | 0 | 0 | 6 |
| `test_started_date` | 99 | 98.0% | 98.0% | 1 | 1 | 0 |
| `report_date` | 99 | 89.9% | 89.9% | 2 | 0 | 8 |
| `karyotype` | 99 | 100.0% | 100.0% | 0 | 0 | 0 |
| `clinical_indication` | 99 | 98.0% | 78.8% | 0 | 0 | 2 |
| `lab_name` | 99 | 100.0% | 100.0% | 0 | 0 | 0 |
| `genome_build` | 99 | 84.9% | 84.9% | 15 | 0 | 0 |
| `normalized.date_of_birth` | 99 | 97.0% | 97.0% | 2 | 0 | 1 |
| `normalized.collection_date` | 99 | 99.0% | 99.0% | 1 | 0 | 0 |
| `normalized.received_date` | 99 | 90.9% | 90.9% | 9 | 0 | 0 |
| `normalized.test_started_date` | 99 | 98.0% | 98.0% | 1 | 1 | 0 |
| `normalized.report_date` | 99 | 88.9% | 88.9% | 3 | 0 | 8 |
| `normalized.specimen_type` | 99 | 98.0% | 98.0% | 0 | 2 | 0 |
| `normalized.overall_result` | 99 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.page` | 84 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.gene_symbol` | 84 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.transcript` | 84 | 97.6% | 97.6% | 2 | 0 | 0 |
| `variants.hgvs_c` | 84 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.hgvs_p` | 84 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.dna_change_raw` | 84 | 96.4% | 96.4% | 0 | 3 | 0 |
| `variants.chromosomal_position` | 84 | 94.0% | 94.0% | 0 | 5 | 0 |
| `variants.copy_number` | 84 | 100.0% | 100.0% | 0 | 0 | 0 |
| `variants.classification_raw` | 84 | 83.3% | 79.8% | 0 | 3 | 11 |
| `variants.classification` | 84 | 96.4% | 96.4% | 0 | 3 | 0 |
| `variants.zygosity_raw` | 84 | 94.0% | 92.9% | 0 | 2 | 3 |
| `variants.zygosity` | 84 | 97.6% | 97.6% | 0 | 2 | 0 |
| `variants.parental_origin_raw` | 84 | 98.8% | 98.8% | 0 | 1 | 0 |
| `variants.parental_origin` | 84 | 98.8% | 98.8% | 0 | 1 | 0 |
| `variants.associated_phenotype` | 84 | 89.3% | 89.3% | 0 | 4 | 5 |
| `variants.mode_of_inheritance_raw` | 84 | 95.2% | 92.9% | 1 | 0 | 3 |
| `variants.mode_of_inheritance` | 84 | 98.8% | 98.8% | 1 | 0 | 0 |
| `variants.is_secondary_finding` | 84 | 33.3% | 33.3% | 0 | 56 | 0 |
| `variants.variant_type_raw` | 84 | 52.4% | 52.4% | 0 | 39 | 1 |
| `normalized.variants.hgnc_id` | 84 | 98.8% | 98.8% | 1 | 0 | 0 |
| `normalized.variants.disease_id` | 84 | 92.9% | 92.9% | 4 | 1 | 1 |
| `normalized.variants.clinvar_variation_id` | 64 | 98.4% | 98.4% | 1 | 0 | 0 |
| `patient_phenotypes.present` | 273 | 100.0% | 100.0% | 0 | 0 | 0 |

## Groups

| Group | Reports | Report accuracy |
| --- | --- | --- |
| held_out: seen in dev | 99 | 88.9% |
| kind: array | 12 | 100.0% |
| kind: carrier | 16 | 100.0% |
| kind: exome | 16 | 100.0% |
| kind: karyotype | 5 | 20.0% |
| kind: methylation | 2 | 0.0% |
| kind: mito | 4 | 100.0% |
| kind: panel | 20 | 100.0% |
| kind: repeat | 5 | 60.0% |
| kind: single_gene | 9 | 100.0% |
| kind: sma | 3 | 0.0% |
| kind: targeted | 7 | 100.0% |
| lab: carrier-banner | 5 | 100.0% |
| lab: chart | 7 | 100.0% |
| lab: dx-banner | 6 | 100.0% |
| lab: enterprise | 5 | 0.0% |
| lab: exome-box | 5 | 100.0% |
| lab: exome-findings | 5 | 100.0% |
| lab: findings-grid | 6 | 100.0% |
| lab: graybar-panel | 6 | 100.0% |
| lab: karyotype | 5 | 20.0% |
| lab: microarray-printout | 6 | 100.0% |
| lab: one-page | 5 | 100.0% |
| lab: patient-page | 5 | 100.0% |
| lab: results-statement | 6 | 100.0% |
| lab: screen-badge | 5 | 100.0% |
| lab: snp-array | 5 | 100.0% |
| lab: summary-line | 6 | 66.7% |
| lab: summary-sidebar | 6 | 100.0% |
| lab: teal-banner | 5 | 100.0% |
| scenario: carrier | 12 | 83.3% |
| scenario: indeterminate | 2 | 100.0% |
| scenario: mixed | 5 | 100.0% |
| scenario: negative | 24 | 95.8% |
| scenario: positive | 41 | 80.5% |
| scenario: secondary_finding | 2 | 100.0% |
| scenario: vus_only | 13 | 100.0% |
| tag: ambiguous_specimen | 8 | 87.5% |
| tag: boilerplate_variant_notation | 8 | 87.5% |
| tag: explicitly_unavailable | 8 | 75.0% |
| tag: family_history_distractor | 8 | 100.0% |
| tag: gene_list_distractor | 7 | 100.0% |
| tag: late_page_evidence | 8 | 87.5% |
| tag: legacy_gene_symbol | 8 | 100.0% |
| tag: missing_optional_fields | 8 | 75.0% |
| tag: multiple_patient_ids | 4 | 0.0% |
| tag: multiple_variants | 8 | 100.0% |
| tag: negated_or_uncertain_phenotypes | 8 | 100.0% |
| tag: nonstandard_hgvs | 7 | 100.0% |
| tag: provided_phenotype_page | 8 | 100.0% |
| tag: repeated_variant | 8 | 100.0% |
| tag: similar_identifiers | 8 | 87.5% |
| tag: table_split_across_pages | 8 | 100.0% |
| tag: trio_columns | 7 | 100.0% |
| tag: unusual_date_format | 9 | 77.8% |
| variants: 0 | 30 | 76.7% |
| variants: 1 | 54 | 92.6% |
| variants: 2 or more | 15 | 100.0% |

## Speed and cost

| Command | Model | Seconds | Requests | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- |
| `gentrex transcribe` | lightonai/LightOnOCR-3-4B | 28.3 | 0 | 0 | 0 |
| `gentrex select` | google/gemma-4-26B-A4B-it | 12.6 | 574 | 336135 | 574 |
| `gentrex extract` | google/gemma-4-31B-it | 219.9 | 99 | 376410 | 46583 |
| `gentrex normalize` |  | 42.1 | 0 | 0 | 0 |

The run read 99 PDFs. That is 3060 seconds and 1.35 GPU-hours per 1,000 PDFs.

The model servers took 670 seconds more to start, which these numbers leave out.
