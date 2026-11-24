"""The tables and figures of evaluation_results/benchruns.py.

They read what the scorer writes, so a number that the scorer renames or
drops would otherwise only show when someone opens a notebook.
"""

import pathlib
import sys

import pytest
import yaml

pytest.importorskip("pandas")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

_ROOT = pathlib.Path(__file__).parents[1]
sys.path[:0] = [
    str(_ROOT / "evaluation_results"),
    str(_ROOT / "tests"),
    str(_ROOT / "gentrex-bench"),
]

import benchruns  # noqa: E402
import run as bench_run  # noqa: E402
import score  # noqa: E402
import test_bench_scorer as scorer_tests  # noqa: E402


def _run(tmp_path, change=None):
    """Returns the scores and the errors of a run of one report."""
    truth = scorer_tests._truth()
    pages = enumerate(scorer_tests._PAGES, 1)
    truth["pages"] = [{"page": number, "text": text} for number, text in pages]
    report = scorer_tests._report(truth)
    report["pages"] = [1, 2]
    term = {"hpo_id": "HP:0002515", "label": "Waddling gait"}
    report["normalized"]["patient_phenotypes"] = [
        {**term, "models_agree": True, "candidates": [{**term, "models": {}}]}
    ]
    for variant in report["normalized"]["variants"]:
        variant["gene_symbol"] = "DMD"
    if change:
        change(report)
    truth_dir, run_dir = scorer_tests._write_run(tmp_path, [truth], [report])
    transcribe_dir = run_dir.parents[1] / "transcribe" / run_dir.name
    transcribed = [
        {
            "file": "SYN-0001.pdf",
            "page": number,
            "source": "native",
            "text": text,
        }
        for number, text in enumerate(scorer_tests._PAGES, 1)
    ]
    (transcribe_dir / "pages.jsonl").write_text(
        "".join(benchruns.json.dumps(p) + "\n" for p in transcribed)
    )
    select_dir = run_dir.parents[1] / "select" / run_dir.name
    decisions = [
        {"file": "SYN-0001.pdf", "page": page, "p_yes": {"has_result": p}, "keep": True}
        for page, p in ((1, 0.9), (2, 0.7))
    ]
    text = "".join(benchruns.json.dumps(d) + "\n" for d in decisions)
    (select_dir / "decisions.jsonl").write_text(text)
    record = yaml.safe_load((select_dir / "run.yaml").read_text())
    record["settings"] |= {"keep_threshold": 0.5, "model": "fake"}
    (select_dir / "run.yaml").write_text(yaml.safe_dump(record))
    return score.score(truth_dir, run_dir, [1, 1, 2])


