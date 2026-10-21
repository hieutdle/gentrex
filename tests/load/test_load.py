import json
import os
import pathlib
import uuid
from typing import Any

import psycopg
import pytest
from psycopg import sql

from gentrex import records
from gentrex.load import hpo
from gentrex.load import run

_OBO = "http://purl.obolibrary.org/obo/"

_NO_TERMS = hpo.HpoTree({}, {})


@pytest.fixture
def conn():
    """A connection whose tables go to a new schema, dropped afterwards."""
    url = os.environ.get("GENTREX_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set GENTREX_TEST_DATABASE_URL to run the database tests")
    schema = sql.Identifier(f"test_{uuid.uuid4().hex}")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        conn.execute(sql.SQL("SET search_path TO {}").format(schema))
        yield conn
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))


def _load(
    conn: psycopg.Connection,
    tmp_path: pathlib.Path,
    reports: list[records.NormalizedReport],
    tree: hpo.HpoTree = _NO_TERMS,
) -> list[str]:
    """Writes `reports` as stage 4 does, loads them and returns the failed files."""
    path = tmp_path / "normalized.jsonl"
    with path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
        fh.writelines(report.to_json() + "\n" for report in reports)
    return run.run(path, conn, tree)


def _match(hpo_id: str, label: str) -> dict[str, Any]:
    """Returns stage 4's match of a feature, with the term as only candidate."""
    models = {"words": {"name": label, "similarity": 1.0}}
    candidate = {"hpo_id": hpo_id, "label": label, "models": models}
    return {**candidate, "models_agree": None, "candidates": [candidate]}


def test_ancestors_are_the_term_and_every_term_above_it(tmp_path):
    """A term reached by two paths, as Seizure is here, must be listed once."""
    labels = {
        "0001250": "Seizure",
        "0007359": "Focal-onset seizure",
        "0011146": "Dialeptic seizure",
        "0002384": "Focal impaired awareness seizure",
    }
    links = [
        ("0007359", "0001250"),
        ("0011146", "0001250"),
        ("0002384", "0007359"),
        ("0002384", "0011146"),
    ]
    graph = {
        "nodes": [
            {"id": f"{_OBO}HP_{n}", "type": "CLASS", "lbl": label}
            for n, label in labels.items()
        ],
        "edges": [
            {"sub": f"{_OBO}HP_{child}", "pred": "is_a", "obj": f"{_OBO}HP_{parent}"}
            for child, parent in links
        ],
    }
    release = tmp_path / "hp-base.json"
    release.write_text(json.dumps({"graphs": [graph]}))

    tree = hpo.HpoTree.from_release(release)

    assert tree.ancestors["HP:0002384"] == {
        "HP:0002384",
        "HP:0007359",
        "HP:0011146",
        "HP:0001250",
    }


@pytest.mark.parametrize(
    ("data", "key"),
    [
        (
            {"mrn": "SYN-MRN-0001", "submitter_patient_id": "SYN-SUB-0002"},
            "mrn:SYN-MRN-0001",
        ),
        (
            {"mrn": None, "submitter_patient_id": "SYN-SUB-0002"},
            "submitter:SYN-SUB-0002",
        ),
        ({"mrn": " ", "submitter_patient_id": None}, "file:report-04.pdf"),
    ],
)
def test_patient_key_is_the_mrn_else_the_submitter_id_else_the_file(data, key):
    assert run.patient_key("report-04.pdf", data) == key


def test_loading_a_file_again_replaces_its_rows(conn, tmp_path):
    """A rerun must not keep the variants or features of the earlier load."""
    first = records.NormalizedReport(
        "a.pdf",
        [1],
        {
            "variants": [{"gene_symbol": "BRCA1"}, {"gene_symbol": "BRCA2"}],
            "patient_phenotypes": [{"text": "Seizure", "present": True}],
        },
        {"variants": [{}, {}], "patient_phenotypes": [_match("HP:0001250", "Seizure")]},
    )
    other = records.NormalizedReport(
        "b.pdf", [1], {"variants": [{"gene_symbol": "CFTR"}]}, None
    )
    _load(conn, tmp_path, [first, other])
    second = records.NormalizedReport(
        "a.pdf", [1], {"variants": [{"gene_symbol": "MECP2"}]}, None
    )

    _load(conn, tmp_path, [second])

    assert conn.execute(
        "SELECT file, gene_symbol_raw FROM variants ORDER BY file"
    ).fetchall() == [("a.pdf", "MECP2"), ("b.pdf", "CFTR")]
    assert conn.execute("SELECT count(*) FROM patient_phenotypes").fetchone() == (0,)


def test_a_report_that_fails_to_load_keeps_its_earlier_rows(conn, tmp_path):
    """Each report is one transaction, so its failure costs no rows of others."""
    earlier = records.NormalizedReport("a.pdf", [1], {"variants": [{"page": 1}]}, None)
    _load(conn, tmp_path, [earlier])
    broken = records.NormalizedReport(
        "a.pdf", [1], {"variants": [{"page": "one"}]}, None
    )
    no_data = records.NormalizedReport("b.pdf", [1], None, None, error="TimeoutError")
    complete = records.NormalizedReport("c.pdf", [1], {"variants": []}, None)

    failed = _load(conn, tmp_path, [broken, no_data, complete])

    assert failed == ["a.pdf", "b.pdf"]
    assert conn.execute("SELECT file FROM reports ORDER BY file").fetchall() == [
        ("a.pdf",),
        ("c.pdf",),
    ]
    assert conn.execute("SELECT page FROM variants").fetchall() == [(1,)]


def test_half_a_surrogate_pair_is_loaded_as_a_replacement_character(conn, tmp_path):
    """Stage 3 keeps it as a JSON escape, but PostgreSQL text can't hold it."""
    report = records.NormalizedReport("a.pdf", [1], {"test_name": "Panel \ud835"}, None)

    assert _load(conn, tmp_path, [report]) == []
    assert conn.execute("SELECT test_name FROM reports").fetchone() == ("Panel \ufffd",)


def test_a_feature_is_found_under_every_term_above_its_match(conn, tmp_path):
    """A query on a broad term must find the features matched to narrower ones."""
    tree = hpo.HpoTree(
        {
            "HP:0001249": "Intellectual disability",
            "HP:0001256": "Mild intellectual disability",
        },
        {
            "HP:0001249": frozenset({"HP:0001249"}),
            "HP:0001256": frozenset({"HP:0001256", "HP:0001249"}),
        },
    )
    report = records.NormalizedReport(
        "a.pdf",
        [1],
        {"patient_phenotypes": [{"text": "mild ID", "present": True}]},
        {"patient_phenotypes": [_match("HP:0001256", "Mild intellectual disability")]},
    )
    _load(conn, tmp_path, [report], tree)

    found = conn.execute(
        "SELECT p.file FROM patient_phenotypes p"
        " JOIN hpo_ancestors a ON a.hpo_id = p.hpo_id"
        " WHERE a.ancestor_id = 'HP:0001249'"
    ).fetchall()

    assert found == [("a.pdf",)]
