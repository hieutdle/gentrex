# Changelog

## 0.1.0

The first release.

- `gentrex transcribe` reads the text of every page of the PDF reports, with
  OCR for scanned pages.
- `gentrex select` keeps the pages with the result or the patient's clinical
  features.
- `gentrex extract` turns the kept pages of each report into one record.
- `gentrex normalize` adds ISO dates, categories for the specimen and the
  result, HGNC IDs for genes, MONDO IDs for diseases and HPO terms for
  clinical features.
- `gentrex load` writes the records into SQLite, PostgreSQL or MySQL.
- `gentrex export phenopackets` writes one GA4GH Phenopacket per patient.
  With `--pseudonymize`, it replaces the patient keys and file names with
  keyed pseudonyms, for sharing.
- `gentrex export omop` writes the records into an OMOP CDM database.
  `gentrex export omop-extended` does the same and adds extension tables.
- `gentrex export fhir` writes one FHIR® Bundle per report, following HL7's
  Genomics Reporting Implementation Guide.
- `--retry` makes `gentrex transcribe`, `gentrex select` and
  `gentrex extract` redo only the pages and reports that failed in an earlier
  run.
- Each run folder's `run.yaml` contains the Gentrex version and git commit.
  When the run ends, it also gets the run's time and the requests and tokens
  of its model server.
- `gentrex transcribe` also sends pages to OCR that have some text but are
  mostly images, or that draw their text as outlines.
- `gentrex extract` also reads copy-number changes, repeat expansions,
  uniparental disomies and karyotypes. The record has three fields for them,
  `karyotype` and `genome_build` for the report and `copy_number` for each
  variant, and `test_type` can be `karyotype`. `mrn` also takes a national
  patient number, such as the NHS number, when a report gives no hospital
  number.
- `gentrex normalize` reads the results of karyotypes and arrays, as in
  "Normal male karyotype" or "ABNORMAL MICROARRAY RESULT". It reads
  "POSITIVE: CARRIER", and "POSITIVE" on a carrier screen, as carrier.
  "Indeterminate" counts as inconclusive. Dates printed like "18 March 1995"
  or "18 Mar 1995" are read too.
- `gentrex load` stores the three fields in version 3 of its tables.
- The exports carry the three fields. A Phenopacket gets the karyotypic sex,
  array results as ISCN expressions and copy-number gains and losses. A FHIR
  Bundle gets the karyotype and the IG's components for ISCN, copy number and
  genome build. `gentrex export omop-extended` keeps them in its extension
  tables.
- `--settings` names a YAML file of your own with the settings that differ
  from the defaults, so that the default file stays as it is.
- `gentrex extract` names the copied values that it can't find in the text
  of the report's pages, in `not_in_pages`.
- `gentrex normalize` checks each c. and p. change against the HGVS syntax
  (`hgvs_c_status`, `hgvs_p_status`). With ClinVar's `variant_summary` file,
  it also gives each variant its ClinVar ID (`clinvar_variation_id`,
  `clinvar_status`).
- `gentrex normalize` reads dates with a time of day or a two-digit year,
  and a date such as 25/03/2020, where 25 can only be the day. With
  `normalize.day_first`, it reads 03/04/2020 as April 3.
- `gentrex run` runs `gentrex transcribe`, `gentrex select`,
  `gentrex extract` and `gentrex normalize` in a row, and starts and stops
  the model server of each with a script that you name with `--serve`.
- `--schema` names an extraction schema of your own for `gentrex extract`.
- `gentrex extract` sets each variant's `page` to the first page whose text
  has its DNA change. The model's page stays where no page has it.
- With ClinVar's file, `gentrex normalize` compares each protein change with
  the one in ClinVar's name of the variant (`clinvar_hgvs_p`,
  `clinvar_hgvs_p_status`).
- `gentrex load` stores the HGVS statuses, the ClinVar ID and ClinVar's
  protein change in version 4 of its tables. `gentrex export omop-extended`
  keeps them in `genomic_variant`.
- The FHIR Bundles and the Phenopackets carry the ClinVar ID. Both take a
  c. change as an HGVS expression only if `gentrex normalize` didn't mark it
  `invalid`.
- `evaluation/mondo_normalization.py` measures the MONDO matching of
  `gentrex normalize` on ClinVar's condition names.
- The scores of a benchmark run with `--serve` record how long each model
  server took to start.
- `gentrex extract` records how long the model took for each report and the
  tokens of its answer, as `seconds`, `prompt_tokens` and
  `completion_tokens` in `extractions.jsonl`.
- The benchmark's scorer adds the value F1, the share of reports with every
  value right, the F1 of every field, how many stated values each command
  lost, the share of the words of scanned pages that OCR wrote, and the
  report accuracy by number of pages.
- The benchmark's scorer tells where each wrong value comes from, counts how
  each category was written, scores each kind of variant and each check
  that flags values for a person, and finds the pages that `gentrex select`
  must keep. It also scores each command on what the command before gave
  it: the pages that `gentrex select` kept and what other thresholds would
  keep, the values that reached `gentrex extract`, the standard values given
  a right source, and the HPO terms at the first place and among the five
  candidates. `--label` names a run's setup, and `score.py --list` lists the
  scored runs. A clinical feature without an HPO term no longer also counts
  as an extra term.
- The benchmark generator records each attempt at a report in
  `attempts.jsonl`, the kind of each variant in the truth files, and the
  date and commit of the sampling in `manifest.json`.
- `evaluation_results/analysis.ipynb` has the tables and figures of the
  benchmark results and writes them as files for a paper.
  `evaluation_results/walkthrough.ipynb` follows one report through the
  four commands.
- `gentrex select` asks a third question, `has_dates`, which keeps a page
  that lists the dates of the specimen and the report.
- `not_in_pages` no longer names a value that wraps in a table cell or a
  column of the page.
- With ClinVar's file, `gentrex normalize` settles a symbol of several
  genes, such as MLL2, by the gene that has the variant in ClinVar
  (`gene_status` is then `clinvar`).
- `gentrex normalize` reads dates with periods, such as 08.27.2026, by the
  rule for dates with slashes. The month comes first unless
  `normalize.day_first` is set.
- The extraction schema says more exactly what goes in `mrn`,
  `submitter_patient_id`, `lab_accession_number`, `report_date`,
  `genome_build` and `variants`, and when `classification_raw`,
  `zygosity_raw`, `variant_type_raw`, `dna_change_raw` and
  `chromosomal_position` stay empty. A karyotype finding, a normal result
  and a methylation pattern are no variants.
- The benchmark's scorer accepts a test name with or without its subtitle,
  `is_secondary_finding` as `false` where a report labels no finding, and a
  clinical feature that the reason for testing names.
- The benchmark's reports print a date with periods month first, as
  12.25.2026, and the trio table of one template keeps a protein change on
  one line.
- A carrier test of one gene is a `single_gene` test in the benchmark's
  truth. `generate.py recheck` renews the truth files of reports that are
  already built.

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
