"""Rows of an OMOP CDM 5.4 database, from NormalizedReports.

Gentrex inserts into the standard tables of an existing CDM and looks up every
concept in the CDM's own vocabulary. Two tables of its own, in a schema apart
from the CDM, record the rows and persons it wrote, so that a later run
replaces only those.
"""

import csv
import dataclasses
import datetime
import logging
import pathlib
import re
import time
from typing import Any

import sqlalchemy as sa

from gentrex import records
from gentrex.export import patients
from gentrex.load import run as load_run

# Concepts with fixed IDs, as OHDSI's own ETLs use them (ETL-LambdaBuilder).
_NLP = 32858  # Type Concept "NLP", for facts derived by language processing.
_GENDERS = {"FEMALE": 8532, "MALE": 8507}
# The field that an event ID points to, by table.
_EVENT_FIELDS = {
    "procedure_occurrence": 1147082,
    "measurement": 1147138,
    "observation": 1147165,
}

# Concepts looked up by (vocabulary_id, concept_code).
_TEST = ("SNOMED", "405825005")  # Molecular genetic test
_SPECIMENS = {
    "whole_blood": "258580003",
    "saliva": "119342007",
    "buccal_swab": "733104004",
    "bone_marrow": "119359002",
    "amniotic_fluid": "119373006",
    "chorionic_villus": "258565009",
    "fibroblast": "119333000",
    "tissue": "119376003",
}
_VARIANT = ("LOINC", "69548-6")  # Genetic variant assessment
_SIGNIFICANCE = ("LOINC", "53037-8")  # Genetic variation clinical significance
_ALLELIC_STATE = ("LOINC", "53034-5")
_GENE = ("LOINC", "48018-6")  # Gene studied
_PROTEIN_CHANGE = ("LOINC", "48005-3")  # Amino acid change (pHGVS)
_PHENOTYPE = ("LOINC", "81259-4")  # Associated phenotype
_PRESENT, _ABSENT = ("LOINC", "LA9633-4"), ("LOINC", "LA9634-2")
_CLASSIFICATIONS = {
    "pathogenic": "LA6668-3",
    "likely_pathogenic": "LA26332-9",
    "uncertain_significance": "LA26333-7",
    "likely_benign": "LA26334-5",
    "benign": "LA6675-8",
}
_ZYGOSITIES = {
    "heterozygous": "LA6706-1",
    "homozygous": "LA6705-3",
    "hemizygous": "LA6707-9",
    "heteroplasmic": "LA6703-8",
    "homoplasmic": "LA6704-6",
}
_CODES = [
    _TEST,
    *(("SNOMED", code) for code in _SPECIMENS.values()),
    _VARIANT,
    _SIGNIFICANCE,
    _ALLELIC_STATE,
    _GENE,
    _PROTEIN_CHANGE,
    _PHENOTYPE,
    _PRESENT,
    _ABSENT,
    *(("LOINC", code) for code in _CLASSIFICATIONS.values()),
    *(("LOINC", code) for code in _ZYGOSITIES.values()),
]
# OMOP Genomic names the gene-level concept of each gene like this.
_GENE_CONCEPT = re.compile(r"(\S+) \(.*\) gene variant measurement")
# A concept goes to the table of its domain. The others stay where they are.
_DOMAIN_TABLES = {
    "Procedure": "procedure_occurrence",
    "Measurement": "measurement",
    "Observation": "observation",
}
_PREFIXES = {
    "procedure_occurrence": "procedure",
    "measurement": "measurement",
    "observation": "observation",
}
_EVENT_COLUMNS = {
    "measurement": ("measurement_event_id", "meas_event_field_concept_id"),
    "observation": ("observation_event_id", "obs_event_field_concept_id"),
}
_KEYS = {
    "person": "person_id",
    "observation_period": "observation_period_id",
    "procedure_occurrence": "procedure_occurrence_id",
    "specimen": "specimen_id",
    "measurement": "measurement_id",
    "observation": "observation_id",
}

_logger = logging.getLogger(__name__)


class SetupError(Exception):
    """The database can't take an OMOP export as it is."""


