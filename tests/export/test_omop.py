import datetime
import pathlib
from typing import Any

import pytest
import sqlalchemy as sa

from gentrex import records
from gentrex.export import omop

_SCHEMAS = omop.Schemas(cdm=None, vocabulary=None, gentrex=None)

# Concepts of a small test vocabulary: (concept_id, vocabulary, code, domain).
_VOCABULARY = [
    (1001, "SNOMED", "405825005", "Procedure"),
    (1002, "SNOMED", "258580003", "Specimen"),
    (2001, "LOINC", "69548-6", "Measurement"),
    (2002, "LOINC", "53037-8", "Measurement"),
    (2003, "LOINC", "53034-5", "Measurement"),
    (2004, "LOINC", "48018-6", "Measurement"),
    (2006, "LOINC", "81259-4", "Observation"),
    (3001, "LOINC", "LA9633-4", "Meas Value"),
    (3002, "LOINC", "LA9634-2", "Meas Value"),
    (3003, "LOINC", "LA6668-3", "Meas Value"),
    (3004, "LOINC", "LA6706-1", "Meas Value"),
]
_SCN1A_CONCEPT = 4001


@pytest.fixture
def cdm(engine):
    """A CDM with the tables of the export and the test vocabulary."""
    found = omop.tables(_SCHEMAS)
    cdm_tables = [
        "person",
        "observation_period",
        "procedure_occurrence",
        "specimen",
        "measurement",
        "observation",
        "concept",
    ]
    found["concept"].metadata.create_all(
        engine, tables=[found[name] for name in cdm_tables]
    )
    day = datetime.date(1970, 1, 1)
    end = datetime.date(2099, 12, 31)
    rows = [
        {
            "concept_id": concept_id,
            "concept_name": code,
            "domain_id": domain,
            "vocabulary_id": vocabulary,
            "concept_class_id": "Test",
            "standard_concept": "S",
            "concept_code": code,
            "valid_start_date": day,
            "valid_end_date": end,
        }
        for concept_id, vocabulary, code, domain in _VOCABULARY
    ]
    rows.append(
        {
            "concept_id": _SCN1A_CONCEPT,
            "concept_name": "SCN1A (sodium voltage-gated channel alpha subunit 1)"
            " gene variant measurement",
            "domain_id": "Measurement",
            "vocabulary_id": "OMOP Genomic",
            "concept_class_id": "Genetic Variation",
            "standard_concept": "S",
            "concept_code": "OMOP4001",
            "valid_start_date": day,
            "valid_end_date": end,
        }
    )
    with engine.begin() as conn:
        conn.execute(found["concept"].insert(), rows)
    return engine


def _report(
    file: str = "report-01.pdf",
    mrn: str = "SYN-MRN-0001",
    gene: str = "SCN1A",
    date_of_birth: str | None = "2018-05-14",
) -> records.NormalizedReport:
    data = {
        "mrn": mrn,
        "sex": "Female",
        "test_name": "Epilepsy Panel",
        "specimen_type": "Blood in EDTA",
        "patient_phenotypes": [
            {"text": "seizures", "present": True},
            {"text": "no hearing loss", "present": False},
        ],
        "variants": [
            {
                "gene_symbol": gene,
                "transcript": "NM_001165963.4",
                "hgvs_c": "c.4933C>T",
                "classification": "pathogenic",
                "zygosity": "heterozygous",
                "associated_phenotype": "Dravet syndrome",
            }
        ],
    }
    normalized = {
        "date_of_birth": date_of_birth,
        "collection_date": "2026-08-27",
        "specimen_type": "whole_blood",
        "patient_phenotypes": [
            {"hpo_id": "HP:0001250", "label": "Seizure"},
            {"hpo_id": "HP:0000365", "label": "Hearing impairment"},
        ],
        "variants": [
            {
                "gene_symbol": gene,
                "hgnc_id": "HGNC:10585",
                "disease_id": "MONDO:0100135",
            }
        ],
    }
    return records.NormalizedReport(file, [1], data, normalized)


