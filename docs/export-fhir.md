# Export report data as FHIR Bundles

`gentrex export fhir` writes the records from a run of `gentrex normalize` as
FHIR Bundles, one JSON file per report. FHIR is HL7's standard for exchanging
health data between systems, such as a laboratory and an EHR. FHIR data comes
in resources, such as a Patient or an Observation, and a Bundle is one file
that holds several resources. The Bundles follow version 3.0.0 of HL7's
Genomics Reporting Implementation Guide (IG), the rules for genetic test
results in FHIR R4, the fourth release of FHIR and the one that Epic uses.
An EHR such as Epic, or a FHIR server, can then take the reports in as
structured results rather than as PDFs.

For example, a report on a girl with seizures and a pathogenic SCN1A variant
becomes a Bundle with these resources:

- A Patient with the MRN SYN-MRN-0001.
- A DiagnosticReport for the report itself, with its overall result,
  `POSITIVE`.
- An Observation for the variant `NM_001165963.4:c.4933C>T` in SCN1A,
  heterozygous and de novo.
- An Observation for what the variant means. It is pathogenic, and the
  disease is MONDO:0100135, Dravet syndrome.
- An Observation for the clinical feature HP:0001250, Seizure.

`gentrex export fhir` reads `normalized.jsonl` from a run of
`gentrex normalize` and writes to `results/export/fhir/`. It needs no model
server, no GPU and no database, and it exports a few hundred reports in a
second.

## Before you start

You need:

