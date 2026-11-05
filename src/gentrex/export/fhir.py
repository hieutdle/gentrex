"""FHIR R4 Bundles of genetic test reports, in HL7's Genomics Reporting IG.

Each report becomes one transaction Bundle that follows version 3.0.0 (STU3)
of the Genomics Reporting Implementation Guide. Every resource has a fixed
ID, made from the report's file name, or from the patient's key for the
Patient. So posting a Bundle to a FHIR server again replaces its resources
instead of adding copies, and the reports of one patient share one Patient.
"""

import uuid
from typing import Any

from gentrex import records
from gentrex.export import patients

_PROFILES = "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/"
_LOINC = "http://loinc.org"
_SNOMED = "http://snomed.info/sct"
_HGNC = "http://www.genenames.org"
_HGVS = "http://varnomen.hgvs.org"
_REFSEQ = "http://www.ncbi.nlm.nih.gov/refseq"
_HPO = "http://human-phenotype-ontology.org"
_MONDO = "http://purl.obolibrary.org/obo/mondo.owl"
_IG_CODES = "http://hl7.org/fhir/uv/genomics-reporting/CodeSystem/tbd-codes-cs"
_IDENTIFIER_TYPES = "http://terminology.hl7.org/CodeSystem/v2-0203"

# Resource IDs are UUIDs of names in this namespace, so that a report gets
# the same IDs in every run.
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/hieutdle/gentrex")

# Codes as (system, code, display), with the displays of the code systems.
Code = tuple[str, str, str | None]

_GENETICS: Code = ("http://terminology.hl7.org/CodeSystem/v2-0074", "GE", "Genetics")
_LABORATORY: Code = (
    "http://terminology.hl7.org/CodeSystem/observation-category",
    "laboratory",
    "Laboratory",
)
_MRN: Code = (_IDENTIFIER_TYPES, "MR", "Medical record number")
_ACCESSION: Code = (_IDENTIFIER_TYPES, "ACSN", "Accession ID")
_REPORT: Code = (_LOINC, "51969-4", "Genetic analysis report")
_TEST: Code = (_SNOMED, "405825005", "Molecular genetic test")
_VARIANT: Code = (_LOINC, "69548-6", "Genetic variant assessment")
_IMPLICATION: Code = (_IG_CODES, "diagnostic-implication", "Diagnostic Implication")
_GENE: Code = (_LOINC, "48018-6", "Gene studied [ID]")
_TRANSCRIPT: Code = (_LOINC, "51958-7", "Transcript reference sequence [ID]")
_DNA_CHANGE: Code = (_LOINC, "48004-6", "DNA change (c.HGVS)")
_PROTEIN_CHANGE: Code = (_LOINC, "48005-3", "Amino acid change (pHGVS)")
_ALLELIC_STATE: Code = (_LOINC, "53034-5", "Allelic state")
_ORIGIN: Code = (_LOINC, "94186-4", "Origin of germline genetic variant [Type]")
_SIGNIFICANCE: Code = (
    _LOINC,
    "53037-8",
    "Genetic variation clinical significance [Imp]",
)
_PHENOTYPE: Code = (_LOINC, "81259-4", "Associated phenotype")
_INHERITANCE: Code = (_IG_CODES, "condition-inheritance", "Condition Inheritance")
_PRESENT: Code = (_LOINC, "LA9633-4", "Present")
_ABSENT: Code = (_LOINC, "LA9634-2", "Absent")