@dataclasses.dataclass(frozen=True)
class Schemas:
    """The database schemas of the tables, where None is the default schema.

    Attributes:
        cdm: The CDM tables.
        vocabulary: The vocabulary tables, such as CONCEPT.
        gentrex: Gentrex's two tables, which record what it wrote.
    """

    cdm: str | None
    vocabulary: str | None
    gentrex: str | None


def tables(schemas: Schemas) -> dict[str, sa.Table]:
    """Returns the tables that the export reads and writes, by name.

    The CDM tables have the columns that the export uses, as OMOP CDM 5.4
    defines them. Gentrex's own tables are omop_rows and omop_persons.
    """
    metadata = sa.MetaData()

    def cdm(name: str, *columns: sa.Column) -> sa.Table:
        return sa.Table(name, metadata, *columns, schema=schemas.cdm)

    def key(name: str) -> sa.Column:
        return sa.Column(name, sa.Integer, primary_key=True, autoincrement=False)

    def required(name: str, type_: Any = sa.Integer) -> sa.Column:
        return sa.Column(name, type_, nullable=False)

    def text(name: str, length: int = 50) -> sa.Column:
        return sa.Column(name, sa.String(length))

    def event(table: str) -> list[sa.Column]:
        return [sa.Column(name, sa.Integer) for name in _EVENT_COLUMNS[table]]

    found = [
        cdm(
            "person",
            key("person_id"),
            required("gender_concept_id"),
            required("year_of_birth"),
            sa.Column("month_of_birth", sa.Integer),
            sa.Column("day_of_birth", sa.Integer),
            required("race_concept_id"),
            required("ethnicity_concept_id"),
            text("person_source_value"),
            text("gender_source_value"),
        ),
        cdm(
            "observation_period",
            key("observation_period_id"),
            required("person_id"),
            required("observation_period_start_date", sa.Date),
            required("observation_period_end_date", sa.Date),
            required("period_type_concept_id"),
        ),
        cdm(
            "procedure_occurrence",
            key("procedure_occurrence_id"),
            required("person_id"),
            required("procedure_concept_id"),
            required("procedure_date", sa.Date),
            required("procedure_type_concept_id"),
            text("procedure_source_value"),
        ),
        cdm(
            "specimen",
            key("specimen_id"),
            required("person_id"),
            required("specimen_concept_id"),
            required("specimen_type_concept_id"),
            required("specimen_date", sa.Date),
            text("specimen_source_id"),
            text("specimen_source_value"),
        ),
        cdm(
            "measurement",
            key("measurement_id"),
            required("person_id"),
            required("measurement_concept_id"),
            required("measurement_date", sa.Date),
            required("measurement_type_concept_id"),
            sa.Column("value_as_concept_id", sa.Integer),
            text("measurement_source_value"),
            text("value_source_value"),
            *event("measurement"),
        ),
        cdm(
            "observation",
            key("observation_id"),
            required("person_id"),
            required("observation_concept_id"),
            required("observation_date", sa.Date),
            required("observation_type_concept_id"),
            text("value_as_string", 60),
            sa.Column("value_as_concept_id", sa.Integer),
            text("observation_source_value"),
            text("value_source_value"),
            *event("observation"),
        ),
        sa.Table(
            "concept",
            metadata,
            key("concept_id"),
            required("concept_name", sa.String(255)),
            required("domain_id", sa.String(20)),
            required("vocabulary_id", sa.String(20)),
            required("concept_class_id", sa.String(20)),
            text("standard_concept", 1),
            required("concept_code", sa.String(50)),
            required("valid_start_date", sa.Date),
            required("valid_end_date", sa.Date),
            text("invalid_reason", 1),
            schema=schemas.vocabulary,
        ),
        sa.Table(
            "omop_rows",
            metadata,
            sa.Column("cdm_table", sa.String(30), primary_key=True),
            sa.Column("row_id", sa.Integer, primary_key=True, autoincrement=False),
            sa.Column("file", sa.String(255), nullable=False, index=True),
            schema=schemas.gentrex,
        ),
        sa.Table(
            "omop_persons",
            metadata,
            sa.Column("patient_key", sa.String(255), primary_key=True),
            required("person_id"),
            sa.Column("observation_period_id", sa.Integer),
            schema=schemas.gentrex,
        ),
    ]
    return {table.name: table for table in found}


