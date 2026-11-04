"""The Phenopacket of one patient, GA4GH's JSON format, from their reports."""

import logging
from collections.abc import Callable
from typing import Any

from gentrex import records

_SCHEMA_VERSION = "2.0"

_ACMG = {
    "pathogenic": "PATHOGENIC",
    "likely_pathogenic": "LIKELY_PATHOGENIC",
    "uncertain_significance": "UNCERTAIN_SIGNIFICANCE",
    "likely_benign": "LIKELY_BENIGN",
    "benign": "BENIGN",
}
# Zygosity as terms of the Genotype Ontology (GENO), checked against this
# release.
_GENO_VERSION = "2026-02-02"
_ALLELIC_STATES = {
    "heterozygous": {"id": "GENO:0000135", "label": "heterozygous"},
    "homozygous": {"id": "GENO:0000136", "label": "homozygous"},
    "hemizygous": {"id": "GENO:0000134", "label": "hemizygous"},
    "heteroplasmic": {"id": "GENO:0000603", "label": "heteroplasmic"},
    "homoplasmic": {"id": "GENO:0000602", "label": "homoplasmic"},
}
_SEXES = {"f": "FEMALE", "female": "FEMALE", "m": "MALE", "male": "MALE"}
# MONDO's root term, for variants whose associated phenotype names no MONDO
# disease. A diagnosis needs a disease, and the variants would be lost
# without one.
_ANY_DISEASE = {"id": "MONDO:0000001", "label": "disease"}

_logger = logging.getLogger(__name__)


def build(
    patient_key: str,
    reports: list[records.NormalizedReport],
    versions: dict[str, str | None],
    created: str,
) -> dict[str, Any]:
    """Returns the Phenopacket of one patient.

    Args:
        patient_key: The patient's key from stage 5, which identifies the
            Phenopacket and its subject.
        reports: The patient's reports, each with data, in input order.
        versions: The HPO and MONDO releases that stage 4 used, under "hpo"
            and "mondo". "hpo" is None if stage 4 ran with --no-hpo.
        created: When the Phenopacket was made, as an ISO 8601 time in UTC.
    """
    subject: dict[str, Any] = {"id": patient_key}
    birth = _agreed(
        reports, lambda r: (r.normalized or {}).get("date_of_birth"), "dates of birth"
    )
    if birth:
        subject["dateOfBirth"] = f"{birth}T00:00:00Z"
    sex = _agreed(reports, _sex, "sexes")
    if sex:
        subject["sex"] = sex
    packet: dict[str, Any] = {"id": patient_key, "subject": subject}
    if features := _features(reports):
        packet["phenotypicFeatures"] = features
    packet["interpretations"] = [
        interpretation
        for report in reports
        for interpretation in _interpretations(patient_key, report)
    ]
    packet["metaData"] = {
        "created": created,
        "createdBy": "Gentrex",
        "resources": _resources(versions),
        "phenopacketSchemaVersion": _SCHEMA_VERSION,
    }
    return packet


def _sex(report: records.NormalizedReport) -> str | None:
    return _SEXES.get(((report.data or {}).get("sex") or "").strip().casefold())


def _agreed(
    reports: list[records.NormalizedReport],
    value: Callable[[records.NormalizedReport], str | None],
    what: str,
) -> str | None:
    """Returns the value that all reports giving one agree on, else None."""
    values = {v for report in reports if (v := value(report)) is not None}
    if len(values) > 1:
        _logger.warning(
            "%s give different %s, so the Phenopacket leaves them out",
            ", ".join(report.file for report in reports),
            what,
        )
        return None
    return next(iter(values), None)


def _features(reports: list[records.NormalizedReport]) -> list[dict[str, Any]]:
    """Returns each HPO term of the patient once, in order of first mention.

    A term is excluded only if no report finds it present. Features that a
    report is unsure of, and those without an HPO term, are left out.
    """
    terms: dict[str, dict[str, Any]] = {}
    for report in reports:
        matches = (report.normalized or {}).get("patient_phenotypes")
        if matches is None:
            continue
        features = (report.data or {}).get("patient_phenotypes") or []
        for feature, match in zip(features, matches, strict=True):
            if feature.get("present") is None or not match.get("hpo_id"):
                continue
            term = terms.setdefault(
                match["hpo_id"],
                {
                    "type": {"id": match["hpo_id"], "label": match["label"]},
                    "excluded": True,
                },
            )
            if feature["present"]:
                term["excluded"] = False
    return [
        term if term["excluded"] else {"type": term["type"]} for term in terms.values()
    ]


