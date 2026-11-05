import json
import pathlib
from collections.abc import Iterator
from typing import Any

from gentrex import records
from gentrex.export import run

_LOINC = "http://loinc.org"


def _report(file: str = "report-01.pdf") -> records.NormalizedReport:
    data = {
        "mrn": "SYN-MRN-0001",
        "sex": "Female",
        "specimen_type": "Blood in EDTA",
        "test_name": "Epilepsy Panel",
        "overall_result_raw": "POSITIVE",
        "lab_name": "GeneDx",
        "patient_phenotypes": [
            {"text": "seizures", "present": True},
            {"text": "no hearing loss", "present": False},
            {"text": "possible ataxia", "present": None},
        ],
        "variants": [
            {
                "gene_symbol": "SCN1A",
                "transcript": "NM_001165963.4",
                "hgvs_c": "c.4933C>T",
                "hgvs_p": "p.(Arg1645*)",
                "classification": "pathogenic",
                "zygosity": "heterozygous",
                "parental_origin": "de_novo",
                "associated_phenotype": "Dravet syndrome",
            }
        ],
    }
    normalized = {
        "date_of_birth": "2018-05-14",
        "specimen_type": "whole_blood",
        "collection_date": "2026-08-27",
        "overall_result": "positive",
        "patient_phenotypes": [
            {"hpo_id": "HP:0001250", "label": "Seizure"},
            {"hpo_id": "HP:0000365", "label": "Hearing impairment"},
            {"hpo_id": "HP:0001251", "label": "Ataxia"},
        ],
        "variants": [
            {
                "gene_symbol": "SCN1A",
                "hgnc_id": "HGNC:10585",
                "disease_id": "MONDO:0100135",
                "disease_label": "Dravet syndrome",
            }
        ],
    }
    return records.NormalizedReport(file, [1], data, normalized)


def _export(
    tmp_path: pathlib.Path, reports: list[records.NormalizedReport]
) -> dict[str, dict[str, Any]]:
    """Writes `reports` as `gentrex normalize` does, and returns each Bundle."""
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / "normalized.jsonl"
    path.write_text("".join(report.to_json() + "\n" for report in reports))
    run.run_fhir(path, tmp_path / "bundles")
    return {
        bundle.name: json.loads(bundle.read_text(encoding="utf-8"))
        for bundle in sorted((tmp_path / "bundles").glob("*.json"))
    }


def _observations(bundle: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
        and entry["resource"]["code"]["coding"][0]["code"] == code
    ]


def _values(observation: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Returns the system and code of each component's value, by LOINC code."""
    return {
        component["code"]["coding"][0]["code"]: (
            component["valueCodeableConcept"]["coding"][0]["system"],
            component["valueCodeableConcept"]["coding"][0]["code"],
        )
        for component in observation["component"]
    }


def _references(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        if "reference" in node:
            yield node["reference"]
        for value in node.values():
            yield from _references(value)
    elif isinstance(node, list):
        for value in node:
            yield from _references(value)


def test_a_variant_has_the_loinc_components_of_the_ig(tmp_path):
    """EHRs and FHIR searches find the gene, change and zygosity by these codes."""
    [bundle] = _export(tmp_path, [_report()]).values()

    [variant] = _observations(bundle, "69548-6")

    assert _values(variant) == {
        "48018-6": ("http://www.genenames.org", "HGNC:10585"),
        "51958-7": ("http://www.ncbi.nlm.nih.gov/refseq", "NM_001165963.4"),
        "48004-6": ("http://varnomen.hgvs.org", "NM_001165963.4:c.4933C>T"),
        "53034-5": (_LOINC, "LA6706-1"),
        "94186-4": (_LOINC, "LA26807-0"),
    }


def test_a_protein_change_without_its_reference_sequence_is_a_note(tmp_path):
    """The IG requires a valid HGVS expression, which needs the NP_ sequence."""
    [bundle] = _export(tmp_path, [_report()]).values()

    [variant] = _observations(bundle, "69548-6")

    assert variant["note"] == [{"text": "Protein change: p.(Arg1645*)"}]


def test_the_class_and_disease_are_an_implication_of_the_variant(tmp_path):
    [bundle] = _export(tmp_path, [_report()]).values()

    [variant] = _observations(bundle, "69548-6")
    [implication] = _observations(bundle, "diagnostic-implication")

    assert implication["derivedFrom"] == [{"reference": f"urn:uuid:{variant['id']}"}]
    assert _values(implication) == {
        "53037-8": (_LOINC, "LA6668-3"),
        "81259-4": ("http://purl.obolibrary.org/obo/mondo.owl", "MONDO:0100135"),
    }


def test_clinical_features_keep_their_hpo_term_and_wording(tmp_path):
    """FHIR has no value for a feature the report is unsure of, so it is left out."""
    [bundle] = _export(tmp_path, [_report()]).values()

    features = [
        (
            observation["code"]["coding"][0]["code"],
            observation["code"]["text"],
            observation["valueCodeableConcept"]["coding"][0]["code"],
        )
        for code in ("HP:0001250", "HP:0000365", "HP:0001251")
        for observation in _observations(bundle, code)
    ]

    assert features == [
        ("HP:0001250", "seizures", "LA9633-4"),
        ("HP:0000365", "no hearing loss", "LA9634-2"),
    ]


def test_every_reference_points_to_an_entry_of_the_bundle(tmp_path):
    """A FHIR server rejects a transaction whose references it can't resolve."""
    [bundle] = _export(tmp_path, [_report()]).values()

    full_urls = {entry["fullUrl"] for entry in bundle["entry"]}

    assert set(_references(bundle)) <= full_urls


def test_exporting_again_gives_the_same_resource_ids(tmp_path):
    """Posting a Bundle again then replaces its resources instead of copying them."""
    first = _export(tmp_path / "first", [_report()])

    second = _export(tmp_path / "second", [_report()])

    assert first == second


def test_reports_of_one_patient_share_one_patient(tmp_path):
    bundles = _export(tmp_path, [_report("report-01.pdf"), _report("report-02.pdf")])

    patients = [
        entry
        for bundle in bundles.values()
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Patient"
    ]

    assert len(patients) == 2
    assert patients[0] == patients[1]