def read_person_map(path: pathlib.Path) -> dict[str, int]:
    """Reads the CSV file that gives the person_id of each patient_key.

    Raises:
        OSError: The file can't be read.
        ValueError: The file lacks a column, or a person_id is not a number.
    """
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = {"patient_key", "person_id"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path} lacks the columns {', '.join(sorted(missing))}")
        try:
            return {row["patient_key"].strip(): int(row["person_id"]) for row in reader}
        except ValueError as exc:
            raise ValueError(f"{path} has a person_id that is not a number") from exc


def prepare(
    engine: sa.Engine, schemas: Schemas, person_map: dict[str, int] | None
) -> None:
    """Creates Gentrex's own tables, and checks that the CDM can take the export.

    Raises:
        SetupError: A CDM or vocabulary table is missing, or the CDM holds
            persons that Gentrex didn't create while there is no person map.
    """
    found = tables(schemas)
    inspector = sa.inspect(engine)
    for name in (*_KEYS, "concept"):
        table = found[name]
        if not inspector.has_table(table.name, schema=table.schema):
            raise SetupError(
                f"the database has no table {table.fullname}; create the CDM as"
                " docs/export-omop.md shows"
            )
    own = [found["omop_rows"], found["omop_persons"]]
    with engine.begin() as conn:
        if schemas.gentrex:
            conn.execute(sa.schema.CreateSchema(schemas.gentrex, if_not_exists=True))
        own[0].metadata.create_all(conn, tables=own)
        if person_map is None:
            person, created = found["person"], found["omop_persons"]
            others = conn.execute(
                sa.select(sa.func.count()).where(
                    person.c.person_id.not_in(sa.select(created.c.person_id))
                )
            ).scalar()
            if others:
                raise SetupError(
                    f"the CDM holds {others} persons that Gentrex didn't create; set"
                    " export.omop.person_map to the file that gives each patient's"
                    " person_id"
                )


class _Concepts:
    """The concept IDs that the export needs, from the CDM's vocabulary."""

    def __init__(self, conn: sa.Connection, concept: sa.Table) -> None:
        c = concept.c
        current = (c.standard_concept == "S", c.invalid_reason.is_(None))
        rows = conn.execute(
            sa.select(c.concept_id, c.vocabulary_id, c.concept_code, c.domain_id).where(
                c.concept_code.in_({code for _, code in _CODES}), *current
            )
        ).all()
        self._found = {(r.vocabulary_id, r.concept_code): r for r in rows}
        self.missing = sorted(
            f"{v} {code}" for v, code in _CODES if (v, code) not in self._found
        )
        genes: dict[str, list[int]] = {}
        for concept_id, name in conn.execute(
            sa.select(c.concept_id, c.concept_name).where(
                c.vocabulary_id == "OMOP Genomic",
                c.concept_class_id == "Genetic Variation",
                *current,
            )
        ):
            if match := _GENE_CONCEPT.fullmatch(name):
                genes.setdefault(match[1], []).append(concept_id)
        self._genes = {symbol: ids[0] for symbol, ids in genes.items() if len(ids) == 1}

    def get(self, code: tuple[str, str]) -> tuple[int, str | None]:
        """Returns the concept ID and domain of `code`, or 0 and None."""
        row = self._found.get(code)
        return (row.concept_id, row.domain_id) if row else (0, None)

    def gene(self, symbol: str | None) -> int | None:
        """Returns the OMOP Genomic concept of variants in the gene, if any."""
        return self._genes.get(symbol or "")


class _Ids:
    """The next free primary key of each CDM table that the export writes."""

    def __init__(self, conn: sa.Connection, found: dict[str, sa.Table]) -> None:
        self._next = {
            name: (
                conn.execute(sa.select(sa.func.max(found[name].c[key]))).scalar() or 0
            )
            + 1
            for name, key in _KEYS.items()
        }

    def next(self, table: str) -> int:
        value = self._next[table]
        self._next[table] += 1
        return value


def _fit(value: Any, length: int = 50) -> str | None:
    """Returns `value` as text cut to the column's length, or None."""
    return str(value)[:length] if value not in (None, "") else None