def _export(
    engine: sa.Engine,
    tmp_path: pathlib.Path,
    reports: list[records.NormalizedReport],
    person_map: dict[str, int] | None = None,
    extended: bool = False,
) -> list[str]:
    """Writes `reports` as `gentrex normalize` does, and exports them."""
    path = tmp_path / "normalized.jsonl"
    path.write_text("".join(report.to_json() + "\n" for report in reports))
    omop.prepare(engine, _SCHEMAS, person_map, extended)
    return omop.run(path, engine, _SCHEMAS, person_map, extended)


def _rows(engine: sa.Engine, table: str, *columns: str) -> list[tuple[Any, ...]]:
    found = omop.tables(_SCHEMAS)[table]
    key = found.c[f"{table}_id"]
    with engine.connect() as conn:
        query = sa.select(*(found.c[c] for c in columns)).order_by(key)
        return [tuple(row) for row in conn.execute(query)]


def test_a_variant_is_a_gene_measurement_with_its_class_and_zygosity(cdm, tmp_path):
    """Cohorts in ATLAS select by the gene concept and by the LOINC answers."""
    assert _export(cdm, tmp_path, [_report()]) == []

    [test] = _rows(cdm, "procedure_occurrence", "procedure_occurrence_id")
    measurements = _rows(
        cdm,
        "measurement",
        "measurement_id",
        "measurement_concept_id",
        "value_as_concept_id",
        "measurement_event_id",
        "meas_event_field_concept_id",
    )
    variant = measurements[0]
    assert variant[1:] == (_SCN1A_CONCEPT, 3001, test[0], 1147082)
    assert (2002, 3003, variant[0], 1147138) in [row[1:] for row in measurements]
    assert (2003, 3004, variant[0], 1147138) in [row[1:] for row in measurements]


def test_a_concept_goes_to_the_table_of_its_domain(cdm, tmp_path):
    """The CDM requires it, so the associated phenotype, an Observation, moves."""
    _export(cdm, tmp_path, [_report()])

    observations = _rows(
        cdm, "observation", "observation_concept_id", "value_source_value"
    )

    assert (2006, "MONDO:0100135") in observations


def test_a_gene_without_a_genomic_concept_is_a_variant_assessment(cdm, tmp_path):
    """Without an OMOP Genomic concept, the variant must still be counted."""
    _export(cdm, tmp_path, [_report(gene="SYN1")])

    measurements = _rows(
        cdm, "measurement", "measurement_concept_id", "measurement_source_value"
    )

    assert measurements[0] == (2001, "NM_001165963.4:c.4933C>T")
    assert (2004, "48018-6") in measurements


def test_clinical_features_keep_their_hpo_id_and_wording(cdm, tmp_path):
    """OMOP has no HPO vocabulary, so the ID must survive as the source value."""
    _export(cdm, tmp_path, [_report()])

    observations = _rows(
        cdm,
        "observation",
        "observation_concept_id",
        "observation_source_value",
        "value_as_concept_id",
        "value_as_string",
        "value_source_value",
    )

    assert (0, "HP:0001250", 3001, "Seizure", "seizures") in observations
    assert (0, "HP:0000365", 3002, "Hearing impairment", "no hearing loss") in (
        observations
    )


def test_exporting_a_file_again_replaces_only_its_own_rows(cdm, tmp_path):
    """Rows of other ETLs in the same CDM must never be touched."""
    found = omop.tables(_SCHEMAS)
    with cdm.begin() as conn:
        conn.execute(
            found["person"].insert(),
            {
                "person_id": 7,
                "gender_concept_id": 8532,
                "year_of_birth": 2018,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            },
        )
        conn.execute(
            found["measurement"].insert(),
            {
                "measurement_id": 1,
                "person_id": 7,
                "measurement_concept_id": 9999,
                "measurement_date": datetime.date(2020, 1, 1),
                "measurement_type_concept_id": 32817,
            },
        )
    person_map = {"mrn:SYN-MRN-0001": 7}
    _export(cdm, tmp_path, [_report(gene="SCN1A")], person_map)

    _export(cdm, tmp_path, [_report(gene="SYN1")], person_map)

    concepts = [row[0] for row in _rows(cdm, "measurement", "measurement_concept_id")]
    assert concepts[0] == 9999
    assert _SCN1A_CONCEPT not in concepts
    assert concepts.count(2001) == 1


