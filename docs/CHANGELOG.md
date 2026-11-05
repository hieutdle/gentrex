# Changelog

## 0.1.0

The first release.

- `gentrex transcribe` reads the text of every page of the PDF reports, with
  OCR for scanned pages.
- `gentrex select` keeps the pages that hold the result or the patient's
  clinical features.
- `gentrex extract` turns the kept pages of each report into one record.
- `gentrex normalize` adds ISO dates, categories for the specimen and the
  result, HGNC IDs for the genes, MONDO IDs for the diseases and HPO terms for
  the clinical features.
- `gentrex load` writes the records into SQLite, PostgreSQL or MySQL.
- `gentrex export phenopackets` writes one GA4GH Phenopacket per patient.
  `--pseudonymize` replaces the patient keys and file names with keyed
  pseudonyms, for Phenopackets that are shared.
- `gentrex export omop` and `gentrex export omop-extended` write the records
  into an OMOP CDM database, the second with extension tables.
- `gentrex export fhir` writes one FHIR Bundle per report, following HL7's
  Genomics Reporting Implementation Guide.
- `--retry` makes `gentrex transcribe`, `gentrex select` and
  `gentrex extract` redo only the pages and reports that failed in an earlier
  run.
- Every run records the version of Gentrex, and its git commit, in
  `run.yaml`.