def _interpretations(
    patient_key: str, report: records.NormalizedReport
) -> list[dict[str, Any]]:
    """Returns one interpretation per disease of the report's variants.

    A report without variants gets one interpretation without a diagnosis.
    """
    data = report.data or {}
    normalized = report.normalized or {}
    result = normalized.get("overall_result")
    common: dict[str, Any] = {
        "progressStatus": {"negative": "UNSOLVED", None: "UNKNOWN_PROGRESS"}.get(
            result, "COMPLETED"
        )
    }
    if data.get("overall_result_raw"):
        common["summary"] = data["overall_result_raw"]
    variants = data.get("variants") or []
    genes = normalized.get("variants") or [{}] * len(variants)
    if not variants:
        return [{"id": f"{report.file}:1", **common}]
    by_disease: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for number, (variant, gene) in enumerate(zip(variants, genes, strict=True), 1):
        disease = (gene.get("disease_id"), gene.get("disease_label"))
        by_disease.setdefault(disease, []).append(
            _genomic_interpretation(
                patient_key, f"{report.file}:{number}", variant, gene
            )
        )
    return [
        {
            "id": f"{report.file}:{number}",
            **common,
            "diagnosis": {
                "disease": {"id": mondo_id, "label": label}
                if mondo_id
                else _ANY_DISEASE,
                "genomicInterpretations": interpretations,
            },
        }
        for number, ((mondo_id, label), interpretations) in enumerate(
            by_disease.items(), 1
        )
    ]


def _genomic_interpretation(
    patient_key: str, variant_id: str, variant: dict[str, Any], gene: dict[str, Any]
) -> dict[str, Any]:
    """Returns one variant, with its gene, HGVS change, zygosity and ACMG class."""
    descriptor: dict[str, Any] = {"id": variant_id}
    hgvs_c = variant.get("hgvs_c")
    label = " ".join(
        part
        for part in (
            gene.get("gene_symbol") or variant.get("gene_symbol"),
            hgvs_c or variant.get("dna_change_raw"),
            variant.get("hgvs_p"),
        )
        if part
    )
    if label:
        descriptor["label"] = label
    if gene.get("hgnc_id"):
        descriptor["geneContext"] = {
            "valueId": gene["hgnc_id"],
            "symbol": gene["gene_symbol"],
        }
    if hgvs_c and (":" in hgvs_c or variant.get("transcript")):
        expression = hgvs_c if ":" in hgvs_c else f"{variant['transcript']}:{hgvs_c}"
        descriptor["expressions"] = [{"syntax": "hgvs.c", "value": expression}]
    if state := _ALLELIC_STATES.get(variant.get("zygosity") or ""):
        descriptor["allelicState"] = state
    interpretation: dict[str, Any] = {"variationDescriptor": descriptor}
    if acmg := _ACMG.get(variant.get("classification") or ""):
        interpretation["acmgPathogenicityClassification"] = acmg
    if variant.get("classification") in ("benign", "likely_benign"):
        status = "REJECTED"
    elif variant.get("is_secondary_finding"):
        status = "UNKNOWN_STATUS"
    else:
        status = "CANDIDATE"
    return {
        "subjectOrBiosampleId": patient_key,
        "interpretationStatus": status,
        "variantInterpretation": interpretation,
    }


def _resources(versions: dict[str, str | None]) -> list[dict[str, str]]:
    """Returns the ontologies that the Phenopacket's terms come from."""
    resources = [
        ("mondo", "Mondo Disease Ontology", "MONDO", versions["mondo"] or "unknown"),
        ("geno", "Genotype Ontology", "GENO", _GENO_VERSION),
    ]
    if versions["hpo"] is not None:
        resources.insert(0, ("hp", "human phenotype ontology", "HP", versions["hpo"]))
    return [
        {
            "id": resource_id,
            "name": name,
            "url": f"http://purl.obolibrary.org/obo/{resource_id}.owl",
            "version": version,
            "namespacePrefix": prefix,
            "iriPrefix": f"http://purl.obolibrary.org/obo/{prefix}_",
        }
        for resource_id, name, prefix, version in resources
    ]