_SPECIMENS: dict[str, Code] = {
    "whole_blood": (_SNOMED, "258580003", "Whole blood specimen"),
    "saliva": (_SNOMED, "119342007", "Saliva specimen"),
    "buccal_swab": (_SNOMED, "733104004", "Swab from buccal mucosa"),
    "bone_marrow": (_SNOMED, "119359002", "Bone marrow specimen"),
    "amniotic_fluid": (_SNOMED, "119373006", "Amniotic fluid specimen"),
    "chorionic_villus": (_SNOMED, "258565009", "Chorionic villi specimen"),
    "fibroblast": (_SNOMED, "119333000", "Fibroblast specimen"),
    "tissue": (_SNOMED, "119376003", "Tissue specimen"),
}
# The LOINC answers for a genetic test's overall interpretation have no
# uncertain or carrier result.
_RESULTS: dict[str, Code] = {
    "positive": (_LOINC, "LA6576-8", "Positive"),
    "negative": (_LOINC, "LA6577-6", "Negative"),
    "inconclusive": (_LOINC, "LA9663-1", "Inconclusive"),
}
_SIGNIFICANCES: dict[str, Code] = {
    "pathogenic": (_LOINC, "LA6668-3", "Pathogenic"),
    "likely_pathogenic": (_LOINC, "LA26332-9", "Likely pathogenic"),
    "uncertain_significance": (_LOINC, "LA26333-7", "Uncertain significance"),
    "likely_benign": (_LOINC, "LA26334-5", "Likely benign"),
    "benign": (_LOINC, "LA6675-8", "Benign"),
}
_ALLELIC_STATES: dict[str, Code] = {
    "heterozygous": (_LOINC, "LA6706-1", "Heterozygous"),
    "homozygous": (_LOINC, "LA6705-3", "Homozygous"),
    "hemizygous": (_LOINC, "LA6707-9", "Hemizygous"),
    "heteroplasmic": (_LOINC, "LA6703-8", "Heteroplasmic"),
    "homoplasmic": (_LOINC, "LA6704-6", "Homoplasmic"),
}
_ORIGINS: dict[str, Code] = {
    "de_novo": (_LOINC, "LA26807-0", "De novo"),
    "maternal": (_LOINC, "LA26320-4", "Maternal"),
    "paternal": (_LOINC, "LA26321-2", "Paternal"),
}
# HPO terms, as the IG's value set for the mode of inheritance lists them.
_INHERITANCES: dict[str, Code] = {
    "autosomal_dominant": (_HPO, "HP:0000006", "Autosomal dominant inheritance"),
    "autosomal_recessive": (_HPO, "HP:0000007", "Autosomal recessive inheritance"),
    "x_linked": (_HPO, "HP:0001417", "X-linked inheritance"),
    "x_linked_recessive": (_HPO, "HP:0001419", "X-linked recessive inheritance"),
    "x_linked_dominant": (_HPO, "HP:0001423", "X-linked dominant inheritance"),
    "mitochondrial": (_HPO, "HP:0001427", "Mitochondrial inheritance"),
}


def patient(
    patient_key: str, reports: list[records.NormalizedReport]
) -> dict[str, Any]:
    """Returns the Bundle entry of one patient, from all the patient's reports.

    The date of birth and sex are kept only when all reports that give one
    agree, as in the Phenopackets.

    Args:
        patient_key: The patient's key from `gentrex load`, which the
            Patient's ID is made from.
        reports: The patient's reports, each with data.
    """
    resource: dict[str, Any] = {}
    identifiers = [
        {"type": _concept(_MRN), "value": mrn}
        for mrn in sorted(patients.given(reports, lambda r: _field(r, "mrn")))
    ] + [
        {"type": {"text": "Submitter patient ID"}, "value": submitter_id}
        for submitter_id in sorted(
            patients.given(reports, lambda r: _field(r, "submitter_patient_id"))
        )
    ]
    if identifiers:
        resource["identifier"] = identifiers
    if sex := patients.agreed(reports, patients.sex, "sexes", "Patient resource"):
        resource["gender"] = sex.lower()
    if birth := patients.agreed(
        reports, patients.date_of_birth, "dates of birth", "Patient resource"
    ):
        resource["birthDate"] = birth
    return _entry("Patient", patient_key, resource)


def bundle(
    report: records.NormalizedReport, patient_entry: dict[str, Any]
) -> dict[str, Any]:
    """Returns the transaction Bundle of one report.

    Args:
        report: The report, with data.
        patient_entry: The entry of the report's patient, from `patient`.
    """
    data = report.data or {}
    normalized = report.normalized or {}
    subject = _reference(patient_entry)
    entries = [patient_entry]
    common: dict[str, Any] = {"subject": subject}
    if date := _effective_date(normalized):
        common["effectiveDateTime"] = date
    if lab := (data.get("lab_name") or "").strip():
        lab_entry = _entry("Organization", lab, {"name": lab})
        entries.append(lab_entry)
        common["performer"] = [_reference(lab_entry)]
    specimen = None
    if specimen_entry := _specimen(report.file, data, normalized, subject):
        entries.append(specimen_entry)
        specimen = _reference(specimen_entry)

    features = _features(report, subject)
    entries += features
    order: dict[str, Any] = {
        "status": "completed",
        "intent": "order",
        "code": _concept(_TEST, data.get("test_name")),
        "subject": subject,
    }
    if data.get("clinical_indication"):
        order["reasonCode"] = [{"text": data["clinical_indication"]}]
    if features:
        order["supportingInfo"] = [_reference(entry) for entry in features]
    if specimen:
        order["specimen"] = [specimen]
    order_entry = _entry("ServiceRequest", report.file, order)
    entries.append(order_entry)

    results = []
    variants = data.get("variants") or []
    genes = normalized.get("variants") or [{}] * len(variants)
    for number, (variant, gene) in enumerate(zip(variants, genes, strict=True), 1):
        variant_entry = _entry(
            "Observation",
            f"{report.file}/variant/{number}",
            _variant(variant, gene, common, specimen),
        )
        entries.append(variant_entry)
        results.append(_reference(variant_entry))
        if implication := _implication(variant, gene, common, variant_entry):
            implication_entry = _entry(
                "Observation", f"{report.file}/implication/{number}", implication
            )
            entries.append(implication_entry)
            results.append(_reference(implication_entry))

    diagnostic_report: dict[str, Any] = {
        "meta": {"profile": [_PROFILES + "genomic-report"]}
    }
    if accession := data.get("lab_accession_number"):
        diagnostic_report["identifier"] = [
            {"type": _concept(_ACCESSION), "value": accession}
        ]
    diagnostic_report |= {
        "basedOn": [_reference(order_entry)],
        "status": "final",
        "category": [_concept(_GENETICS)],
        "code": _concept(_REPORT, data.get("test_name")),
        **common,
    }
    if specimen:
        diagnostic_report["specimen"] = [specimen]
    if results:
        diagnostic_report["result"] = results
    if data.get("overall_result_raw"):
        diagnostic_report["conclusion"] = data["overall_result_raw"]
    if result := _RESULTS.get(normalized.get("overall_result") or ""):
        diagnostic_report["conclusionCode"] = [_concept(result)]
    entries.append(_entry("DiagnosticReport", report.file, diagnostic_report))
    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def _field(report: records.NormalizedReport, name: str) -> str | None:
    return ((report.data or {}).get(name) or "").strip() or None


