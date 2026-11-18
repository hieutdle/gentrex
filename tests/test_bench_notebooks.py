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
sys.path[:0] = [str(_ROOT / "evaluation_results"), str(_ROOT / "tests")]

import benchruns  # noqa: E402
import score  # noqa: E402
import test_bench_scorer as scorer_tests  # noqa: E402


def _run(tmp_path, change=None):
    """Returns the scores and the errors of a run of one report."""
    truth = scorer_tests._truth()
    pages = enumerate(scorer_tests._PAGES, 1)
    truth["pages"] = [{"page": number, "text": text} for number, text in pages]
    report = scorer_tests._report(truth)
    report["normalized"]["patient_phenotypes"] = [
        {
            "hpo_id": "HP:0002515",
            "models_agree": True,
            "candidates": [{"hpo_id": "HP:0002515"}],
        }
    ]
    if change:
        change(report)
    truth_dir, run_dir = scorer_tests._write_run(tmp_path, [truth], [report])
    select_dir = run_dir.parents[1] / "select" / run_dir.name
    decisions = [
        {"file": "SYN-0001.pdf", "page": page, "p_yes": {"has_result": p}, "keep": True}
        for page, p in ((1, 0.9), (2, 0.7))
    ]
    text = "".join(benchruns.json.dumps(d) + "\n" for d in decisions)
    (select_dir / "decisions.jsonl").write_text(text)
    record = yaml.safe_load((select_dir / "run.yaml").read_text())
    record["settings"]["keep_threshold"] = 0.5
    (select_dir / "run.yaml").write_text(yaml.safe_dump(record))
    return score.score(truth_dir, run_dir, "dev", [1, 1, 2])


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
        benchruns.generalization_table(runs),
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
        benchruns.repeats_table(runs | {"20261118-130000": scores}, "dev"),
        benchruns.wrong_reports_table(scores, found),
        benchruns.errors_table(found),
    ]
    benchruns.accuracy_figure(chosen)
    benchruns.stages_figure(chosen)
    benchruns.select_figure(scores)
    benchruns.fields_figure(scores)
    benchruns.errors_figure(scores)
    benchruns.confusion_figure(scores)
    benchruns.groups_figure(scores, ("kind", "scenario", "pages", "tag"))
    assert benchruns.findings(scores, chosen)

    assert all(len(table.columns) for table in tables[:19])
    main = benchruns.main_table(chosen).loc["native"]
    assert main["Report accuracy"].startswith("100.0")
    assert main["Every value right"].startswith("0.0")
    written = {path.name for path in (tmp_path / "paper").iterdir()}
    assert {"table-main.csv", "table-main.tex", "figure-accuracy.pdf"} <= written


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
    """The walkthrough shows where on the page a wrong value came from."""
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
