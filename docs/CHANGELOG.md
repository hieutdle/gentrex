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

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
