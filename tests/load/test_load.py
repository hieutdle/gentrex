import json
import pathlib
from typing import Any

import pytest
import sqlalchemy as sa

from gentrex import records
from gentrex.load import hpo
from gentrex.load import run

_OBO = "http://purl.obolibrary.org/obo/"

_NO_TERMS = hpo.HpoTree({}, {}, sha256="0" * 64)


def _select(engine: sa.Engine, query: str) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(sa.text(query))]


def _load(
    engine: sa.Engine,
    tmp_path: pathlib.Path,
    reports: list[records.NormalizedReport],
    tree: hpo.HpoTree = _NO_TERMS,
) -> list[str]:
    """Writes `reports` as `gentrex normalize` does and loads them.

    Returns:
        The failed files.
    """
    path = tmp_path / "normalized.jsonl"
    with path.open("w", encoding="utf-8", errors="backslashreplace") as fh:
        fh.writelines(report.to_json() + "\n" for report in reports)
    return run.run(path, engine, tree)


def _match(hpo_id: str, label: str) -> dict[str, Any]:
    """Returns the match of a feature, as `gentrex normalize` writes it.

    The term is the only candidate.
    """
    models = {"words": {"name": label, "similarity": 1.0}}
    candidate = {"hpo_id": hpo_id, "label": label, "models": models}
    return {**candidate, "models_agree": None, "candidates": [candidate]}


def _tree(sha256: str, **labels: str) -> hpo.HpoTree:
    """Returns a tree of unrelated terms, each its own only ancestor."""
    return hpo.HpoTree(
        labels, {term: frozenset({term}) for term in labels}, sha256=sha256
    )


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


def test_a_database_that_is_not_supported_is_refused():
    """The URL must fail at once, not after the HPO release was read."""
    with pytest.raises(ValueError, match="oracle is not a supported database"):
        run.make_engine("oracle://scott:tiger@127.0.0.1/orcl")


def test_loading_a_file_again_replaces_its_rows(engine, tmp_path):
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
    _load(engine, tmp_path, [first, other])
    second = records.NormalizedReport(
        "a.pdf", [1], {"variants": [{"gene_symbol": "MECP2"}]}, None
    )

    _load(engine, tmp_path, [second])

    assert _select(
        engine, "SELECT file, gene_symbol_raw FROM variants ORDER BY file"
    ) == [("a.pdf", "MECP2"), ("b.pdf", "CFTR")]
    assert _select(engine, "SELECT count(*) FROM patient_phenotypes") == [(0,)]


def test_a_report_that_fails_to_load_keeps_its_earlier_rows(engine, tmp_path):
    """Each report is one transaction, so its failure costs no rows of others."""
    earlier = records.NormalizedReport("a.pdf", [1], {"variants": [{"page": 1}]}, None)
    _load(engine, tmp_path, [earlier])
    broken = records.NormalizedReport(
        "a.pdf",
        [1],
        {
            "variants": [{"page": 2}],
            "patient_phenotypes": [{"text": None, "present": True}],
        },
        None,
    )
    no_data = records.NormalizedReport("b.pdf", [1], None, None, error="TimeoutError")
    complete = records.NormalizedReport("c.pdf", [1], {"variants": []}, None)

    failed = _load(engine, tmp_path, [broken, no_data, complete])

    assert failed == ["a.pdf", "b.pdf"]
    assert _select(engine, "SELECT file FROM reports ORDER BY file") == [
        ("a.pdf",),
        ("c.pdf",),
    ]
    assert _select(engine, "SELECT page FROM variants") == [(1,)]


def test_half_a_surrogate_pair_is_loaded_as_a_replacement_character(engine, tmp_path):
    """`gentrex extract` keeps it as a JSON escape, but no database can store it."""
    report = records.NormalizedReport("a.pdf", [1], {"test_name": "Panel \ud835"}, None)

    assert _load(engine, tmp_path, [report]) == []
    assert _select(engine, "SELECT test_name FROM reports") == [("Panel �",)]


def test_a_feature_is_found_under_every_term_above_its_match(engine, tmp_path):
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
        sha256="1" * 64,
    )
    report = records.NormalizedReport(
        "a.pdf",
        [1],
        {"patient_phenotypes": [{"text": "mild ID", "present": True}]},
        {"patient_phenotypes": [_match("HP:0001256", "Mild intellectual disability")]},
    )
    _load(engine, tmp_path, [report], tree)

    found = _select(
        engine,
        "SELECT p.file FROM patient_phenotypes p"
        " JOIN hpo_ancestors a ON a.hpo_id = p.hpo_id"
        " WHERE a.ancestor_id = 'HP:0001249'",
    )

    assert found == [("a.pdf",)]


def test_hpo_terms_are_loaded_again_only_when_the_release_changes(engine, tmp_path):
    """Loading 223,079 ancestor rows on every run would be the slowest step."""
    first = _tree("a" * 64, **{"HP:0000001": "All"})
    _load(engine, tmp_path, [], first)
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM hpo_terms"))

    _load(engine, tmp_path, [], first)
    assert _select(engine, "SELECT count(*) FROM hpo_terms") == [(0,)]

    second = _tree("b" * 64, **{"HP:0000118": "Phenotypic abnormality"})
    _load(engine, tmp_path, [], second)
    assert _select(engine, "SELECT hpo_id FROM hpo_terms") == [("HP:0000118",)]


@pytest.mark.parametrize(
    "stored", [2, 1, None], ids=["version-2", "version-1", "no-version"]
)
def test_a_database_with_older_tables_is_refused(engine, tmp_path, stored):
    """`gentrex load` never changes a table, so loading into old tables would fail."""
    _load(engine, tmp_path, [])
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM schema_version"))
        if stored is not None:
            conn.execute(sa.text(f"INSERT INTO schema_version VALUES ({stored})"))

    with pytest.raises(run.TableVersionError, match=f"holds version {stored or 1} "):
        _load(engine, tmp_path, [])
