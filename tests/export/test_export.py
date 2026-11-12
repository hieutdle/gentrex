import json
import pathlib
from typing import Any

import pytest
from google.protobuf import json_format
from phenopackets import Phenopacket

from gentrex import records
from gentrex.export import pseudonyms as pseudonyms_lib
from gentrex.export import run

_VERSIONS: dict[str, str | None] = {"hpo": "2026-09-01", "mondo": "2026-11-03"}

_SCN1A = (
    {
        "gene_symbol": "SCN1A",
        "transcript": "NM_001165963.4",
        "hgvs_c": "c.4933C>T",
        "hgvs_p": "p.(Arg1645*)",
        "classification": "pathogenic",
        "zygosity": "heterozygous",
        "is_secondary_finding": False,
        "associated_phenotype": "Dravet syndrome",
    },
    {
        "gene_symbol": "SCN1A",
        "hgnc_id": "HGNC:10585",
        "disease_id": "MONDO:0100135",
        "disease_label": "Dravet syndrome",
    },
)
_BRCA2 = (
    {
        "gene_symbol": "BRCA2",
        "hgvs_c": "NM_000059.4:c.5946del",
        "classification": "pathogenic",
        "zygosity": "heterozygous",
        "is_secondary_finding": True,
        "associated_phenotype": "BRCA2-related cancer predisposition",
    },
    {"gene_symbol": "BRCA2", "hgnc_id": "HGNC:1101", "disease_id": None},
)
_MT_TL1 = (
    {
        "gene_symbol": "MT-TL1",
        "dna_change_raw": "NC_012920.1:m.3243A>G",
        "classification": "pathogenic",
        "zygosity": "heteroplasmic",
        "associated_phenotype": "MELAS",
    },
    {
        "gene_symbol": "MT-TL1",
        "hgnc_id": "HGNC:7490",
        "disease_id": "MONDO:0010789",
        "disease_label": "MELAS syndrome",
    },
)
_DUP17P = (
    {
        "dna_change_raw": "arr[GRCh37] 17p11.2(16761827_20304681)x3",
        "copy_number": 3,
        "classification": "pathogenic",
    },
    {"gene_symbol": None, "hgnc_id": None, "disease_id": None},
)


def _report(
    file: str,
    mrn: str,
    features: tuple[tuple[str, bool | None, str, str], ...] = (),
    variants: tuple[tuple[dict[str, Any], dict[str, Any]], ...] = (),
    date_of_birth: str | None = None,
    result: str | None = "positive",
    karyotype: str | None = None,
) -> records.NormalizedReport:
    """Returns a record as `gentrex normalize` writes it.

    Each feature is (text, present, HPO ID, label).
    """
    candidates = [
        {"hpo_id": hpo_id, "label": label, "models": {}}
        for _, _, hpo_id, label in features
    ]
    data = {
        "mrn": mrn,
        "sex": "Female",
        "overall_result_raw": f"{result.upper()}." if result else None,
        "karyotype": karyotype,
        "patient_phenotypes": [
            {"text": text, "present": present} for text, present, _, _ in features
        ],
        "variants": [variant for variant, _ in variants],
    }
    normalized = {
        "date_of_birth": date_of_birth,
        "overall_result": result,
        "patient_phenotypes": [
            {**candidate, "models_agree": None, "candidates": [candidate]}
            for candidate in candidates
        ],
        "variants": [gene for _, gene in variants],
    }
    return records.NormalizedReport(file, [1], data, normalized)