def _effective_date(normalized: dict[str, Any]) -> str | None:
    """Returns the date that the results refer to, the collection date if known."""
    for field in (
        "collection_date",
        "received_date",
        "test_started_date",
        "report_date",
    ):
        if normalized.get(field):
            return normalized[field]
    return None


def _entry(resource_type: str, name: str, resource: dict[str, Any]) -> dict[str, Any]:
    """Returns a Bundle entry that creates or replaces the resource by its ID."""
    resource_id = str(uuid.uuid5(_NAMESPACE, f"{resource_type}/{name}"))
    return {
        "fullUrl": f"urn:uuid:{resource_id}",
        "resource": {"resourceType": resource_type, "id": resource_id, **resource},
        "request": {"method": "PUT", "url": f"{resource_type}/{resource_id}"},
    }


def _reference(entry: dict[str, Any]) -> dict[str, str]:
    return {"reference": entry["fullUrl"]}


def _concept(code: Code, text: str | None = None) -> dict[str, Any]:
    """Returns a CodeableConcept with one coding and, if given, the text."""
    system, value, display = code
    coding = {"system": system, "code": value}
    if display:
        coding["display"] = display
    concept: dict[str, Any] = {"coding": [coding]}
    if text:
        concept["text"] = text
    return concept


def _coded(
    codes: dict[str, Code], value: str | None, raw: str | None
) -> dict[str, Any] | None:
    """Returns the code of `value` with the report's wording, else the wording."""
    if value in codes:
        return _concept(codes[value], raw)
    return {"text": raw} if raw else None


def _component(code: Code, value: dict[str, Any]) -> dict[str, Any]:
    return {"code": _concept(code), "valueCodeableConcept": value}


def _specimen(
    file: str, data: dict[str, Any], normalized: dict[str, Any], subject: dict[str, str]
) -> dict[str, Any] | None:
    """Returns the entry of the report's specimen, or None if it states none."""
    specimen: dict[str, Any] = {}
    raw = data.get("specimen_type")
    if category := _SPECIMENS.get(normalized.get("specimen_type") or ""):
        specimen["type"] = _concept(category, raw)
    elif raw:
        specimen["type"] = {"text": raw}
    if not specimen and not (
        normalized.get("collection_date") or normalized.get("received_date")
    ):
        return None
    specimen["subject"] = subject
    if normalized.get("received_date"):
        specimen["receivedTime"] = normalized["received_date"]
    if normalized.get("collection_date"):
        specimen["collection"] = {"collectedDateTime": normalized["collection_date"]}
    return _entry("Specimen", file, specimen)


def _features(
    report: records.NormalizedReport, subject: dict[str, str]
) -> list[dict[str, Any]]:
    """Returns one Observation entry per clinical feature, present or absent.

    Features that the report is unsure of are left out, as in the other
    exports.
    """
    features = (report.data or {}).get("patient_phenotypes") or []
    matches = (report.normalized or {}).get("patient_phenotypes") or [{}] * len(
        features
    )
    entries = []
    for number, (feature, match) in enumerate(zip(features, matches, strict=True), 1):
        if feature.get("present") is None:
            continue
        code = {"text": feature["text"]}
        if match.get("hpo_id"):
            code = _concept((_HPO, match["hpo_id"], match["label"]), feature["text"])
        observation = {
            "status": "final",
            "code": code,
            "subject": subject,
            "valueCodeableConcept": _concept(
                _PRESENT if feature["present"] else _ABSENT
            ),
        }
        entries.append(
            _entry("Observation", f"{report.file}/feature/{number}", observation)
        )
    return entries