def test_every_table_and_figure_reads_the_scores_of_a_run(tmp_path, monkeypatch):
    def wrong_specimen(report):
        report["data"]["specimen_type"] = "Blood"

    scores, errors = _run(tmp_path, wrong_specimen)
    runs = {"20261118-120000": scores}
    chosen = {benchruns.setup_of(scores): scores}
    found = benchruns.pd.DataFrame(errors).assign(flagged=None)
    monkeypatch.setattr(benchruns, "EXPORT", tmp_path / "paper")
    monkeypatch.setattr(benchruns.plt, "show", lambda: None)

    tables = [
        benchruns.runs_table(runs),
        benchruns.setup_table(scores),
        benchruns.data_table(scores),
        benchruns.main_table(chosen),
        benchruns.safety_table(chosen),
        benchruns.clinical_errors_table(chosen),
        benchruns.transcribe_table(chosen),
        benchruns.select_pages_table(chosen),
        benchruns.questions_table(scores),
        benchruns.extract_table(chosen),
        benchruns.hpo_table(scores),
        benchruns.stages_table(chosen),
        benchruns.efficiency_table(chosen),
        benchruns.entities_table(scores),
        benchruns.fields_table(scores),
        benchruns.normalize_table(scores),
        benchruns.checks_table(scores),
        benchruns.review_table(scores),
        benchruns.variant_kinds_table(scores),
        benchruns.repeats_table(runs | {"20261118-130000": scores}),
        benchruns.wrong_reports_table(scores, found),
        benchruns.errors_table(found),
    ]
    benchruns.accuracy_figure(chosen)
    benchruns.stages_figure(chosen)
    benchruns.select_figure(scores)
    benchruns.fields_figure(scores)
    benchruns.errors_figure(scores)
    benchruns.confusion_figure(scores)
    benchruns.groups_figure(scores, ("kind", "scenario", "pages", "challenge"))
    assert benchruns.findings(scores, chosen)

    assert all(len(table.columns) for table in tables[:19])
    main = benchruns.main_table(chosen).loc["native"]
    assert main["Report accuracy"].startswith("100.0")
    assert main["Every value right"].startswith("0.0")
    safety = benchruns.safety_table(chosen)
    assert {"P/LP variant recall, %", "Actionable ACMG F1, %"} <= set(safety.columns)
    assert "Completed reports, %" in benchruns.efficiency_table(chosen).index
    assert "Workload avoided, %" in benchruns.review_table(scores).columns
    written = {path.name for path in (tmp_path / "paper").iterdir()}
    assert {
        "table-main.csv",
        "table-main.tex",
        "table-clinical-errors.tex",
        "figure-accuracy.pdf",
    } <= written


def test_the_ways_to_choose_pages_and_the_speed_of_a_command_are_tables(tmp_path):
    """They read what gentrex-bench/run.py adds to the scores of a run."""
    scores, _ = _run(tmp_path)
    bench_run.add_select_methods(scores, {}, tmp_path / "v1" / "truth")

    methods = benchruns.select_methods_table(scores)
    speed = benchruns.speed_table({"native": scores}, "select")

    assert methods.index.tolist() == [benchruns.SELECT_METHOD_LABELS["questions"]]
    assert methods.iloc[0]["Needed pages kept, %"] == "100.0"
    assert "Page AUROC" in methods.columns
    assert methods.iloc[0]["Pages per minute"] == round(2 * 60 / 36)
    assert speed.loc["native", "Seconds per report"] == 36.0


def test_runs_of_an_older_scorer_are_left_out(tmp_path, monkeypatch, capsys):
    """Their scores.json lacks numbers that the tables read."""
    scores, _ = _run(tmp_path)
    for name, version in (("20261117-201846", 1), ("20261118-120000", score.FORMAT)):
        folder = tmp_path / "results" / "gentrex-bench" / name
        folder.mkdir(parents=True)
        text = benchruns.json.dumps(scores | {"format": version})
        (folder / "scores.json").write_text(text)
    monkeypatch.setattr(benchruns, "RESULTS", tmp_path / "results")

    assert list(benchruns.load_runs()) == ["20261118-120000"]
    assert "20261117-201846" in capsys.readouterr().out


def test_copied_values_are_boxed_on_the_page_by_whether_they_are_right(
    monkeypatch,
):
    """The figure shows where on the page a wrong value came from."""
    example = _ROOT / "gentrex-bench" / "examples" / "chart"
    truth = benchruns.json.loads(example.with_suffix(".json").read_text())
    data = truth["record"] | {"lab_accession_number": "Apricot Reference"}
    errors = benchruns.pd.DataFrame(
        [
            {
                "field": "lab_accession_number",
                "result": "wrong",
                "found": "Apricot Reference",
            }
        ]
    )
    files = {"pdf": example.with_suffix(".pdf"), "decisions": [], "data": data}
    drawn = []
    monkeypatch.setattr(
        benchruns.plt, "show", lambda: drawn.append(benchruns.plt.gcf())
    )

    benchruns.values_figure(files, errors, pages=1)

    colors = [
        matplotlib.colors.to_hex(patch.get_edgecolor())
        for patch in drawn[0].axes[0].patches
    ]
    assert "#d03b3b" in colors
    assert colors.count("#2a78d6") > 3