- Gentrex installed, as in step 1 of
  [Transcribe PDF pages](transcribe.md#step-1-install).
- A finished run of `gentrex normalize`, in `results/normalize/`.

To check the Bundles, as [Check the result](#check-the-result) shows, you
also need Java 17 or newer for HL7's validator. To search them, you need
[Docker](https://docs.docker.com/get-started/get-docker/) for a test FHIR
server.

## Step 1: Run

```bash
uv run gentrex export fhir
```

This reads the newest finished run of `gentrex normalize`,
`results/normalize/latest`, and writes a new folder named after the time the
run started, such as `results/export/fhir/20261105-042612/`. To export
another run of `gentrex normalize`:

```bash
uv run gentrex export fhir --input results/normalize/20261019-030000
```

Gentrex prints one line per Bundle, such as
`wrote report-01.json from report-01.pdf`. The last line counts the reports
it wrote, as in `wrote 3 of 4 reports as Bundles in 0 s`.

## Check the result

The run folder holds:

| File | Contents |
| --- | --- |
| `bundles/` | One JSON file per report, named after the PDF, such as `report-01.json` for `report-01.pdf`. |
| `run.yaml` | The command and the run of `gentrex normalize` that was read. |
| `log.txt` | What Gentrex printed during the run. |

`results/export/fhir/latest` points to the newest finished run.
[Runs and results](../README.md#runs-and-results) explains run folders and
`latest`.

The Bundles hold patient identifiers. Each Patient has the MRN, the date of
birth and the sex, because an EHR needs the MRN to file the results with the
right patient. Send the Bundles only to systems approved for patient data.

Each Bundle has these resources:

| Resource | From the record |
| --- | --- |
| Patient | `mrn` and `submitter_patient_id` as identifiers, `sex` and `normalized.date_of_birth`. |
| Organization | `lab_name`, the laboratory that performed the test. |
| Specimen | `specimen_type`, with a SNOMED CT code for its category, and `collection_date` and `received_date`. |
| Observation, one per clinical feature | The HPO term and the wording of each feature in `patient_phenotypes`, with the value Present or Absent. |
| ServiceRequest | The order, with `test_name`, the `clinical_indication` as its reason, and the clinical features as supporting information. |
| Observation, one per variant | The gene, transcript, HGVS changes, zygosity and parental origin, in the IG's `variant` profile. |
| Observation, one per variant | The ACMG class, the MONDO disease and the mode of inheritance, in the IG's `diagnostic-implication` profile. |
| DiagnosticReport | The report, in the IG's `genomic-report` profile, with `test_name`, `lab_accession_number` and `overall_result_raw`. It lists the variants and their implications as its results. |

A profile is a set of rules that an IG adds to a FHIR resource, such as which
codes a field must use. Shortened, the Observation of a variant looks like
this:

```json
{
  "fullUrl": "urn:uuid:d50bb200-7a2a-5f41-8641-79b9508f4ad6",
  "resource": {
    "resourceType": "Observation",
    "id": "d50bb200-7a2a-5f41-8641-79b9508f4ad6",
    "meta": {"profile": ["http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/variant"]},
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "69548-6", "display": "Genetic variant assessment"}]},
    "subject": {"reference": "urn:uuid:9bc2e9b1-e23e-5d9a-bf4e-123c90777b13"},
    "effectiveDateTime": "2026-08-27",
    "valueCodeableConcept": {"coding": [{"system": "http://loinc.org", "code": "LA9633-4", "display": "Present"}]},
    "note": [{"text": "Protein change: p.(Arg1645*)"}],
    "component": [
      {
        "code": {"coding": [{"system": "http://loinc.org", "code": "48018-6", "display": "Gene studied [ID]"}]},
        "valueCodeableConcept": {"coding": [{"system": "http://www.genenames.org", "code": "HGNC:10585", "display": "SCN1A"}]}
      },
      {
        "code": {"coding": [{"system": "http://loinc.org", "code": "48004-6", "display": "DNA change (c.HGVS)"}]},
        "valueCodeableConcept": {"coding": [{"system": "http://varnomen.hgvs.org", "code": "NM_001165963.4:c.4933C>T"}]}
      },
      {
        "code": {"coding": [{"system": "http://loinc.org", "code": "53034-5", "display": "Allelic state"}]},
        "valueCodeableConcept": {"coding": [{"system": "http://loinc.org", "code": "LA6706-1", "display": "Heterozygous"}], "text": "Heterozygous"}
      }
    ]
  },
  "request": {"method": "PUT", "url": "Observation/d50bb200-7a2a-5f41-8641-79b9508f4ad6"}
}
```

Each component holds one fact under a code, which is how EHRs and FHIR
searches find it. The variant's Observation has the first six components,
and the implication has the last three:

| Component | Code | From |
| --- | --- | --- |
| Gene studied | LOINC 48018-6 | `hgnc_id`, with the approved symbol. A gene without an HGNC ID keeps `gene_symbol` as printed. |
| Transcript reference sequence | LOINC 51958-7 | `transcript`. |
| DNA change (c.HGVS) | LOINC 48004-6 | `transcript` and `hgvs_c`, as one HGVS expression. |
| Amino acid change (pHGVS) | LOINC 48005-3 | `hgvs_p`, if it names the protein's reference sequence. |
| Allelic state | LOINC 53034-5 | `zygosity`. |
| Origin of germline genetic variant | LOINC 94186-4 | `parental_origin`. |
| Clinical significance | LOINC 53037-8 | `classification`. |
| Associated phenotype | LOINC 81259-4 | `disease_id` and `disease_label` from MONDO, with `associated_phenotype` as printed. |
| Mode of inheritance | `condition-inheritance`, a code of the IG | `mode_of_inheritance`, as an HPO term. |

### Check the Bundles against the IG

HL7's FHIR Validator checks each Bundle against FHIR R4 and the IG's
profiles. Download it once, about 200 MB:

```bash
curl -L -o validator_cli.jar https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar
```

Then check the Bundles of the newest run:

```bash
java -jar validator_cli.jar -version 4.0.1 \
  -ig hl7.fhir.uv.genomics-reporting#3.0.0 -tx n/a \
  results/export/fhir/latest/bundles/*.json
```

- `-version 4.0.1` checks against FHIR R4, the version that the IG builds on.
- `-ig hl7.fhir.uv.genomics-reporting#3.0.0` loads the IG's profiles. The
  validator downloads them from HL7's package server on the first run.
- `-tx n/a` turns off the terminology server, a web service that checks
  codes. Without this option, the validator sends the codes to HL7's public
  server tx.fhir.org, the HGVS changes among them. Leave it out only for
  Bundles from synthetic reports.

After the first run, the check takes about 10 seconds. The validator prints
`Success: 0 errors` for each Bundle that follows the IG, with warnings that
[When something goes wrong](#when-something-goes-wrong) explains.

### Search the Bundles

A FHIR server stores resources and answers searches over them. HAPI FHIR is
an open-source FHIR server, and Docker runs it in a container, a package of
the server with everything it needs. The server stores the patients'
results, so start it only on a machine approved for patient data:

```bash
docker run -d --name gentrex-fhir -p 127.0.0.1:8080:8080 hapiproject/hapi:v8.12.0-2
```

- `-d` runs the container in the background.
- `--name gentrex-fhir` names the container, so that later commands can
  refer to it.
- `-p 127.0.0.1:8080:8080` makes the server reachable at port 8080 from your
  machine only.
- `hapiproject/hapi:v8.12.0-2` is the version of HAPI that Gentrex is tested
  with. The first run downloads it, about 1.1 GB.

The server is ready, within a minute, when
`curl http://127.0.0.1:8080/fhir/metadata` prints JSON. Then post the Bundles
to it:

```bash
for bundle in results/export/fhir/latest/bundles/*.json; do
  curl -s -o /dev/null -w "%{http_code} $bundle\n" -X POST \
    -H "Content-Type: application/fhir+json" --data-binary @"$bundle" \
    http://127.0.0.1:8080/fhir
done
```

Each line starts with `200` when the server took the Bundle. To find the
variants in SCN1A, search for the gene's HGNC ID in the component with the
LOINC code 48018-6:

```bash
curl -s -G http://127.0.0.1:8080/fhir/Observation \
  --data-urlencode 'component-code-value-concept=http://loinc.org|48018-6$http://www.genenames.org|HGNC:10585'
```

To find the pathogenic variants, search for the implications with the LOINC
answer LA6668-3, Pathogenic. `_include` adds the variant that each
implication is derived from, with its gene:

```bash
curl -s -G http://127.0.0.1:8080/fhir/Observation \
  --data-urlencode 'component-code-value-concept=http://loinc.org|53037-8$http://loinc.org|LA6668-3' \
  --data-urlencode '_include=Observation:derived-from'
```

HAPI keeps the resources inside the container, so `docker rm -f gentrex-fhir`
deletes them with it.

## How it works

### One Bundle per report

A laboratory sends its results one report at a time, and an EHR files them
that way. So each report becomes one Bundle, and the reports of one patient,
those with the same `patient_key` as in
[`gentrex load`](load.md#link-reports-to-patients), share one Patient. A
report without data, from a failed request in `gentrex extract`, gets no
Bundle, and Gentrex lists it among the failed files.

The Patient's date of birth and sex come from all the patient's reports in
the run. They are kept only when all reports that give one agree, as in the
[Phenopackets](export-phenopackets.md#one-phenopacket-per-patient).

### Fixed resource IDs

Each Bundle is a transaction, a set of changes that a FHIR server makes all
together or not at all. Each entry asks the server to create a resource
under a fixed ID, or to replace the resource that already has it. The ID is
a UUID, a 36-character identifier, made from the PDF's file name, and from
the patient's key for the Patient. So:

- Posting a Bundle again replaces its resources instead of adding copies.
- The Bundles of one patient's reports write the same Patient.
- The same lab name always writes the same Organization.
- Two PDFs with the same file name write the same resources, even from
  different folders. Give each report a file name of its own.

The resources refer to each other by their `fullUrl`, such as
`urn:uuid:9bc2e9b1-e23e-5d9a-bf4e-123c90777b13`. The server replaces it with
its own address, such as `Patient/9bc2e9b1-e23e-5d9a-bf4e-123c90777b13`.

### Variants

The IG takes an HGVS change only as a valid HGVS expression, which starts
with its reference sequence. `hgvs_c` becomes one when it starts with a
reference sequence, such as `NM_000059.4:c.5946del`, or when the report
names the `transcript`. A protein change needs the protein's reference
sequence, as in `NP_000050.2:p.(Asn1836Lys)`, which reports rarely print.
Changes without a reference sequence go into the variant's `note`, as
printed, after `DNA change:` or `Protein change:`. So does a DNA change
without a c. notation, such as `NC_012920.1:m.3243A>G` or a deletion of whole
exons, from `dna_change_raw`.

The IG separates what was found from what it means. So the ACMG class, the
disease and the mode of inheritance go into a second Observation, the
diagnostic implication, which points to the variant with `derivedFrom`. A
variant without any of the three has no implication.

A value that the IG has no code for keeps only the report's wording, as
text. This applies to `other` in any field, to `both_parents` as the
parental origin, and to a gene without an HGNC ID. A secondary finding gets
the extension for secondary findings, an extra field that the IG adds to the
variant, with the text `Secondary finding`. The extension's codes name the
version of the ACMG guideline, which reports don't state.

### Overall result and dates

The report's `overall_result_raw` is the DiagnosticReport's `conclusion`. A
positive, negative or inconclusive result also gets a LOINC answer in
`conclusionCode`. LOINC has no answer for an uncertain or a carrier result,
so those keep only the wording.

The DiagnosticReport and its Observations have one date,
`effectiveDateTime`, the date that the results refer to. It is the
collection date. If the report gives none, it is the first of the received
date, the test start date and the report date. FHIR records when a report
was issued with the time of day and the time zone, which reports don't
print, so the report date goes in only this way.

### What the Bundles leave out

- `test_type` and `variant_type_raw`, because the IG's fields for them take
  codes that Gentrex doesn't assign.
- `chromosomal_position`, because a genomic position needs the genome build,
  which reports rarely state.
- The HPO candidates of each clinical feature, and `models_agree`. Features
  that a report is unsure of, with `present` set to `null`, are left out too,
  because FHIR has no value for them.

## Settings

`gentrex export fhir` has no settings.

## When something goes wrong

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Every report was exported, and none has an error. | Nothing. |
| 1 | The run of `gentrex normalize` is missing, some reports have no data or an error, or the run stopped with a traceback. The end of the output says which. | See below. |

If `results/normalize/latest/normalized.jsonl not found` appears, run
`gentrex normalize` first, or name a run of `gentrex normalize` with
`--input`.

While it exports, Gentrex prints a warning for each problem it works around:

- `skipped report-13.pdf, which has no data: APITimeoutError: Request timed out.`
  means that `gentrex extract` got no data for the report. Run
  `gentrex extract` again for it, and then `gentrex normalize` and
  `gentrex export fhir`.
- `report-01.pdf, report-02.pdf give different dates of birth, so the
  Patient resource leaves them out` means that the reports of one patient
  disagree. Check the PDFs. The same goes for `different sexes`.

A report with an error from `gentrex extract` or `gentrex normalize` is still
exported, but it is listed among the failed files at the end.

The validator prints warnings for every Bundle. These don't break the IG:

| Warning | Why it appears |
| --- | --- |
| `dom-6: 'A resource should have narrative for robust management'` | Gentrex writes no narrative, the HTML text of a resource for people to read. FHIR servers and EHRs display the data themselves. |
| `A definition for CodeSystem 'http://www.genenames.org' could not be found` | The validator can't look up codes without a terminology server, and tx.fhir.org doesn't hold HGNC, HPO, MONDO or RefSeq either. The same goes for HGVS with `-tx n/a`. |
| `No code provided, and a code should be provided from the value set ...` | The value has only the report's wording, as [Variants](#variants) explains. |
| `In general, all observations should have a performer` and `... should have an effective[x]` | Clinical features have neither, because reports don't say who found a feature or when. |

If a FHIR server other than HAPI rejects the Bundles, check whether it lets
clients choose the IDs of new resources. Each entry creates its resource
under Gentrex's fixed ID, and some servers allow only IDs that they assign.
Ask the server's team to allow it for Gentrex's Bundles.
