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

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