def test_a_patient_missing_from_the_person_map_is_left_out(cdm, tmp_path):
    """Guessing a person in a shared CDM would put the results on someone else."""
    failed = _export(cdm, tmp_path, [_report()], person_map={})

    assert failed == ["report-01.pdf"]
    assert _rows(cdm, "measurement", "measurement_id") == []


def test_a_created_person_needs_a_year_of_birth(cdm, tmp_path):
    """OHDSI drops persons without a year of birth, so Gentrex creates none."""
    reports = [_report(), _report("report-02.pdf", "SYN-MRN-0002", date_of_birth=None)]

    failed = _export(cdm, tmp_path, reports)

    assert failed == ["report-02.pdf"]
    assert _rows(
        cdm, "person", "gender_concept_id", "year_of_birth", "person_source_value"
    ) == [(8532, 2018, "mrn:SYN-MRN-0001")]
    assert _rows(
        cdm,
        "observation_period",
        "observation_period_start_date",
        "observation_period_end_date",
    ) == [(datetime.date(2026, 8, 27), datetime.date(2026, 8, 27))]


def test_persons_are_not_created_in_a_cdm_with_other_persons(cdm, tmp_path):
    """In an institutional CDM, new persons would duplicate real patients."""
    with cdm.begin() as conn:
        conn.execute(
            omop.tables(_SCHEMAS)["person"].insert(),
            {
                "person_id": 7,
                "gender_concept_id": 0,
                "year_of_birth": 1990,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            },
        )

    with pytest.raises(omop.SetupError, match="persons that Gentrex didn't create"):
        omop.prepare(cdm, _SCHEMAS, None)


def test_the_extended_export_keeps_what_omop_cannot_hold(cdm, tmp_path):
    """Source values stop at 50 characters, and OMOP has no parental origin."""
    report = _report()
    assert report.data is not None
    deletion = "Deletion of exons 1 to 26 of SCN1A, including the promoter region"
    report.data["variants"][0].update(
        dna_change_raw=deletion, parental_origin="de_novo"
    )

    _export(cdm, tmp_path, [report], extended=True)

    [variant] = _rows(cdm, "measurement", "measurement_id")[:1]
    found = omop.tables(_SCHEMAS)["genomic_variant"]
    with cdm.connect() as conn:
        rows = conn.execute(
            sa.select(
                found.c.cdm_table,
                found.c.cdm_row_id,
                found.c.dna_change_raw,
                found.c.parental_origin,
            )
        ).all()
    assert [tuple(row) for row in rows] == [
        ("measurement", variant[0], deletion, "de_novo")
    ]


def test_the_extended_export_keeps_the_karyotype_genome_build_and_copy_number(
    cdm, tmp_path
):
    """The CDM rows hold none of the three, and a copy number of 0 is a result."""
    report = _report()
    assert report.data is not None
    report.data.update(karyotype="46,XX", genome_build="GRCh37")
    report.data["variants"][0]["copy_number"] = 0

    _export(cdm, tmp_path, [report], extended=True)

    found = omop.tables(_SCHEMAS)
    test, variant = found["genomic_test"], found["genomic_variant"]
    with cdm.connect() as conn:
        karyotype = conn.execute(sa.select(test.c.karyotype, test.c.genome_build)).one()
        copies = conn.execute(sa.select(variant.c.copy_number)).scalar_one()
    assert (tuple(karyotype), copies) == (("46,XX", "GRCh37"), 0)


def test_exporting_again_replaces_the_extension_rows(cdm, tmp_path):
    _export(cdm, tmp_path, [_report()], extended=True)

    _export(cdm, tmp_path, [_report()], extended=True)

    found = omop.tables(_SCHEMAS)["phenotype_feature"]
    with cdm.connect() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(found)).scalar()
    assert count == 2


def test_the_plain_export_creates_no_extension_tables(cdm, tmp_path):
    """`gentrex export omop` must leave the database to the standard tables."""
    _export(cdm, tmp_path, [_report()])

    assert not sa.inspect(cdm).has_table("genomic_variant")