def _date(value: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if value else None


class _Report:
    """The rows of one report, as they are built, by table."""

    def __init__(self, person_id: int, day: datetime.date, ids: _Ids) -> None:
        self.person_id = person_id
        self.day = day
        self.ids = ids
        self.rows: dict[str, list[dict[str, Any]]] = {}

    def fact(
        self,
        concept: tuple[int, str | None],
        default_table: str,
        source_value: Any,
        value_concept: tuple[int, str | None] | None = None,
        value_text: Any = None,
        event: tuple[str, int] | None = None,
        value_string: Any = None,
    ) -> tuple[str, int]:
        """Adds one row to the table of the concept's domain, and returns its key.

        A concept without a domain, such as 0, goes to `default_table`.
        `value_text` goes to value_source_value, and in OBSERVATION
        `value_string`, else `value_text`, goes to value_as_string.
        """
        concept_id, domain = concept
        table = _DOMAIN_TABLES.get(domain or "", default_table)
        if table == "procedure_occurrence" and (value_concept or value_text or event):
            table = "measurement"
        prefix = _PREFIXES[table]
        row_id = self.ids.next(table)
        row: dict[str, Any] = {
            f"{table}_id": row_id,
            "person_id": self.person_id,
            f"{prefix}_concept_id": concept_id,
            f"{prefix}_date": self.day,
            f"{prefix}_type_concept_id": _NLP,
            f"{prefix}_source_value": _fit(source_value),
        }
        if table != "procedure_occurrence":
            row["value_as_concept_id"] = value_concept[0] if value_concept else None
            row["value_source_value"] = _fit(value_text)
            event_id, event_field = _EVENT_COLUMNS[table]
            row[event_id] = event[1] if event else None
            row[event_field] = _EVENT_FIELDS[event[0]] if event else None
        if table == "observation":
            row["value_as_string"] = _fit(value_string or value_text, 60)
        self.rows.setdefault(table, []).append(row)
        return table, row_id


def _event_date(report: records.NormalizedReport) -> datetime.date | None:
    """Returns the date that every row of the report gets."""
    normalized = report.normalized or {}
    for field in (
        "collection_date",
        "received_date",
        "test_started_date",
        "report_date",
    ):
        if day := _date(normalized.get(field)):
            return day
    return None


def _rows(
    report: records.NormalizedReport,
    person_id: int,
    day: datetime.date,
    concepts: _Concepts,
    ids: _Ids,
) -> dict[str, list[dict[str, Any]]]:
    """Returns the CDM rows of one report, by table."""
    data = report.data or {}
    normalized = report.normalized or {}
    out = _Report(person_id, day, ids)
    test = out.fact(concepts.get(_TEST), "procedure_occurrence", data.get("test_name"))
    category = normalized.get("specimen_type")
    if category or data.get("specimen_type"):
        concept_id, domain = concepts.get(("SNOMED", _SPECIMENS.get(category, "")))
        out.rows["specimen"] = [
            {
                "specimen_id": ids.next("specimen"),
                "person_id": person_id,
                "specimen_concept_id": concept_id if domain == "Specimen" else 0,
                "specimen_type_concept_id": _NLP,
                "specimen_date": _date(normalized.get("collection_date")) or day,
                "specimen_source_id": _fit(data.get("lab_accession_number")),
                "specimen_source_value": _fit(data.get("specimen_type")),
            }
        ]
    variants = data.get("variants") or []
    genes = normalized.get("variants") or [{}] * len(variants)
    for variant, gene in zip(variants, genes, strict=True):
        _variant(out, variant, gene, test, concepts)
    matches = normalized.get("patient_phenotypes") or []
    features = data.get("patient_phenotypes") or []
    for feature, match in zip(features, matches or [{}] * len(features), strict=True):
        if feature.get("present") is None:
            continue
        out.fact(
            (0, None),
            "observation",
            match.get("hpo_id") or feature.get("text"),
            concepts.get(_PRESENT if feature["present"] else _ABSENT),
            feature.get("text"),
            test,
            match.get("label"),
        )
    return out.rows


def _variant(
    out: _Report,
    variant: dict[str, Any],
    gene: dict[str, Any],
    test: tuple[str, int],
    concepts: _Concepts,
) -> None:
    """Adds the rows of one variant, which point to the row of the test."""
    hgvs_c = variant.get("hgvs_c")
    transcript = variant.get("transcript")
    if hgvs_c and transcript and ":" not in hgvs_c:
        hgvs_c = f"{transcript}:{hgvs_c}"
    symbol = gene.get("gene_symbol") or variant.get("gene_symbol")
    gene_concept = concepts.gene(gene.get("gene_symbol"))
    anchor = out.fact(
        (gene_concept, "Measurement") if gene_concept else concepts.get(_VARIANT),
        "measurement",
        hgvs_c or variant.get("dna_change_raw") or symbol,
        concepts.get(_PRESENT),
        event=test,
    )
    classification = variant.get("classification")
    zygosity = variant.get("zygosity")
    attributes = [
        (
            _SIGNIFICANCE,
            _CLASSIFICATIONS.get(classification or ""),
            variant.get("classification_raw") or classification,
        ),
        (
            _ALLELIC_STATE,
            _ZYGOSITIES.get(zygosity or ""),
            variant.get("zygosity_raw") or zygosity,
        ),
        (_GENE, None, symbol),
        (_PROTEIN_CHANGE, None, variant.get("hgvs_p")),
        (
            _PHENOTYPE,
            None,
            gene.get("disease_id") or variant.get("associated_phenotype"),
        ),
    ]
    for code, answer, text in attributes:
        if not text:
            continue
        value = concepts.get(("LOINC", answer)) if answer else None
        if value is None and code != _PROTEIN_CHANGE:
            value = (0, None)
        label = gene.get("disease_label") if code == _PHENOTYPE else None
        out.fact(concepts.get(code), "measurement", code[1], value, text, anchor, label)


def _replace(
    conn: sa.Connection,
    found: dict[str, sa.Table],
    file: str,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Replaces the rows that an earlier export wrote for the file."""
    written = found["omop_rows"]
    earlier: dict[str, list[int]] = {}
    for table, row_id in conn.execute(
        sa.select(written.c.cdm_table, written.c.row_id).where(written.c.file == file)
    ):
        earlier.setdefault(table, []).append(row_id)
    for table, row_ids in earlier.items():
        key = found[table].c[_KEYS[table]]
        conn.execute(found[table].delete().where(key.in_(row_ids)))
    conn.execute(written.delete().where(written.c.file == file))
    for table, table_rows in rows.items():
        conn.execute(found[table].insert(), table_rows)
        conn.execute(
            written.insert(),
            [
                {"cdm_table": table, "row_id": row[_KEYS[table]], "file": file}
                for row in table_rows
            ],
        )


def _persons(
    conn: sa.Connection,
    found: dict[str, sa.Table],
    by_patient: dict[str, list[records.NormalizedReport]],
    person_map: dict[str, int] | None,
    ids: _Ids,
) -> dict[str, int]:
    """Returns the person_id of each patient that the CDM has or can get."""
    person = found["person"]
    if person_map is not None:
        wanted = {person_map[key] for key in by_patient if key in person_map}
        known = set(
            conn.execute(
                sa.select(person.c.person_id).where(person.c.person_id.in_(wanted))
            ).scalars()
        )
        result = {}
        for key, reports in by_patient.items():
            files = ", ".join(report.file for report in reports)
            if key not in person_map:
                _logger.warning("left out %s: the person map has no %s", files, key)
            elif person_map[key] not in known:
                _logger.warning(
                    "left out %s: the CDM has no person %d", files, person_map[key]
                )
            else:
                result[key] = person_map[key]
        return result
    created = found["omop_persons"]
    result = dict(
        conn.execute(sa.select(created.c.patient_key, created.c.person_id)).all()
    )
    for key, reports in by_patient.items():
        if key in result:
            continue
        births = patients.given(reports, patients.date_of_birth)
        if len(births) != 1:
            _logger.warning(
                "left out %s: OMOP needs a person's year of birth, and the reports"
                " give %s",
                ", ".join(report.file for report in reports),
                "different dates of birth" if births else "none",
            )
            continue
        birth = datetime.date.fromisoformat(births.pop())
        sexes = patients.given(reports, patients.sex)
        printed = next((r.data.get("sex") for r in reports if r.data.get("sex")), None)
        person_id = ids.next("person")
        conn.execute(
            person.insert(),
            {
                "person_id": person_id,
                "gender_concept_id": _GENDERS[sexes.pop()] if len(sexes) == 1 else 0,
                "year_of_birth": birth.year,
                "month_of_birth": birth.month,
                "day_of_birth": birth.day,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
                "person_source_value": _fit(key),
                "gender_source_value": _fit(printed),
            },
        )
        conn.execute(created.insert(), {"patient_key": key, "person_id": person_id})
        result[key] = person_id
    return result


def _observation_periods(
    conn: sa.Connection, found: dict[str, sa.Table], ids: _Ids
) -> None:
    """Gives each person that Gentrex created one period around its rows."""
    created = found["omop_persons"]
    period = found["observation_period"]
    dated = [
        (found["procedure_occurrence"], "procedure_date"),
        (found["specimen"], "specimen_date"),
        (found["measurement"], "measurement_date"),
        (found["observation"], "observation_date"),
    ]
    for key, person_id, period_id in conn.execute(sa.select(created)).all():
        days = [
            day
            for table, column in dated
            for day in conn.execute(
                sa.select(
                    sa.func.min(table.c[column]), sa.func.max(table.c[column])
                ).where(table.c.person_id == person_id)
            ).one()
            if day is not None
        ]
        if period_id is not None:
            conn.execute(
                period.delete().where(period.c.observation_period_id == period_id)
            )
        if not days:
            period_id = None
        else:
            period_id = period_id or ids.next("observation_period")
            conn.execute(
                period.insert(),
                {
                    "observation_period_id": period_id,
                    "person_id": person_id,
                    "observation_period_start_date": min(days),
                    "observation_period_end_date": max(days),
                    "period_type_concept_id": _NLP,
                },
            )
        conn.execute(
            created.update()
            .where(created.c.patient_key == key)
            .values(observation_period_id=period_id)
        )


def run(
    input_path: pathlib.Path,
    engine: sa.Engine,
    schemas: Schemas,
    person_map: dict[str, int] | None,
) -> list[str]:
    """Inserts every report of a run of `gentrex normalize` into the CDM.

    Each report replaces the rows that an earlier export wrote for its file, in
    one transaction. Rows that other programs wrote stay. Call prepare first.

    Args:
        input_path: JSONL file of NormalizedReports, from `gentrex normalize`.
        engine: The CDM's database.
        schemas: Where the CDM, vocabulary and Gentrex tables are.
        person_map: The person_id of each patient_key, or None to create a
            person for each patient, in a CDM that holds only Gentrex's records.

    Returns:
        Names of the files that were left out or have an error from
        `gentrex extract` or `gentrex normalize`, in input order. Reports with
        an error and data are still exported.
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        reports = [load_run.read_report(line) for line in fh]
    found = tables(schemas)
    by_patient: dict[str, list[records.NormalizedReport]] = {}
    # Only patients with a report that can be exported get a person.
    for report in reports:
        if report.data is not None and _event_date(report):
            key = load_run.patient_key(report.file, report.data)
            by_patient.setdefault(key, []).append(report)
    with engine.begin() as conn:
        concepts = _Concepts(conn, found["concept"])
        ids = _Ids(conn, found)
        people = _persons(conn, found, by_patient, person_map, ids)
    failed: list[str] = []
    exported = 0
    for report in reports:
        if report.data is None:
            _logger.warning(
                "left out %s, which has no data: %s", report.file, report.error
            )
            failed.append(report.file)
            continue
        person_id = people.get(load_run.patient_key(report.file, report.data))
        day = _event_date(report)
        if person_id is None or day is None:
            if day is None:
                _logger.warning("left out %s, which has no date", report.file)
            failed.append(report.file)
            continue
        try:
            with engine.begin() as conn:
                _replace(
                    conn,
                    found,
                    report.file,
                    _rows(report, person_id, day, concepts, ids),
                )
        except Exception as exc:  # One report's failure must not cost the others.
            _logger.error("failed %s: %s: %s", report.file, type(exc).__name__, exc)
            failed.append(report.file)
            continue
        _logger.info("exported %s", report.file)
        exported += 1
        if report.error:
            failed.append(report.file)
    if person_map is None:
        with engine.begin() as conn:
            _observation_periods(conn, found, ids)
    if concepts.missing:
        _logger.warning(
            "the vocabulary has no standard concept for %s, so their rows have"
            " concept 0",
            ", ".join(concepts.missing),
        )
    _logger.info(
        "exported %d of %d reports in %.0f s",
        exported,
        len(reports),
        time.perf_counter() - start,
    )
    return failed