def _variant(
    variant: dict[str, Any],
    gene: dict[str, Any],
    common: dict[str, Any],
    specimen: dict[str, str] | None,
) -> dict[str, Any]:
    """Returns the Observation of one variant, in the IG's variant profile.

    The IG takes HGVS changes only as valid HGVS expressions, with their
    reference sequence. Changes without one go into a note, as printed.
    """
    components = []
    notes = []
    if variant.get("dna_change_raw"):
        notes.append(f"DNA change: {variant['dna_change_raw']}")
    if gene.get("hgnc_id"):
        components.append(
            _component(_GENE, _concept((_HGNC, gene["hgnc_id"], gene["gene_symbol"])))
        )
    elif variant.get("gene_symbol"):
        components.append(_component(_GENE, {"text": variant["gene_symbol"]}))
    transcript = variant.get("transcript")
    if transcript:
        components.append(
            _component(_TRANSCRIPT, _concept((_REFSEQ, transcript, None)))
        )
    hgvs_c = variant.get("hgvs_c")
    if hgvs_c and (":" in hgvs_c or transcript):
        expression = hgvs_c if ":" in hgvs_c else f"{transcript}:{hgvs_c}"
        components.append(_component(_DNA_CHANGE, _concept((_HGVS, expression, None))))
    elif hgvs_c:
        notes.append(f"DNA change: {hgvs_c}")
    hgvs_p = variant.get("hgvs_p")
    if hgvs_p and ":" in hgvs_p:
        components.append(_component(_PROTEIN_CHANGE, _concept((_HGVS, hgvs_p, None))))
    elif hgvs_p:
        notes.append(f"Protein change: {hgvs_p}")
    if state := _coded(
        _ALLELIC_STATES, variant.get("zygosity"), variant.get("zygosity_raw")
    ):
        components.append(_component(_ALLELIC_STATE, state))
    if origin := _coded(
        _ORIGINS, variant.get("parental_origin"), variant.get("parental_origin_raw")
    ):
        components.append(_component(_ORIGIN, origin))

    observation: dict[str, Any] = {"meta": {"profile": [_PROFILES + "variant"]}}
    if variant.get("is_secondary_finding"):
        observation["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/"
                "observation-secondaryFinding",
                "valueCodeableConcept": {"text": "Secondary finding"},
            }
        ]
    observation |= {
        "status": "final",
        "category": [_concept(_LABORATORY), _concept(_GENETICS)],
        "code": _concept(_VARIANT),
        **common,
        "valueCodeableConcept": _concept(_PRESENT),
    }
    if notes:
        observation["note"] = [{"text": note} for note in notes]
    if specimen:
        observation["specimen"] = specimen
    if components:
        observation["component"] = components
    return observation


def _implication(
    variant: dict[str, Any],
    gene: dict[str, Any],
    common: dict[str, Any],
    variant_entry: dict[str, Any],
) -> dict[str, Any] | None:
    """Returns the variant's ACMG class, disease and mode of inheritance.

    The Observation follows the IG's diagnostic-implication profile. It is
    None if the report states none of the three.
    """
    components = []
    if significance := _coded(
        _SIGNIFICANCES, variant.get("classification"), variant.get("classification_raw")
    ):
        components.append(_component(_SIGNIFICANCE, significance))
    phenotype = variant.get("associated_phenotype")
    if gene.get("disease_id"):
        disease = (_MONDO, gene["disease_id"], gene.get("disease_label"))
        components.append(_component(_PHENOTYPE, _concept(disease, phenotype)))
    elif phenotype:
        components.append(_component(_PHENOTYPE, {"text": phenotype}))
    if inheritance := _coded(
        _INHERITANCES,
        variant.get("mode_of_inheritance"),
        variant.get("mode_of_inheritance_raw"),
    ):
        components.append(_component(_INHERITANCE, inheritance))
    if not components:
        return None
    return {
        "meta": {"profile": [_PROFILES + "diagnostic-implication"]},
        "status": "final",
        "category": [_concept(_LABORATORY), _concept(_GENETICS)],
        "code": _concept(_IMPLICATION),
        **common,
        "derivedFrom": [_reference(variant_entry)],
        "component": components,
    }
