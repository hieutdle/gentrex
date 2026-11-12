"""The Phenopacket of one patient, GA4GH's JSON format, from their reports."""

import re
from typing import Any

from gentrex import records
from gentrex.export import patients
from gentrex.export import pseudonyms as pseudonyms_lib

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
# MONDO's root term, for variants whose associated phenotype names no MONDO
# disease. A diagnosis needs a disease, and the variants would be lost
# without one.
_ANY_DISEASE = {"id": "MONDO:0000001", "label": "disease"}
# Copy-number changes as terms of the Sequence Ontology (SO) under
# structural_variant, SO:0001537, as the schema recommends. Checked against
# this release.
_SO_VERSION = "2026-08-07"
_GAIN = {"id": "SO:0001911", "label": "copy_number_increase"}
_LOSS = {"id": "SO:0001912", "label": "copy_number_decrease"}
# An array result in ISCN, as in arr[GRCh37] 17p11.2(16761827_20304681)x3,
# with the chromosome that it names first.
_ARRAY = re.compile(r"arr\b(?:\[[^\]]*\])?\s*\(?(\d+|X|Y)?")
# A karyotype in ISCN, as in 46,XY or 45,X[20], with its sex chromosomes and
# the rest.
_KARYOTYPE = re.compile(r"\d+,([XY]+)(?:\[\d+\])?(.*)")
_KARYOTYPIC_SEXES = {
    "X": "XO",
    **{sex: sex for sex in ("XX", "XY", "XXY", "XXX", "XXYY", "XXXY", "XXXX", "XYY")},
}


def build(
    patient_key: str,
    reports: list[records.NormalizedReport],
    versions: dict[str, str | None],
    created: str,
    pseudonyms: pseudonyms_lib.Pseudonyms | None = None,
) -> dict[str, Any]:
    """Returns the Phenopacket of one patient.

    Args:
        patient_key: The patient's key from `gentrex load`, which identifies
            the Phenopacket and its subject.
        reports: The patient's reports, each with data, in input order.
        versions: The HPO and MONDO releases that `gentrex normalize` used,
            under "hpo" and "mondo". "hpo" is None if `gentrex normalize` ran
            with --no-hpo.
        created: When the Phenopacket was made, as an ISO 8601 time in UTC.
        pseudonyms: Pseudonyms that replace the patient key and the reports'
            file names, for Phenopackets that are shared. The date of birth is
            then left out.
    """
    subject_id = pseudonyms.patient(patient_key) if pseudonyms else patient_key
    subject: dict[str, Any] = {"id": subject_id}
    if not pseudonyms and (
        birth := patients.agreed(
            reports, patients.date_of_birth, "dates of birth", "Phenopacket"
        )
    ):
        subject["dateOfBirth"] = f"{birth}T00:00:00Z"
    sex = patients.agreed(reports, patients.sex, "sexes", "Phenopacket")
    if sex:
        subject["sex"] = sex
    if karyotypic_sex := patients.agreed(
        reports, _karyotypic_sex, "karyotypic sexes", "Phenopacket"
    ):
        subject["karyotypicSex"] = karyotypic_sex
    packet: dict[str, Any] = {"id": subject_id, "subject": subject}
    if features := _features(reports):
        packet["phenotypicFeatures"] = features
    packet["interpretations"] = [
        interpretation
        for report in reports
        for interpretation in _interpretations(
            subject_id,
            pseudonyms.report(report.file) if pseudonyms else report.file,
            report,
        )
    ]
    packet["metaData"] = {
        "created": created,
        "createdBy": "Gentrex",
        "resources": _resources(versions),
        "phenopacketSchemaVersion": _SCHEMA_VERSION,
    }
    return packet


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


def _karyotypic_sex(report: records.NormalizedReport) -> str | None:
    """Returns the KaryotypicSex of the report's karyotype, or None without one.

    A mosaic, and a karyotype that changes the structure of a sex chromosome,
    as in 46,X,i(X)(q10), are OTHER_KARYOTYPE.
    """
    karyotype = "".join(((report.data or {}).get("karyotype") or "").split())
    if "/" in karyotype:
        return "OTHER_KARYOTYPE"
    if not (match := _KARYOTYPE.match(karyotype)):
        return None
    sex, rest = match.groups()
    if sex not in _KARYOTYPIC_SEXES or re.search("[XY]", rest):
        return "OTHER_KARYOTYPE"
    return _KARYOTYPIC_SEXES[sex]


def _interpretations(
    subject_id: str, report_id: str, report: records.NormalizedReport
) -> list[dict[str, Any]]:
    """Returns one interpretation per disease of the report's variants.

    A report without variants gets one interpretation without a diagnosis.
    The IDs of the interpretations and variants start with `report_id`.
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
        return [{"id": f"{report_id}:1", **common}]
    by_disease: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for number, (variant, gene) in enumerate(zip(variants, genes, strict=True), 1):
        disease = (gene.get("disease_id"), gene.get("disease_label"))
        by_disease.setdefault(disease, []).append(
            _genomic_interpretation(subject_id, f"{report_id}:{number}", variant, gene)
        )
    return [
        {
            "id": f"{report_id}:{number}",
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
    """Returns one variant, with its gene, change, zygosity and ACMG class."""
    descriptor: dict[str, Any] = {"id": variant_id}
    hgvs_c = variant.get("hgvs_c")
    array = _ARRAY.match(variant.get("dna_change_raw") or "")
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
    expressions = []
    if hgvs_c and (":" in hgvs_c or variant.get("transcript")):
        expression = hgvs_c if ":" in hgvs_c else f"{variant['transcript']}:{hgvs_c}"
        expressions.append({"syntax": "hgvs.c", "value": expression})
    if array:
        expressions.append({"syntax": "iscn", "value": variant["dna_change_raw"]})
    if expressions:
        descriptor["expressions"] = expressions
    chromosome = array[1] if array else None
    if structural_type := _structural_type(variant.get("copy_number"), chromosome):
        descriptor["structuralType"] = structural_type
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


def _structural_type(
    copies: int | None, chromosome: str | None
) -> dict[str, str] | None:
    """Returns whether the variant gains or loses copies, when that is certain.

    A region normally has at most two copies, so 3 or more is a gain and 0 a
    loss. 1 is a loss if an array result puts the change on one of the
    chromosomes 1 to 22. On X and Y, 1 and 2 depend on the patient's sex
    chromosomes.

    Args:
        copies: The variant's `copy_number`.
        chromosome: The chromosome that the variant's array result names.
    """
    if copies is None:
        return None
    if copies >= 3:
        return _GAIN
    if copies == 0 or (copies == 1 and (chromosome or "").isdigit()):
        return _LOSS
    return None


def _resources(versions: dict[str, str | None]) -> list[dict[str, str]]:
    """Returns the ontologies that the Phenopacket's terms come from."""
    resources = [
        ("mondo", "Mondo Disease Ontology", "MONDO", versions["mondo"] or "unknown"),
        ("geno", "Genotype Ontology", "GENO", _GENO_VERSION),
        ("so", "Sequence types and features ontology", "SO", _SO_VERSION),
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