def _export(
    tmp_path: pathlib.Path,
    reports: list[records.NormalizedReport],
    pseudonyms: pseudonyms_lib.Pseudonyms | None = None,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Writes `reports` as `gentrex normalize` does and exports them.

    Returns:
        The failed files, and each Phenopacket by its file name.
    """
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / "normalized.jsonl"
    with path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
        fh.writelines(report.to_json() + "\n" for report in reports)
    failed = run.run(path, tmp_path / "phenopackets", _VERSIONS, pseudonyms)
    packets = {
        packet.name: json.loads(packet.read_text(encoding="utf-8"))
        for packet in sorted((tmp_path / "phenopackets").glob("*.json"))
    }
    return failed, packets


def _descriptor(packet: dict[str, Any]) -> dict[str, Any]:
    """Returns the variation descriptor of the Phenopacket's only variant."""
    [interpretation] = packet["interpretations"][0]["diagnosis"][
        "genomicInterpretations"
    ]
    return interpretation["variantInterpretation"]["variationDescriptor"]


def test_every_phenopacket_follows_the_ga4gh_schema(tmp_path):
    """Other tools read the files, so field names and values must be exact."""
    reports = [
        _report(
            "report-01.pdf",
            "SYN-MRN-0001",
            features=(
                ("global developmental delay", True, "HP:0001263", "GDD"),
                ("no hearing impairment", False, "HP:0000365", "Hearing impairment"),
                ("possible seizure", None, "HP:0001250", "Seizure"),
            ),
            variants=(_SCN1A, _BRCA2),
            date_of_birth="2018-05-14",
        ),
        _report("report-02.pdf", "SYN-MRN-0002", variants=(_MT_TL1, _DUP17P)),
        _report("report-03.pdf", "SYN-MRN-0003", result="negative", karyotype="46,XX"),
    ]

    _, packets = _export(tmp_path, reports)

    assert list(packets) == [
        "mrn_SYN-MRN-0001.json",
        "mrn_SYN-MRN-0002.json",
        "mrn_SYN-MRN-0003.json",
    ]
    for packet in packets.values():
        json_format.Parse(json.dumps(packet), Phenopacket())


def test_reports_of_one_patient_make_one_phenopacket(tmp_path):
    """A Phenopacket describes one patient, as patient_key does in `gentrex load`."""
    reports = [
        _report("report-01.pdf", "SYN-MRN-0001", variants=(_SCN1A,)),
        _report("report-02.pdf", "SYN-MRN-0001", result="negative"),
    ]

    _, packets = _export(tmp_path, reports)

    [packet] = packets.values()
    assert [i["id"] for i in packet["interpretations"]] == [
        "report-01.pdf:1",
        "report-02.pdf:1",
    ]


def test_a_feature_that_any_report_finds_present_is_not_excluded(tmp_path):
    absent = ("no hearing impairment", False, "HP:0000365", "Hearing impairment")
    present = ("hearing impairment", True, "HP:0000365", "Hearing impairment")
    reports = [
        _report("report-01.pdf", "SYN-MRN-0001", features=(absent,)),
        _report("report-02.pdf", "SYN-MRN-0001", features=(present,)),
    ]

    _, packets = _export(tmp_path, reports)

    [packet] = packets.values()
    assert packet["phenotypicFeatures"] == [
        {"type": {"id": "HP:0000365", "label": "Hearing impairment"}}
    ]


def test_a_date_of_birth_the_reports_disagree_on_is_left_out(tmp_path):
    """A misread date on one report must not become the patient's."""
    reports = [
        _report("report-01.pdf", "SYN-MRN-0001", date_of_birth="2018-05-14"),
        _report("report-02.pdf", "SYN-MRN-0001", date_of_birth="2016-05-14"),
    ]

    _, packets = _export(tmp_path, reports)

    [packet] = packets.values()
    assert packet["subject"] == {"id": "mrn:SYN-MRN-0001", "sex": "FEMALE"}


def test_a_variant_without_a_disease_id_stays_under_any_disease(tmp_path):
    """A diagnosis needs a disease, and the variant must not be lost."""
    report = _report("report-01.pdf", "SYN-MRN-0001", variants=(_SCN1A, _BRCA2))

    _, packets = _export(tmp_path, [report])

    [packet] = packets.values()
    assert [
        (i["diagnosis"]["disease"]["id"], len(i["diagnosis"]["genomicInterpretations"]))
        for i in packet["interpretations"]
    ] == [("MONDO:0100135", 1), ("MONDO:0000001", 1)]


def test_a_report_without_data_is_left_out_and_listed(tmp_path):
    reports = [
        _report("report-01.pdf", "SYN-MRN-0001"),
        records.NormalizedReport("report-02.pdf", [1], None, None, error="Timeout"),
    ]

    failed, packets = _export(tmp_path, reports)

    assert failed == ["report-02.pdf"]
    assert list(packets) == ["mrn_SYN-MRN-0001.json"]


@pytest.mark.parametrize(
    ("classification", "secondary", "status"),
    [
        ("pathogenic", False, "CANDIDATE"),
        ("uncertain_significance", None, "CANDIDATE"),
        ("pathogenic", True, "UNKNOWN_STATUS"),
        ("likely_benign", False, "REJECTED"),
    ],
)
def test_only_primary_findings_are_candidates(
    tmp_path, classification, secondary, status
):
    """Gentrex doesn't claim a cause; secondary findings aren't about the indication."""
    variant = {
        **_SCN1A[0],
        "classification": classification,
        "is_secondary_finding": secondary,
    }
    report = _report("report-01.pdf", "SYN-MRN-0001", variants=((variant, _SCN1A[1]),))

    _, packets = _export(tmp_path, [report])

    [packet] = packets.values()
    [interpretation] = packet["interpretations"][0]["diagnosis"][
        "genomicInterpretations"
    ]
    assert interpretation["interpretationStatus"] == status


def test_an_array_result_is_an_iscn_expression(tmp_path):
    """ISCN is the syntax that the Phenopacket schema names for array results."""
    report = _report("report-01.pdf", "SYN-MRN-0001", variants=(_DUP17P,))

    _, packets = _export(tmp_path, [report])

    [packet] = packets.values()
    assert _descriptor(packet)["expressions"] == [
        {"syntax": "iscn", "value": "arr[GRCh37] 17p11.2(16761827_20304681)x3"}
    ]


@pytest.mark.parametrize(
    ("change", "copies", "structural_type"),
    [
        ("arr[GRCh37] 17p11.2(16761827_20304681)x3", 3, "SO:0001911"),
        ("arr[GRCh37] 22q11.21(18648855_21800471)x1", 1, "SO:0001912"),
        ("arr[GRCh37] Xp22.31(6455151_8135644)x1", 1, None),
        ("SMN1 copy number: 0", 0, "SO:0001912"),
        ("SMN1 copy number: 1", 1, None),
    ],
)
def test_a_copy_number_is_a_gain_or_loss_only_when_that_is_certain(
    tmp_path, change, copies, structural_type
):
    """One copy is a loss on an autosome, but normal on a male's X."""
    variant = {"dna_change_raw": change, "copy_number": copies}
    report = _report("report-01.pdf", "SYN-MRN-0001", variants=((variant, {}),))

    _, packets = _export(tmp_path, [report])

    [packet] = packets.values()
    assert _descriptor(packet).get("structuralType", {}).get("id") == structural_type


@pytest.mark.parametrize(
    ("karyotype", "karyotypic_sex"),
    [
        ("46,XY", "XY"),
        ("45,X", "XO"),
        ("47,XXY", "XXY"),
        ("47,XX,+21", "XX"),
        ("mos 45,X[10]/46,XX[20]", "OTHER_KARYOTYPE"),
        ("46,X,i(X)(q10)", "OTHER_KARYOTYPE"),
    ],
)
def test_the_karyotypic_sex_comes_from_the_sex_chromosomes(
    tmp_path, karyotype, karyotypic_sex
):
    """An isochromosome X, as in 46,X,i(X)(q10), is neither XO nor XX."""
    report = _report("report-01.pdf", "SYN-MRN-0001", karyotype=karyotype)

    _, packets = _export(tmp_path, [report])

    [packet] = packets.values()
    assert packet["subject"]["karyotypicSex"] == karyotypic_sex


def test_pseudonymous_phenopackets_hold_no_mrn_file_name_or_birth_date(tmp_path):
    """Shared Phenopackets go to people who may not see who the patient is."""
    report = _report(
        "report-01.pdf",
        "SYN-MRN-0001",
        variants=(_SCN1A,),
        date_of_birth="2018-05-14",
    )

    _, packets = _export(tmp_path, [report], pseudonyms_lib.Pseudonyms("secret"))

    [(name, packet)] = packets.items()
    text = json.dumps(packet)
    assert name == f"{packet['id']}.json"
    assert "SYN-MRN-0001" not in text
    assert "report-01" not in text
    assert "dateOfBirth" not in packet["subject"]


def test_the_same_key_gives_the_same_pseudonyms_in_every_run(tmp_path):
    """Phenopackets shared later must match the ones shared before."""
    report = _report("report-01.pdf", "SYN-MRN-0001", variants=(_SCN1A,))

    _, first = _export(tmp_path / "first", [report], pseudonyms_lib.Pseudonyms("key"))
    _, second = _export(tmp_path / "second", [report], pseudonyms_lib.Pseudonyms("key"))

    assert list(first) == list(second)