def test_example_report_prefers_dropped_page_with_variant(monkeypatch):
    """The walkthrough report should show both dropped pages and variants."""
    run = {
        "by_report": {
            "SYN-0001": {"variants": {"matched": 0}},
            "SYN-0002": {"variants": {"matched": 1}},
        }
    }
    decisions = [
        {"file": "SYN-0001.pdf", "keep": False},
        {"file": "SYN-0002.pdf", "keep": False},
    ]
    monkeypatch.setattr(benchruns, "records", lambda *_: decisions)

    assert benchruns.example_report(run) == "SYN-0002"


def test_presentation_notebook_runs_all_cells(tmp_path, monkeypatch):
    """Every code cell in presentation.ipynb runs cleanly on a scored run."""
    scores, errors = _run(tmp_path)
    folder = tmp_path / "results" / "gentrex-bench" / "20261118-120000"
    folder.mkdir(parents=True)
    (folder / "scores.json").write_text(benchruns.json.dumps(scores), encoding="utf-8")
    (folder / "errors.jsonl").write_text(
        "".join(benchruns.json.dumps(e) + "\n" for e in errors), encoding="utf-8"
    )
    monkeypatch.setattr(benchruns, "ROOT", tmp_path)
    monkeypatch.setattr(benchruns, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(benchruns, "EXPORT", None)
    monkeypatch.setattr(benchruns.plt, "show", lambda: None)

    notebook = benchruns.json.loads(
        (_ROOT / "presentation.ipynb").read_text(encoding="utf-8")
    )
    namespace = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), namespace)

    assert "chosen" in namespace and "files" in namespace
    assert (tmp_path / "figures" / "table-main.csv").is_file()


def test_schema_copies_and_real_ontology_benchmark_helpers(tmp_path, monkeypatch):
    """Project-wide presentation helpers read schema, example PDFs, and JSON results."""
    monkeypatch.setattr(benchruns, "EXPORT", tmp_path / "figures")
    monkeypatch.setattr(benchruns.plt, "show", lambda: None)

    schema = benchruns.schema_table()
    hpo = benchruns.hpo_benchmark_table()
    mondo = benchruns.mondo_benchmark_table()
    benchruns.copies_figure()

    assert sum(schema["Fields"].tolist()) >= 30
    assert len(hpo) == 5
    assert "Top-1, %" in hpo.columns
    assert len(mondo) == 2
    assert (tmp_path / "figures" / "figure-copies.pdf").is_file()
    assert (tmp_path / "figures" / "table-hpo-gsc.tex").is_file()
    assert (tmp_path / "figures" / "table-mondo-clinvar.tex").is_file()


def test_challenge_impact_and_export_summary_tables(tmp_path, monkeypatch):
    """Challenge contrasts and live export verification produce paper tables."""
    monkeypatch.setattr(benchruns, "EXPORT", tmp_path / "figures")
    scores, _ = _run(tmp_path)
    exports = benchruns.export_summary_table(scores)
    assert len(exports) == 4
    assert "All subject IDs masked (P-...)" in exports["Verification"].values

    fake = {
        "by_report": {
            "a": {"correct": False, "case": {"challenges": ["split_table"]}},
            "b": {"correct": False, "case": {"challenges": ["split_table"]}},
            "c": {"correct": True, "case": {"challenges": []}},
            "d": {"correct": True, "case": {"challenges": []}},
        }
    }
    impact = benchruns.challenge_impact_table(fake)
    assert impact.loc["Variant table split across pages", "Difference, points"] == (
        "-100.0"
    )
    assert (tmp_path / "figures" / "table-challenges.tex").is_file()
    assert (tmp_path / "figures" / "table-exports.tex").is_file()
