"""The tables and figures of the two notebooks in this folder.

A scored run is a folder under results/gentrex-bench/ with the scores.json
and errors.jsonl that gentrex-bench/run.py wrote. Every function here takes
scored runs and returns a table or draws a figure. With EXPORT set to a
folder, each table is also written there as CSV and LaTeX, and each figure
as PDF and PNG, for a paper.
"""

# The notebook group provides matplotlib and pandas.
# pyright: reportMissingImports=false

import html
import json
import math
import pathlib
import sys
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import ticker

ROOT = pathlib.Path(__file__).parents[1]
RESULTS = ROOT / "results"
# The folder that tables and figures are written to, or None to write none.
EXPORT: pathlib.Path | None = None
COMMANDS = ("transcribe", "select", "extract", "normalize")
COPIES = ("native", "scan", "fax", "mixed", "image")

sys.path.insert(0, str(ROOT / "gentrex-bench" / "scorer"))

import score  # noqa: E402

# The fields that decide whether a report counts as correct.
CLINICAL = score.compare.CLINICAL

MAIN = {
    "report_accuracy": "Report accuracy",
    "record_accuracy": "Every value right",
    "patient_match": "MRN and date of birth right",
    "value_f1": "Value F1",
    "variant_f1": "Variant F1",
}
FIELD_GROUPS = {
    "Patient and specimen": (
        "mrn",
        "submitter_patient_id",
        "date_of_birth",
        "sex",
        "specimen_type",
        "collection_date",
        "received_date",
        "lab_accession_number",
    ),
    "Test and report": (
        "lab_name",
        "test_name",
        "test_type",
        "test_started_date",
        "report_date",
        "clinical_indication",
        "genome_build",
        "karyotype",
    ),
    "Variants": (
        "variants.gene_symbol",
        "variants.transcript",
        "variants.hgvs_c",
        "variants.hgvs_p",
        "variants.dna_change_raw",
        "variants.chromosomal_position",
        "variants.copy_number",
        "variants.classification_raw",
        "variants.classification",
        "variants.zygosity_raw",
        "variants.zygosity",
        "variants.parental_origin_raw",
        "variants.parental_origin",
        "variants.associated_phenotype",
        "variants.mode_of_inheritance_raw",
        "variants.mode_of_inheritance",
        "variants.is_secondary_finding",
        "variants.variant_type_raw",
        "variants.page",
    ),
    "Clinical features": ("patient_phenotypes.present",),
    "Standard values": (
        "normalized.date_of_birth",
        "normalized.collection_date",
        "normalized.received_date",
        "normalized.test_started_date",
        "normalized.report_date",
        "normalized.specimen_type",
        "normalized.overall_result",
        "normalized.variants.hgnc_id",
        "normalized.variants.disease_id",
        "normalized.variants.clinvar_variation_id",
    ),
}
FIELD_LABELS = {
    "mrn": "MRN",
    "submitter_patient_id": "Submitter's patient ID",
    "date_of_birth": "Date of birth",
    "sex": "Sex",
    "specimen_type": "Specimen",
    "collection_date": "Collection date",
    "received_date": "Received date",
    "lab_accession_number": "Accession number",
    "lab_name": "Laboratory",
    "test_name": "Test name",
    "test_type": "Kind of test",
    "test_started_date": "Test start date",
    "report_date": "Report date",
    "clinical_indication": "Indication",
    "genome_build": "Genome build",
    "karyotype": "Karyotype",
    "variants.gene_symbol": "Gene",
    "variants.transcript": "Transcript",
    "variants.hgvs_c": "c. change",
    "variants.hgvs_p": "p. change",
    "variants.dna_change_raw": "Other DNA change",
    "variants.chromosomal_position": "Position",
    "variants.copy_number": "Copy number",
    "variants.classification_raw": "Classification, as printed",
    "variants.classification": "Classification",
    "variants.zygosity_raw": "Zygosity, as printed",
    "variants.zygosity": "Zygosity",
    "variants.parental_origin_raw": "Origin, as printed",
    "variants.parental_origin": "Origin",
    "variants.associated_phenotype": "Condition",
    "variants.mode_of_inheritance_raw": "Inheritance, as printed",
    "variants.mode_of_inheritance": "Inheritance",
    "variants.is_secondary_finding": "Secondary finding",
    "variants.variant_type_raw": "Kind of variant",
    "variants.page": "Page",
    "patient_phenotypes.present": "Feature present or absent",
    "normalized.date_of_birth": "Date of birth",
    "normalized.collection_date": "Collection date",
    "normalized.received_date": "Received date",
    "normalized.test_started_date": "Test start date",
    "normalized.report_date": "Report date",
    "normalized.specimen_type": "Specimen category",
    "normalized.overall_result": "Result category",
    "normalized.variants.hgnc_id": "HGNC ID of the gene",
    "normalized.variants.disease_id": "MONDO ID of the condition",
    "normalized.variants.clinvar_variation_id": "ClinVar ID of the variant",
    "variants": "Variants",
    "patient_phenotypes": "Clinical features",
    "normalized.patient_phenotypes": "HPO terms of the features",
}
VALUE_LABELS = {
    "sma": "SMA copy number",
    "mito": "Mitochondrial genome",
    "array": "Microarray",
    "single_gene": "Single gene",
    "targeted": "Targeted variant",
    "repeat": "Repeat expansion",
    "vus_only": "VUS only",
    "upd": "Uniparental disomy",
    "secondary_finding": "Secondary finding",
}
# Groups whose values have an order of their own.
_ORDERED = ("variants", "pages", "held_out")
GROUP_LABELS = {
    "kind": "Kind of test",
    "scenario": "Result",
    "variants": "Variants in the report",
    "pages": "Pages of the report",
    "held_out": "Templates",
    "lab": "Template",
    "tag": "Challenge",
}

_INK, _SECONDARY, _MUTED = "#0b0b0b", "#52514e", "#898781"
_GRID, _AXIS, _SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
_BLUE, _ORANGE, _AQUA = "#2a78d6", "#eb6834", "#1baf7a"
_STAGES = {"transcribe": _BLUE, "select": _ORANGE, "extract": _AQUA}
# The kinds of a value that isn't right, with their colors in the order of
# the categorical palette.
ERROR_KINDS = {
    "missed": ("Missed", _BLUE),
    "partial": ("Part of the value", _ORANGE),
    "other_value": ("Another value of the report", _AQUA),
    "not_in_pages": ("Not in the pages", "#eda100"),
    "other_text": ("Other text of the pages", "#e87ba4"),
    "category": ("Wrong category or number", "#008300"),
}
# The categories of the fields with a fixed list, in a reader's order.
CATEGORY_ORDER = (
    "pathogenic",
    "likely_pathogenic",
    "uncertain_significance",
    "likely_benign",
    "benign",
    "positive",
    "negative",
    "uncertain",
    "carrier",
    "inconclusive",
    "other",
    "none",
)
_WIDTH = 6.8

# A table cell shows its whole text, however long.
pd.set_option("display.max_colwidth", None)
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "figure.facecolor": _SURFACE,
        "axes.facecolor": _SURFACE,
        "axes.edgecolor": _AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "x",
        "axes.axisbelow": True,
        "grid.color": _GRID,
        "grid.linewidth": 0.8,
        "axes.titlelocation": "left",
        "axes.titlesize": 9,
        "axes.titleweight": "bold",
        "axes.labelcolor": _SECONDARY,
        "axes.labelsize": 8.5,
        "text.color": _INK,
        "xtick.color": _SECONDARY,
        "ytick.color": _INK,
        "xtick.labelsize": 8.5,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
    }
)


# Runs


def load_runs() -> dict[str, dict[str, Any]]:
    """Returns the scores.json of every scored run, by folder name, oldest first.

    Runs that an older scorer wrote lack numbers that the tables need, so
    they are left out and named.
    """
    found = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(RESULTS.glob("gentrex-bench/*/scores.json"))
    }
    old = [name for name, run in found.items() if run.get("format", 1) < score.FORMAT]
    if old:
        print(
            f"Left out what an older scorer wrote: {', '.join(old)}."
            " Score these runs again with gentrex-bench/scorer/score.py to see them."
        )
    return {name: run for name, run in found.items() if name not in old}


def copy_of(run: dict[str, Any]) -> str:
    """Returns the copy of the reports that a run read, such as native or scan."""
    return pathlib.Path(run["pdfs"]).name


def setup_of(run: dict[str, Any]) -> str:
    """Returns a run's setup, as "scan, no select, Qwen".

    That is the copy of the reports that it read, whether it skipped
    gentrex select, and the label that it was scored with.
    """
    return score.setup(run)


def _same_as(run: dict[str, Any]) -> str:
    """Returns what runs of one configuration share.

    That is the split, the setup, the settings of each command and the code
    that ran them. Runs that share it differ only by chance.
    """
    same = {
        "split": run["split"],
        "setup": setup_of(run),
        "settings": {command: r.get("settings") for command, r in run["runs"].items()},
        "code": {command: r.get("gentrex") for command, r in run["runs"].items()},
    }
    return json.dumps(same, sort_keys=True, default=str)


def newest(runs: dict[str, dict[str, Any]], split: str) -> dict[str, str]:
    """Returns the folder of the newest run of each setup on a split.

    The setups come in the order native, scan, fax, mixed, image, and each
    copy's run without gentrex select after its run with it.
    """
    found = {setup_of(run): name for name, run in runs.items() if run["split"] == split}

    def order(setup: str) -> tuple[int, str]:
        copy = setup.partition(",")[0]
        return (COPIES.index(copy) if copy in COPIES else len(COPIES), setup)

    return {setup: found[setup] for setup in sorted(found, key=order)}


def repeats(runs: dict[str, dict[str, Any]], split: str) -> dict[str, list[str]]:
    """Returns the runs of each setup on a split that repeat its newest run.

    They have the same settings and code as the newest run, oldest first.
    """
    found = {}
    for setup, latest in newest(runs, split).items():
        same = _same_as(runs[latest])
        found[setup] = [name for name, run in runs.items() if _same_as(run) == same]
    return found


def run_folder(run: dict[str, Any], command: str) -> pathlib.Path | None:
    """Returns the run folder of a command of a scored run.

    Returns:
        The folder, or None if the run skipped the command. Scores copied
        from another machine still name that machine's folders, so the
        folder of the same name under results/ stands in for a missing one.
    """
    record = run["runs"].get(command)
    if record is None:
        return None
    folder = pathlib.Path(record["path"])
    return folder if folder.exists() else RESULTS / command / folder.name


def records(run: dict[str, Any], command: str, name: str) -> list[dict[str, Any]]:
    """Returns the lines of a JSONL file in a command's run folder.

    Returns:
        The records, or none if the run skipped the command or the file is
        not on this machine.
    """
    folder = run_folder(run, command)
    if folder is None or not (folder / name).is_file():
        return []
    lines = (folder / name).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def errors(name: str, report: str | None = None) -> pd.DataFrame:
    """Returns every value of a scored run that isn't right, one row each.

    Args:
        name: The folder of the scored run.
        report: A report to keep the values of, or None for all reports.
    """
    path = RESULTS / "gentrex-bench" / name / "errors.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    found = [json.loads(line) for line in lines]
    if report is not None:
        found = [error for error in found if error["report"] == report]
    columns = [
        "report",
        "field",
        "result",
        "truth",
        "found",
        "command",
        "cause",
        "flagged",
    ]
    return pd.DataFrame(found, columns=columns)


def errors_table(run_errors: pd.DataFrame) -> pd.DataFrame:
    """Returns values that aren't right as a reader would list them."""
    rows = [
        {
            "Report": row["report"],
            "Field": label(row["field"])
            + (", standard value" if row["field"].startswith("normalized.") else ""),
            "Problem": row["result"],
            "In the report": row["truth"],
            "In the record": row["found"],
            "Lost by": row["command"],
            "In not_in_pages": row["flagged"],
        }
        for row in run_errors.to_dict("records")
    ]
    return pd.DataFrame(rows).fillna("")


# Numbers as text


def label(field: str) -> str:
    """Returns the name of a field or group value as a reader would write it."""
    if field in FIELD_LABELS or field in VALUE_LABELS:
        return FIELD_LABELS.get(field) or VALUE_LABELS[field]
    text = field.rpartition(".")[2].replace("_", " ")
    return text[:1].upper() + text[1:]


def pct(share: float | None, digits: int = 1) -> str:
    """Formats a share as a percentage without the sign, as 88.9."""
    return "" if share is None else f"{share * 100:.{digits}f}"


def interval(number: dict[str, Any]) -> str:
    """Formats a share with its 95% interval, as 88.9 (81.8–93.9)."""
    if number.get("value") is None:
        return ""
    return f"{pct(number['value'])} ({pct(number['low'])}–{pct(number['high'])})"


def wilson(correct: float, total: float) -> dict[str, float | None]:
    """Returns a share with its 95% Wilson interval, shaped like a main number.

    The scorer gives intervals only for the main numbers. This one serves
    the fields and the groups of reports, and it also holds for few reports.
    """
    if not total:
        return {"value": None, "low": None, "high": None}
    z = 1.96
    share = correct / total
    middle = share + z * z / (2 * total)
    spread = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total))
    scale = 1 + z * z / total
    low, high = (middle - spread) / scale, (middle + spread) / scale
    return {"value": share, "low": max(0.0, low), "high": min(1.0, high)}


def difference(first: dict[str, Any], second: dict[str, Any]) -> str:
    """Formats the second run's report accuracy minus the first's, in points.

    The two runs are compared on the reports that both scored, with a 95%
    interval. An interval that includes 0 means the runs can't be told apart.
    """
    gain = score.difference(first, second)
    if not gain["reports"]:
        return ""
    return (
        f"{gain['value'] * 100:+.1f} ({gain['low'] * 100:+.1f} to"
        f" {gain['high'] * 100:+.1f})"
    )


def _per_100(count: float, total: float) -> str:
    return f"{count / total * 100:.1f}" if total else ""


def _save_table(table: pd.DataFrame, name: str) -> pd.DataFrame:
    """Writes a table as CSV and LaTeX if EXPORT names a folder, and returns it."""
    if EXPORT is not None and not table.empty:
        EXPORT.mkdir(parents=True, exist_ok=True)
        table.to_csv(EXPORT / f"{name}.csv")
        text = table.to_latex(escape=True).replace("–", "--")
        (EXPORT / f"{name}.tex").write_text(text, encoding="utf-8")
    return table


def _save_figure(figure, name: str) -> None:
    """Writes a figure as PDF and PNG if EXPORT names a folder, and shows it."""
    if EXPORT is not None:
        EXPORT.mkdir(parents=True, exist_ok=True)
        for suffix in ("pdf", "png"):
            figure.savefig(EXPORT / f"{name}.{suffix}")
    plt.show()


# Tables that compare runs


def runs_table(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns every scored run with its setup and its main number."""
    return pd.DataFrame(
        {
            name: {
                "Setup": setup_of(run),
                "Split": run["split"],
                "Reports": run["reports"],
                "Report accuracy, % (95% CI)": interval(run["main"]["report_accuracy"]),
            }
            for name, run in runs.items()
        }
    ).T


def setup_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns the software, hardware, models and reference data of a run."""
    settings = {command: record["settings"] for command, record in run["runs"].items()}
    normalize = settings["normalize"]
    gentrex = run["runs"]["extract"].get("gentrex") or {}
    # A run that score.py scored on its own names no servers and no GPUs.
    versions = run["performance"].get("server_versions") or {}
    servers = set(filter(None, versions.values()))
    benchmark = run["benchmark"] or {}
    commit = (gentrex.get("commit") or "")[:7]
    rows = {
        "Gentrex": f"{gentrex.get('version')}, commit {commit}"
        + (" with local changes" if gentrex.get("modified") else ""),
        "Model server": ", ".join(f"vLLM {version}" for version in sorted(servers)),
        "GPUs": ", ".join(run["performance"].get("gpu_names") or []),
        "OCR model": (settings["transcribe"].get("ocr") or {}).get("model"),
        "Page selection model": settings.get("select", {}).get("model", "not run"),
        "Extraction model": settings["extract"].get("model"),
        "Embedding models": ", ".join(
            model["name"] for model in (normalize.get("hpo") or {}).get("models", [])
        ),
        "HPO release": normalize.get("hpo_version") or "",
        "MONDO release": normalize.get("mondo_version") or "",
        "HGNC file": pathlib.Path(normalize.get("hgnc_path") or "").name,
        "ClinVar file": pathlib.Path(normalize.get("clinvar_path") or "").name,
        "Benchmark": f"{benchmark.get('version')}, {benchmark.get('generator')}",
    }
    table = pd.Series(rows, name="Value", dtype=object).to_frame()
    return _save_table(table, "table-setup")


def data_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns what the reports of a run's split are made of."""
    data, groups = run["data"], run["groups"]
    held_out = groups.get("held_out", {}).get("held out", {}).get("reports", 0)
    rows = {
        "Reports": data["reports"],
        "Pages": data["pages"],
        "Pages per report, median (most)": (
            f"{data['pages_median']:g} ({data['pages_most']})" if data["pages"] else ""
        ),
        "Words per report, median": (
            None if data.get("words_median") is None else round(data["words_median"])
        ),
        "Variants": data["variants"],
        "Genes": data.get("genes"),
        "Conditions": data.get("conditions"),
        "Clinical features": data["features"],
        "Stated values": run["funnel"]["stated"],
        "Templates": len(groups.get("lab", {})),
        "Reports of held-out templates": held_out,
        "Challenges": len(groups.get("tag", {})),
        "Reports that the writing model wrote more than once": data.get("rewritten"),
    }
    rows = {name: value for name, value in rows.items() if value is not None}
    table = pd.Series(rows, name=f"{run['split']} split", dtype=object).to_frame()
    return _save_table(table, "table-data")


def main_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns the main numbers of each setup, in percent with 95% intervals."""
    table = pd.DataFrame(
        {
            setup: {"Reports": run["reports"]}
            | {title: interval(run["main"][name]) for name, title in MAIN.items()}
            for setup, run in chosen.items()
        }
    ).T
    return _save_table(table, "table-main")


def generalization_table(runs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns the report accuracy of each setup on dev and on test.

    The test reports are also split into the templates that dev has too and
    the held-out ones, which nothing was tuned on.
    """
    by_split = {split: newest(runs, split) for split in ("dev", "test")}
    parts = {
        "seen in dev": "Test, templates that dev has",
        "held out": "Test, held-out templates",
    }
    rows = {}
    for setup in dict.fromkeys([*by_split["dev"], *by_split["test"]]):
        row = {}
        if setup in by_split["dev"]:
            dev = runs[by_split["dev"][setup]]
            row["Dev"] = interval(dev["main"]["report_accuracy"])
        if setup in by_split["test"]:
            test = runs[by_split["test"][setup]]
            row["Test"] = interval(test["main"]["report_accuracy"])
            for value, title in parts.items():
                n = test["groups"].get("held_out", {}).get(value)
                if n:
                    right = round(n["report_accuracy"] * n["reports"])
                    row[title] = (
                        f"{interval(wilson(right, n['reports']))}, n={n['reports']}"
                    )
        rows[setup] = row
    table = pd.DataFrame(rows, dtype=object).T.fillna("")
    return _save_table(table, "table-generalization")


def repeats_table(runs: dict[str, dict[str, Any]], split: str) -> pd.DataFrame:
    """Returns the mean and the range of the main numbers over repeated runs."""
    rows = {}
    for setup, names in repeats(runs, split).items():
        if len(names) < 2:
            continue
        same = [runs[name] for name in names]
        shared = set.intersection(*(set(run["by_report"]) for run in same))
        agree = sum(
            len({run["by_report"][report]["correct"] for run in same}) == 1
            for report in shared
        )
        row: dict[str, Any] = {"Runs": len(names)}
        for name in ("report_accuracy", "value_f1", "variant_f1"):
            values = [run["main"][name]["value"] for run in same]
            values = [value for value in values if value is not None]
            if values:
                row[f"{MAIN[name]}, mean (range)"] = (
                    f"{pct(sum(values) / len(values))}"
                    f" ({pct(min(values))}–{pct(max(values))})"
                )
        row["Reports with the same outcome in all runs, %"] = pct(agree / len(shared))
        rows[setup] = row
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-repeats")


def transcribe_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns how well gentrex transcribe read each copy of the reports.

    The words of the pages that went to OCR are compared with the words of
    the same pages in the truth files, whatever their order, because OCR
    reads the columns of a page in another order than the PDF's text layer.
    The difference to native is in report accuracy, on the same reports.
    """
    native = chosen.get("native")
    rows = {}
    for setup, run in chosen.items():
        if "select" not in run["runs"] or run.get("label"):
            continue
        pages, funnel = run["pages"], run["funnel"]
        recall, precision = pages["ocr_word_recall"], pages["ocr_word_precision"]
        f1 = (
            2 * recall * precision / (recall + precision)
            if recall and precision
            else None
        )
        rows[setup] = {
            "Pages sent to OCR, %": pct(pages["ocr"] / pages["total"], 0),
            "Pages without text": pages["empty"],
            "OCR word recall, %": pct(recall),
            "OCR word precision, %": pct(precision),
            "OCR word F1, %": pct(f1),
            "Values lost in transcribe, per 100": _per_100(
                funnel["lost"]["transcribe"], funnel["stated"]
            ),
            "Report accuracy, %": pct(run["main"]["report_accuracy"]["value"]),
            "Difference to native, points (95% CI)": (
                difference(native, run) if native and run is not native else ""
            ),
        }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-transcribe")


def select_pages_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns how well gentrex select chose the pages in each setup.

    A needed page is the only page of its report that prints a stated
    value. A value is reachable if a kept page prints it.
    """
    rows = {}
    for setup, run in chosen.items():
        select = run.get("select")
        if not select:
            continue
        needed = select["needed_kept"] + select["needed_dropped"]
        other = select["other_kept"] + select["other_dropped"]
        rows[setup] = {
            "Pages": select["pages"],
            "Needed pages": needed,
            "Needed pages kept, %": pct(select["needed_kept"] / max(needed, 1)),
            "Other pages": other,
            "Other pages dropped, %": pct(select["other_dropped"] / max(other, 1)),
            "Pages kept, %": pct(
                (select["needed_kept"] + select["other_kept"]) / max(select["pages"], 1)
            ),
            "Stated values on a kept page, %": pct(
                select["values_reachable"] / max(select["values"], 1)
            ),
        }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-select-pages")


def questions_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns the pages that only one question of gentrex select kept.

    Without that question, those pages would be dropped, so this shows what
    each question is worth.
    """
    select = run.get("select")
    if not select:
        return pd.DataFrame()
    rows = {
        name: {"Pages that only it kept": n["pages"], "of which needed": n["needed"]}
        for name, n in select["only_by"].items()
    }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-select-questions")


def extract_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns how well gentrex extract copied the values that reached it.

    Values that gentrex transcribe or gentrex select lost don't count, so
    the numbers measure gentrex extract alone. The value recall over all
    stated values is next to it.
    """
    rows = {}
    for setup, run in chosen.items():
        funnel = run["funnel"]
        recall, precision = funnel["extract_recall"], funnel["extract_precision"]
        reached = (
            funnel["stated"] - funnel["lost"]["transcribe"] - funnel["lost"]["select"]
        )
        rows[setup] = {
            "Values that reached it": reached,
            "Recall, %": pct(recall),
            "Precision, %": pct(precision),
            "F1, %": pct(
                2 * recall * precision / (recall + precision)
                if recall and precision
                else None
            ),
            "Value recall over all stated values, %": pct(
                run["main"]["value_recall"]["value"]
            ),
        }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-extract")


def select_figure(run: dict[str, Any]) -> None:
    """Draws the share of stated values on a kept page against the pages kept.

    Each point is a keep_threshold of gentrex select, from the probabilities
    of "yes" that the run wrote. The run's own threshold is marked.
    """
    select = run.get("select")
    if not select:
        print("The run skipped gentrex select.")
        return
    sweep = select["sweep"]
    xs = [row["pages_kept"] for row in sweep]
    ys = [row["values_reachable"] for row in sweep]
    # Thresholds that keep the same pages share a point and a label.
    points: dict[tuple[float, float], list[float]] = {}
    for row in sweep:
        place = (row["pages_kept"], row["values_reachable"])
        points.setdefault(place, []).append(row["threshold"])
    figure, ax = plt.subplots(figsize=(_WIDTH * 0.62, 2.9))
    ax.grid(axis="y", visible=True)
    ax.plot(xs, ys, color=_BLUE, linewidth=2, solid_capstyle="round", zorder=2)
    for (x, y), thresholds in points.items():
        own = select["threshold"] in thresholds
        _dot(ax, x, y, _ORANGE if own else _BLUE)
        low, high = min(thresholds), max(thresholds)
        text = f"{low:g}" if low == high else f"{low:g} to {high:g}"
        left = x < 0.5
        ax.annotate(
            text + (", this run" if own else ""),
            (x, y),
            xytext=(6 if left else -6, 8 if left else -12),
            textcoords="offset points",
            ha="left" if left else "right",
            fontsize=8,
            color=_INK if own else _SECONDARY,
        )
    ax.set_xlim(0, 1.02)
    ax.set_ylim(_floor(ys), 1.005)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(1, decimals=0))
    ax.set_xlabel("Pages kept")
    ax.set_ylabel("Stated values on a kept page")
    figure.tight_layout()
    _save_figure(figure, "figure-select")


def select_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns each copy's run with gentrex select next to its run without.

    A needed page is the only page of its report that prints one of the
    stated values. The other pages are the ones that gentrex select may drop.
    """
    columns = {}
    for copy in COPIES:
        pair = (copy, f"{copy}, no select")
        if not all(setup in chosen for setup in pair):
            continue
        for setup in pair:
            run = chosen[setup]
            commands, pages = run["performance"]["commands"], run["pages"]
            files = run["performance"]["files"] or 1
            seconds = sum(commands[c]["seconds"] for c in commands if c != "normalize")
            read = pages["total"] if pages["kept"] is None else pages["kept"]
            columns[setup] = {
                "Report accuracy, % (95% CI)": interval(run["main"]["report_accuracy"]),
                "Difference, points (95% CI)": (
                    "" if setup == copy else difference(chosen[copy], run)
                ),
                "Value F1, % (95% CI)": interval(run["main"]["value_f1"]),
                "Pages that gentrex extract read, %": pct(read / pages["total"], 0),
                "Needed pages kept, %": (
                    ""
                    if pages["needed_kept"] is None
                    else pct(pages["needed_kept"] / max(pages["needed"], 1), 1)
                ),
                "Other pages dropped, %": (
                    ""
                    if pages["other_dropped"] is None
                    else pct(pages["other_dropped"] / max(pages["other"], 1), 1)
                ),
                "Values lost in select, per 100": _per_100(
                    run["funnel"]["lost"]["select"], run["funnel"]["stated"]
                ),
                "Prompt tokens of extract per report": round(
                    commands["extract"]["prompt_tokens"] / files
                ),
                "Seconds of the three models per report": round(seconds / files, 1),
                "GPU-hours per 1,000 reports": run["performance"][
                    "gpu_hours_per_1000_files"
                ],
            }
    return _save_table(pd.DataFrame(columns, dtype=object), "table-select")


def stages_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns what became of the stated values in each setup, per 100 of them."""
    rows = {}
    for setup, run in chosen.items():
        funnel = run["funnel"]
        stated = funnel["stated"]
        rows[setup] = {
            "Stated values": stated,
            "Right": _per_100(funnel["right"], stated),
            **{
                f"Lost in {command}": _per_100(count, stated)
                for command, count in funnel["lost"].items()
            },
            "Not stated but written": _per_100(funnel["extra"], stated),
        }
    return _save_table(pd.DataFrame(rows).T, "table-stages")


def efficiency_table(chosen: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Returns the time, the tokens and the GPU-hours of each setup."""
    rows = {}
    for setup, run in chosen.items():
        performance = run["performance"]
        commands, files = performance["commands"], performance["files"] or 1
        latency = performance.get("extract_seconds_per_report") or {}
        loading = sum(c.get("server_start_seconds") or 0 for c in commands.values())
        prompt = sum(c.get("prompt_tokens") or 0 for c in commands.values())
        written = sum(c.get("completion_tokens") or 0 for c in commands.values())
        rows[setup] = {
            "Report accuracy, %": pct(run["main"]["report_accuracy"]["value"]),
            "GPU-hours per 1,000 reports": performance["gpu_hours_per_1000_files"],
            "Seconds per report": round(
                sum(c["seconds"] for c in commands.values()) / files, 1
            ),
            **{
                f"of which {name}": round(c["seconds"] / files, 1)
                for name, c in commands.items()
            },
            "Extract request, median s (90th percentile)": (
                f"{latency['median']:g} ({latency['p90']:g})" if latency else ""
            ),
            "Tokens read per report": round(prompt / files),
            "Tokens written per report": round(written / files),
            "Model loading, s per run": round(loading),
            "Failed files": sum(c.get("failed_files") or 0 for c in commands.values()),
        }
    table = pd.DataFrame(rows, dtype=object).fillna("")
    return _save_table(table, "table-efficiency")


# Tables of one run


def entities_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns the missed and extra variants and clinical features of a run."""
    rows = {}
    for name, entity in run["entities"].items():
        extra = dict(entity["extra_by"])
        rows[label(name)] = {
            "Stated": entity["matched"] + entity["missed"],
            "Found": entity["matched"],
            "Missed": entity["missed"],
            "Extra": entity["extra"],
            "of which made up": extra.get("hallucination", ""),
            "of which a distractor": extra.get("distractor", ""),
            "Precision, %": pct(entity["precision"]),
            "Recall, %": pct(entity["recall"]),
            "F1, %": pct(entity["f1"]),
        }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-entities")


def _grouped_fields(run: dict[str, Any]) -> dict[str, list[str]]:
    """Returns the scored fields of a run by group, with unknown ones last."""
    known = {field for fields in FIELD_GROUPS.values() for field in fields}
    groups = {
        group: [field for field in fields if field in run["fields"]]
        for group, fields in FIELD_GROUPS.items()
    }
    groups["Other"] = [field for field in run["fields"] if field not in known]
    return {group: fields for group, fields in groups.items() if fields}


def fields_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns precision, recall and F1 of every field, by group of fields."""
    rows = {}
    for group, fields in _grouped_fields(run).items():
        for field in fields:
            numbers = run["fields"][field]
            same = numbers["strict"] / numbers["values"] if numbers["values"] else None
            rows[group, label(field)] = {
                "Stated": numbers["stated"],
                "Precision, %": pct(numbers["precision"]),
                "Recall, %": pct(numbers["recall"]),
                "F1, %": pct(numbers["f1"]),
                "Recall given input, %": pct(numbers.get("recall_given_input")),
                "Missed": numbers["missed"],
                "Wrong": numbers["wrong"],
                "Extra": numbers["extra"],
                "Same text, %": pct(same),
            }
    table = pd.DataFrame(rows, dtype=object).T
    table.index.names = ["Group", "Field"]
    return _save_table(table, "table-fields")


def normalize_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns the accuracy of each standard value, end to end and on its own.

    `Given a right source` leaves out the values whose source gentrex
    extract already got wrong, so it measures gentrex normalize alone. The
    HGNC IDs are also split by whether the report prints the gene's
    approved symbol or an older one.
    """
    rows = {}
    found = run.get("normalize") or {}
    order = {
        field: place for place, field in enumerate(FIELD_GROUPS["Standard values"])
    }
    names = sorted(
        found, key=lambda name: (order.get(name.partition(" (")[0], 99), name)
    )
    for name in names:
        n = found[name]
        field, _, part = name.partition(" (")
        title = label(field) + (f", {part.rstrip(')')}" if part else "")
        rows[title] = {
            "Values": n["values"],
            "End to end, % (95% CI)": interval(wilson(n["right"], n["values"])),
            "Source already wrong": n["source_wrong"],
            "Given a right source, % (95% CI)": interval(
                wilson(n["right"], n["values"] - n["source_wrong"])
            ),
        }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-normalize")


def hpo_table(run: dict[str, Any]) -> pd.DataFrame | None:
    """Returns how well gentrex normalize found the HPO term of each feature.

    Only features whose text gentrex extract found count. `Top 1` is the
    term that the record gets. `First candidate` would be the term without
    the similarity threshold, below which a feature gets no term. `Top 5`
    counts the features whose true term is one of the five candidates.
    """
    hpo = run.get("hpo")
    if not hpo:
        print("The run left the clinical features without HPO terms.")
        return None
    rows = {
        name[:1].upper() + name[1:] + (" features" if name == "all" else ""): {
            "Features": n["features"],
            "Top 1, %": pct(n["top_1"]),
            "First candidate, %": pct(n["first_candidate"]),
            "Top 5, %": pct(n["top_5"]),
            "No term, %": pct(n["no_term"]),
        }
        for name, n in hpo.items()
    }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-hpo")


def wrong_reports_table(run: dict[str, Any], run_errors: pd.DataFrame) -> pd.DataFrame:
    """Returns the clinical errors of the reports that don't count as correct."""
    wrong = {name for name, report in run["by_report"].items() if not report["correct"]}
    print(f"{len(wrong)} of {run['reports']} reports count as wrong")
    rows = []
    for row in run_errors.to_dict("records"):
        if row["report"] not in wrong or row["field"] not in CLINICAL:
            continue
        case = run["by_report"][row["report"]]["case"]
        rows.append(
            {
                "Report": row["report"],
                "Template": case["lab"],
                "Kind of test": label(case["kind"] or ""),
                "Field": label(row["field"]),
                "Problem": row["result"],
                "In the report": row["truth"],
                "In the record": row["found"],
                "Lost by": row["command"],
            }
        )
    table = pd.DataFrame(rows).fillna("")
    return table.set_index("Report") if rows else table


CHECK_LABELS = {
    "not_in_pages": "Copied value not in the pages",
    "hgvs_invalid": "HGVS that isn't valid",
    "result_conflict": "Result and classifications disagree",
    "hpo_models_disagree": "Embedding models disagree on the HPO term",
    "any": "Any check",
}


def checks_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns how well each check of Gentrex tells the values that are wrong."""
    rows = {
        CHECK_LABELS.get(name, name): {
            "Values looked at": c["values"],
            "Flagged": c["flagged"],
            "Wrong": c["not_right"],
            "Flagged and wrong": c["flagged_and_not_right"],
            "Precision, %": pct(c["precision"]),
            "Recall, %": pct(c["recall"]),
        }
        for name, c in (run.get("checks") or {}).items()
    }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-checks")


def review_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns the reports that a person would look at because of each check.

    A wrong report is one that doesn't count as correct.
    """
    review = run["review"]
    every = review["checks"]["any"]
    print(
        f"A person who looks at every report with a flag looks at"
        f" {every['flagged']} of {review['reports']} reports, and finds"
        f" {every['flagged_and_wrong']} of the {review['wrong']} wrong ones."
    )
    rows = {
        CHECK_LABELS.get(name, name): {
            "Reports flagged": c["flagged"],
            "of which wrong": c["flagged_and_wrong"],
            "Precision, %": pct(c["precision"]),
            "Recall, %": pct(c["recall"]),
        }
        for name, c in review["checks"].items()
    }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-review")


VARIANT_KIND_LABELS = {
    "sequence": "Sequence variant",
    "exon_deletion_duplication": "Exon deletion or duplication",
    "mitochondrial": "Mitochondrial variant",
    "copy_number": "Copy-number change",
    "gene_copy_number": "Gene copy number",
    "repeat": "Repeat expansion",
    "uniparental_disomy": "Uniparental disomy",
}


def variant_kinds_table(run: dict[str, Any]) -> pd.DataFrame:
    """Returns how well each kind of variant was found and described.

    The accuracy of the classification, the zygosity and the copy number
    counts the found variants of the kind.
    """
    rows = {
        VARIANT_KIND_LABELS.get(kind, kind): {
            "Stated": k["stated"],
            "Found": k["found"],
            "Extra": k["extra"],
            "Recall, %": pct(k["recall"]),
            "Precision, %": pct(k["precision"]),
            "Classification right, %": pct(k["classification"]),
            "Zygosity right, %": pct(k["zygosity"]),
            "Copy number right, %": pct(k["copy_number"]),
        }
        for kind, k in (run.get("variant_kinds") or {}).items()
    }
    return _save_table(pd.DataFrame(rows, dtype=object).T, "table-variant-kinds")


# Figures


def findings(run: dict[str, Any], chosen: dict[str, dict[str, Any]]) -> list[str]:
    """Returns what the numbers of a run say, in a few sentences.

    Args:
        run: The run that the sentences are about.
        chosen: The newest run of each setup, to compare the copies.
    """
    funnel = run["funnel"]
    lost = funnel["lost"]
    stated = max(funnel["stated"], 1)
    sentences = [
        f"Of 100 stated values, {funnel['right'] / stated * 100:.1f} are right in"
        f" the records. gentrex extract loses {lost['extract'] / stated * 100:.1f},"
        f" gentrex transcribe {lost['transcribe'] / stated * 100:.1f} and"
        f" gentrex select {lost['select'] / stated * 100:.1f}."
    ]
    native = chosen.get("native")
    copies = {
        setup: score.difference(native, other)
        for setup, other in chosen.items()
        if native
        and other is not native
        and "select" in other["runs"]
        and not other.get("label")
    }
    if copies:
        setup, gain = min(copies.items(), key=lambda item: item[1]["value"])
        sentences.append(
            f"The weakest copy is {setup}, at {gain['value'] * 100:+.1f} points of"
            f" report accuracy against the native PDFs"
            f" ({gain['low'] * 100:+.1f} to {gain['high'] * 100:+.1f})."
        )
    weakest = sorted(
        (
            (numbers["f1"], field)
            for field, numbers in run["fields"].items()
            if numbers["f1"] is not None
            and numbers["stated"] >= 10
            and not field.startswith("normalized.")
        ),
    )[:3]
    if weakest:
        names = [f"{label(field)} ({pct(f1)}%)" for f1, field in weakest]
        sentences.append(
            f"The weakest fields by F1 are {', '.join(names[:-1])} and {names[-1]}."
            if len(names) > 1
            else f"The weakest field by F1 is {names[0]}."
        )
    review = run.get("review")
    if review:
        every = review["checks"]["any"]
        sentences.append(
            f"The checks of Gentrex flag {every['flagged']} of {review['reports']}"
            f" reports, among them {every['flagged_and_wrong']} of the"
            f" {review['wrong']} that count as wrong."
        )
    return sentences


def headline(
    run: dict[str, Any], chosen: dict[str, dict[str, Any]] | None = None
) -> Any:
    """Returns the main numbers of a run as large figures, with what they say.

    Args:
        run: The run to show.
        chosen: The newest run of each setup, to compare the copies.
    """
    from IPython.display import HTML

    tiles = "".join(
        '<div style="flex:1;min-width:8.5em;padding:0.6em 1em;'
        f'border-left:3px solid {_BLUE}">'
        f'<div style="color:{_SECONDARY};font-size:0.85em">{html.escape(title)}</div>'
        f'<div style="font-size:2em;font-weight:600;color:{_INK}">'
        f"{pct(run['main'][name]['value'])}%</div>"
        f'<div style="color:{_MUTED};font-size:0.85em">'
        f"{pct(run['main'][name]['low'])} to {pct(run['main'][name]['high'])}</div>"
        "</div>"
        for name, title in MAIN.items()
    )
    caption = (
        f"{run['reports']} reports of the {run['split']} split,"
        f" {html.escape(setup_of(run))}. The small print is the 95% interval."
    )
    said = "".join(
        f"<li>{html.escape(sentence)}</li>" for sentence in findings(run, chosen or {})
    )
    return HTML(
        '<div style="display:flex;flex-wrap:wrap;gap:0.5em;font-family:sans-serif">'
        f'{tiles}</div><div style="color:{_MUTED};font-size:0.85em;'
        f'margin-top:0.4em">{caption}</div>'
        f'<ul style="margin-top:0.8em">{said}</ul>'
    )


def _dot(ax, x: float, y: float, color: str = _BLUE) -> None:
    ax.plot(
        x,
        y,
        "o",
        color=color,
        markersize=6.5,
        markeredgecolor=_SURFACE,
        markeredgewidth=1.5,
        clip_on=False,
        zorder=3,
    )


def _floor(shares: list[float]) -> float:
    """Returns where a share axis can start, a tenth below the lowest share."""
    return max(0.0, math.floor((min(shares, default=0) - 0.02) * 10) / 10)


def _percent_axis(ax) -> None:
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1, decimals=0))


def accuracy_figure(chosen: dict[str, dict[str, Any]]) -> None:
    """Draws the report accuracy of each setup, and its difference to native."""
    if not chosen:
        print("No runs to show.")
        return
    native = chosen.get("native")
    gains = {
        setup: score.difference(native, run)
        for setup, run in chosen.items()
        if native and run is not native
    }
    figure, axes = plt.subplots(
        1,
        2 if gains else 1,
        figsize=(_WIDTH, 0.36 * len(chosen) + 1.0),
        sharey=True,
        squeeze=False,
    )
    left = axes[0][0]
    main = {setup: run["main"]["report_accuracy"] for setup, run in chosen.items()}
    for position, number in enumerate(main.values()):
        left.hlines(position, number["low"], number["high"], color=_BLUE, linewidth=1.5)
        _dot(left, number["value"], position)
        left.annotate(
            pct(number["value"]),
            (number["value"], position),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=_SECONDARY,
        )
    left.set_yticks(range(len(main)), list(main))
    left.set_ylim(len(main) - 0.5, -0.7)
    left.set_xlim(_floor([number["low"] for number in main.values()]), 1.0)
    _percent_axis(left)
    left.set_title("Report accuracy")
    if gains:
        right = axes[0][1]
        right.axvline(0, color=_AXIS, linewidth=1)
        for position, setup in enumerate(chosen):
            gain = gains.get(setup)
            if gain is None or gain["value"] is None:
                continue
            right.hlines(
                position, gain["low"], gain["high"], color=_BLUE, linewidth=1.5
            )
            _dot(right, gain["value"], position)
        right.xaxis.set_major_formatter(
            ticker.FuncFormatter(lambda share, _: f"{share * 100:+.0f}")
        )
        right.set_title("Difference to native, in points")
    figure.tight_layout()
    _save_figure(figure, "figure-accuracy")


def stages_figure(chosen: dict[str, dict[str, Any]]) -> None:
    """Draws where the stated values of each setup were lost, per 100 values."""
    if not chosen:
        print("No runs to show.")
        return
    figure, ax = plt.subplots(figsize=(_WIDTH, 0.36 * len(chosen) + 1.1))
    totals = []
    for position, run in enumerate(chosen.values()):
        funnel, start = run["funnel"], 0.0
        for command, color in _STAGES.items():
            share = funnel["lost"][command] / max(funnel["stated"], 1) * 100
            ax.barh(
                position,
                share,
                left=start,
                height=0.5,
                color=color,
                edgecolor=_SURFACE,
                linewidth=1.5,
                label=f"gentrex {command}" if position == 0 else None,
            )
            start += share
        totals.append(start)
        ax.text(start, position, f"  {start:.1f}", va="center", fontsize=8)
    ax.set_yticks(range(len(chosen)), list(chosen))
    ax.set_ylim(len(chosen) - 0.5, -0.5)
    ax.set_xlim(0, max(max(totals), 1) * 1.15)
    ax.set_xlabel("Stated values lost, per 100")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=3, handlelength=1.2)
    figure.tight_layout()
    _save_figure(figure, "figure-stages")


def _sections(ax, sections: dict[str, dict[str, Any]], draw) -> None:
    """Draws rows in titled sections on one axis, top to bottom.

    Args:
        ax: The axis.
        sections: The rows of each section by label, under the section's title.
        draw: Draws one row, given its position and its value.
    """
    ticks, names, position = [], [], 0.0
    for title, rows in sections.items():
        ax.text(
            -0.012,
            position,
            title,
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="center",
            fontweight="bold",
            fontsize=8.5,
        )
        position += 1
        for name, value in rows.items():
            draw(position, value)
            ticks.append(position)
            names.append(name)
            position += 1
        position += 0.4
    ax.set_yticks(ticks, names)
    ax.set_ylim(position - 0.9, -0.6)


def fields_figure(run: dict[str, Any], other: dict[str, Any] | None = None) -> None:
    """Draws the F1 of every field of a run, by group of fields.

    Args:
        run: The run to show.
        other: A second run to show next to it, such as the scan copy.
    """
    sections = {
        group: {
            f"{label(field)}  ({run['fields'][field]['stated']})": field
            for field in fields
            if run["fields"][field]["f1"] is not None
        }
        for group, fields in _grouped_fields(run).items()
    }
    sections = {group: rows for group, rows in sections.items() if rows}
    if not sections:
        print("No fields to show.")
        return
    count = sum(len(rows) + 1.4 for rows in sections.values())
    figure, ax = plt.subplots(figsize=(_WIDTH, 0.2 * count + 0.8))
    shares = []

    def draw(position: float, field: str) -> None:
        first = run["fields"][field]["f1"]
        if other is not None:
            second = (other["fields"].get(field) or {}).get("f1")
            if second is not None:
                ax.hlines(position, first, second, color=_AXIS, linewidth=1.2)
                _dot(ax, second, position, _ORANGE)
                shares.append(second)
        _dot(ax, first, position)
        shares.append(first)

    _sections(ax, sections, draw)
    ax.set_xlim(_floor(shares), 1.0)
    _percent_axis(ax)
    ax.set_xlabel("F1 (number of stated values in brackets)")
    if other is not None:
        for name, color in ((setup_of(run), _BLUE), (setup_of(other), _ORANGE)):
            ax.plot([], [], "o", color=color, markersize=6.5, label=name)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2)
    figure.tight_layout()
    _save_figure(figure, "figure-fields")
    scores = [
        numbers["f1"]
        for field, numbers in run["fields"].items()
        if numbers["f1"] is not None and not field.startswith("normalized.")
    ]
    if scores:
        print(
            f"F1 averaged over the {len(scores)} extracted fields is"
            f" {pct(sum(scores) / len(scores))}%, and the value F1 over all"
            f" stated values is {pct(run['main']['value_f1']['value'])}%."
        )


def errors_figure(run: dict[str, Any], count: int = 12) -> None:
    """Draws the kinds of the values that aren't right, for the weakest fields.

    The fields are those of gentrex extract with the most values that aren't
    right, most first.
    """
    fields = sorted(
        (
            (sum(numbers.get("kinds", {}).values()), field)
            for field, numbers in run["fields"].items()
            if not field.startswith("normalized.") and numbers.get("kinds")
        ),
        reverse=True,
    )[:count]
    if not fields:
        print("Every extracted value is right.")
        return
    figure, ax = plt.subplots(figsize=(_WIDTH, 0.3 * len(fields) + 1.3))
    names = [label(field) for _, field in fields]
    for position, (total, field) in enumerate(fields):
        start = 0
        for kind, (title, color) in ERROR_KINDS.items():
            amount = run["fields"][field]["kinds"].get(kind, 0)
            ax.barh(
                position,
                amount,
                left=start,
                height=0.55,
                color=color,
                edgecolor=_SURFACE,
                linewidth=1.5,
                label=title if position == 0 else None,
            )
            start += amount
        ax.text(start, position, f"  {total}", va="center", fontsize=8)
    ax.set_yticks(range(len(names)), names)
    ax.set_ylim(len(names) - 0.5, -0.5)
    ax.set_xlim(0, fields[0][0] * 1.12)
    ax.set_xlabel("Values that aren't right")
    ax.legend(
        loc="lower left", bbox_to_anchor=(0, 1.0), ncols=3, handlelength=1.2, fontsize=8
    )
    figure.tight_layout()
    _save_figure(figure, "figure-error-kinds")


def _order(categories: set[str]) -> list[str]:
    known = [c for c in CATEGORY_ORDER if c in categories]
    return known + sorted(categories - set(known))


def confusion_figure(
    run: dict[str, Any],
    fields: tuple[str, ...] = ("variants.classification", "normalized.overall_result"),
) -> None:
    """Draws how often each true category was written as each category.

    A row is a true category and a column what Gentrex wrote. The shade is
    the share of the row, and the number the count.
    """
    import numpy as np

    found = [field for field in fields if run.get("confusions", {}).get(field)]
    if not found:
        print("No categories to show.")
        return
    figure, axes = plt.subplots(1, len(found), figsize=(_WIDTH, 3.0), squeeze=False)
    for ax, field in zip(axes[0], found, strict=True):
        counts = run["confusions"][field]
        truths = _order(set(counts))
        written = _order({w for row in counts.values() for w in row} | set(truths))
        grid = np.array([[counts[t].get(w, 0) for w in written] for t in truths])
        shares = grid / np.maximum(grid.sum(axis=1, keepdims=True), 1)
        ax.imshow(shares, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        for row, column in np.ndindex(grid.shape):
            if grid[row, column]:
                dark = shares[row, column] > 0.6
                ax.text(
                    column,
                    row,
                    grid[row, column],
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=_SURFACE if dark else _INK,
                )
        names = [category.replace("_", " ") for category in written]
        ax.set_xticks(range(len(written)), names, rotation=40, ha="right")
        ax.set_yticks(range(len(truths)), [c.replace("_", " ") for c in truths])
        ax.grid(visible=False)
        ax.set_title(label(field))
        ax.set_xlabel("Written by Gentrex")
    axes[0][0].set_ylabel("In the report")
    figure.tight_layout()
    _save_figure(figure, "figure-confusions")


def groups_figure(
    run: dict[str, Any], groups: tuple[str, ...], name: str = "figure-groups"
) -> None:
    """Draws the report accuracy of each kind of report, with 95% intervals.

    The values of a group come weakest first, unless they have an order of
    their own, as the number of pages has.

    Args:
        run: The run to show.
        groups: The groups of reports, as the scorer names them.
        name: The name of the figure's files.
    """

    def rows(group: str) -> list[tuple[str, dict[str, Any]]]:
        found = list(run["groups"][group].items())
        if group in _ORDERED:
            return found
        return sorted(found, key=lambda item: item[1]["report_accuracy"])

    sections = {
        GROUP_LABELS[group]: {
            f"{value if group == 'lab' else label(value)}  ({n['reports']})": wilson(
                round(n["report_accuracy"] * n["reports"]), n["reports"]
            )
            for value, n in rows(group)
        }
        for group in groups
        if len(run["groups"].get(group, {})) > 1
    }
    if not sections:
        print("No groups to show.")
        return
    count = sum(len(rows) + 1.4 for rows in sections.values())
    figure, ax = plt.subplots(figsize=(_WIDTH, 0.2 * count + 0.8))

    def draw(position: float, number: dict[str, Any]) -> None:
        ax.hlines(position, number["low"], number["high"], color=_BLUE, linewidth=1.5)
        _dot(ax, number["value"], position)

    _sections(ax, sections, draw)
    ax.set_xlim(0, 1.0)
    _percent_axis(ax)
    ax.set_xlabel("Report accuracy with 95% interval (number of reports in brackets)")
    figure.tight_layout()
    _save_figure(figure, name)


# One report, for the walkthrough


def example_report(run: dict[str, Any]) -> str:
    """Returns a report of a run that shows every command at work.

    That is the first report of which gentrex select dropped a page, or else
    the first report.
    """
    dropped = [
        d["file"] for d in records(run, "select", "decisions.jsonl") if not d["keep"]
    ]
    names = sorted(run["by_report"])
    return next(
        (pathlib.Path(d).stem for d in dropped if pathlib.Path(d).stem in names),
        names[0],
    )


def report_files(run: dict[str, Any], report: str) -> dict[str, Any]:
    """Returns what each command wrote about one report of a scored run.

    Returns:
        `truth`, the record of the report's truth file or None; `pdf`, the
        path of the PDF that the run read or None; `pages` and `decisions`,
        the report's lines of gentrex transcribe and gentrex select; `data`,
        `not_in_pages` and `normalized`, the record of gentrex extract, its
        check and the standard values. What is not on this machine is empty.
    """
    benchmark = (run["benchmark"] or {}).get("version", "")
    version = ROOT / "data" / "gentrex-bench" / benchmark
    truths = (pathlib.Path(run["truth"]), version / "truth")
    pdfs = (pathlib.Path(run["pdfs"]), version / "pdf" / copy_of(run))
    truth = next(
        (d / f"{report}.json" for d in truths if (d / f"{report}.json").exists()), None
    )
    pdf = next(
        (d / f"{report}.pdf" for d in pdfs if (d / f"{report}.pdf").exists()), None
    )

    def own(command: str, name: str) -> list[dict[str, Any]]:
        found = records(run, command, name)
        return [record for record in found if record["file"] == f"{report}.pdf"]

    extraction = (own("extract", "extractions.jsonl") or [{}])[0]
    normalized = (own("normalize", "normalized.jsonl") or [{}])[0]
    return {
        "truth": json.loads(truth.read_text(encoding="utf-8"))["record"]
        if truth
        else None,
        "pdf": pdf,
        "pages": own("transcribe", "pages.jsonl"),
        "decisions": own("select", "decisions.jsonl"),
        "data": extraction.get("data") or {},
        "not_in_pages": extraction.get("not_in_pages"),
        "normalized": normalized.get("normalized") or {},
    }


def case_table(run: dict[str, Any], report: str) -> pd.DataFrame:
    """Returns the template, kind of test, result and challenges of a report."""
    case = run["by_report"][report]["case"]
    rows = {
        "Template": case["lab"],
        "Kind of test": label(case["kind"] or ""),
        "Result": label(case["scenario"] or ""),
        "Challenges": ", ".join(label(tag) for tag in case["tags"] or []),
    }
    return pd.Series(rows, name=report, dtype=object).to_frame().T


def pages_figure(files: dict[str, Any]) -> None:
    """Draws the pages of a report, with what gentrex select decided for each.

    A kept page has a blue frame, and a dropped page is faded.
    """
    import pypdfium2

    if files["pdf"] is None:
        print("The PDF is not on this machine.")
        return
    document = pypdfium2.PdfDocument(files["pdf"])
    by_page = {decision["page"]: decision for decision in files["decisions"]}
    width = min(_WIDTH, 1.75 * len(document))
    figure, axes = plt.subplots(1, len(document), figsize=(width, 2.7), squeeze=False)
    for number, ax in enumerate(axes[0], 1):
        decision = by_page.get(number)
        kept = decision is None or decision["keep"]
        # pypdfium2 is unannotated; its docs give `scale` as a float.
        bitmap = document[number - 1].render(scale=0.6)  # pyright: ignore[reportArgumentType]
        ax.imshow(bitmap.to_pil(), alpha=1 if kept else 0.35)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(visible=False)
        framed = kept and decision is not None
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(_BLUE if framed else _GRID)
            spine.set_linewidth(2 if framed else 0.8)
        state = "" if decision is None else (", kept" if kept else ", dropped")
        ax.set_title(f"Page {number}{state}", fontweight="normal", fontsize=8.5)
    figure.tight_layout()
    plt.show()


def _copied(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Returns the field and the text of every value that gentrex extract copied."""
    found = [(field, value) for field, value in data.items() if isinstance(value, str)]
    for variant in data.get("variants") or []:
        found += [
            (f"variants.{field}", value)
            for field, value in variant.items()
            if isinstance(value, str)
        ]
    return found


def values_figure(
    files: dict[str, Any], report_errors: pd.DataFrame, pages: int = 3
) -> None:
    """Draws the kept pages of a report with a box around each copied value.

    A blue box marks a value that is right and a red one a value that isn't.
    Only values of four characters or more are searched, and only pages with
    a text layer have boxes. A value that the page prints more than once gets
    a box at each place.

    Args:
        files: The report's files, from report_files().
        report_errors: The rows of errors() of this report.
        pages: The most pages to draw.
    """
    import re

    import pdfplumber
    import pypdfium2
    from matplotlib import patches

    if files["pdf"] is None:
        print("The PDF is not on this machine.")
        return
    wrong = {
        (row["field"], str(row["found"]))
        for row in report_errors.to_dict("records")
        if row["result"] in ("wrong", "extra")
    }
    values = [(f, v) for f, v in _copied(files["data"]) if len(v.strip()) >= 4]
    kept = {d["page"] for d in files["decisions"] if d["keep"]} or None
    scale = 1.2
    shown = []
    with pdfplumber.open(files["pdf"]) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            if kept is not None and number not in kept:
                continue
            boxes = []
            for field, value in values:
                pattern = r"\s+".join(map(re.escape, value.split()))
                for hit in page.search(pattern, regex=True, case=False):
                    boxes.append((hit, (field, value) in wrong))
            shown.append((number, boxes))
            if len(shown) == pages:
                break
    if not shown:
        print("gentrex select kept no page.")
        return
    document = pypdfium2.PdfDocument(files["pdf"])
    figure, axes = plt.subplots(
        1, len(shown), figsize=(_WIDTH, 4.6 if len(shown) > 1 else 8), squeeze=False
    )
    for ax, (number, boxes) in zip(axes[0], shown, strict=True):
        # pypdfium2 is unannotated; its docs give `scale` as a float.
        bitmap = document[number - 1].render(scale=scale)  # pyright: ignore[reportArgumentType]
        ax.imshow(bitmap.to_pil())
        for hit, is_wrong in boxes:
            ax.add_patch(
                patches.Rectangle(
                    (hit["x0"] * scale - 1.5, hit["top"] * scale - 1.5),
                    (hit["x1"] - hit["x0"]) * scale + 3,
                    (hit["bottom"] - hit["top"]) * scale + 3,
                    fill=False,
                    edgecolor="#d03b3b" if is_wrong else _BLUE,
                    linewidth=1.2,
                )
            )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(visible=False)
        right = sum(not is_wrong for _, is_wrong in boxes)
        ax.set_title(
            f"Page {number}: {right} right, {len(boxes) - right} not",
            fontweight="normal",
            fontsize=8.5,
        )
    figure.tight_layout()
    plt.show()


def pages_table(files: dict[str, Any]) -> pd.DataFrame:
    """Returns the pages of a report as gentrex transcribe read them."""
    rows = [
        {
            "Page": page["page"],
            "Source": page["source"],
            "Characters": len(page["text"]),
            "Start of the text": " ".join(page["text"].split())[:100],
        }
        for page in files["pages"]
    ]
    return pd.DataFrame(rows).set_index("Page") if rows else pd.DataFrame()


def decisions_table(files: dict[str, Any]) -> pd.DataFrame:
    """Returns the answers of gentrex select for each page of a report."""
    rows = [
        {"Page": d["page"], **d["p_yes"], "Kept": "yes" if d["keep"] else "no"}
        for d in files["decisions"]
    ]
    return pd.DataFrame(rows).set_index("Page") if rows else pd.DataFrame()


def _shade(table: pd.DataFrame, column: str) -> Any:
    """Returns a table with the rows shaded whose column names a problem."""
    return table.style.apply(
        lambda cells: [
            "background-color: #fdecea" if cells[column] not in ("", "right") else ""
            for _ in cells
        ],
        axis=1,
    )


def record_table(files: dict[str, Any], report_errors: pd.DataFrame) -> Any:
    """Returns the fields of one report: printed, extracted, normalized, scored.

    Rows with a value that isn't right are shaded.

    Args:
        files: The report's files, from report_files().
        report_errors: The rows of errors() of this report.
    """
    truth, data, normalized = files["truth"], files["data"], files["normalized"]
    problems = dict(zip(report_errors["field"], report_errors["result"], strict=True))
    lost_by = dict(zip(report_errors["field"], report_errors["command"], strict=True))

    def row(field: str, scored: str, standard: Any) -> dict[str, Any]:
        printed = None if truth is None else truth.get(field)
        stated = printed is not None or data.get(field) is not None
        return {
            "In the report": printed,
            "gentrex extract": data.get(field),
            "gentrex normalize": standard,
            "Score": problems.get(scored, "right" if stated else ""),
            "Lost by": lost_by.get(scored) or "",
        }

    fields = (*FIELD_GROUPS["Patient and specimen"], *FIELD_GROUPS["Test and report"])
    rows = {label(field): row(field, field, normalized.get(field)) for field in fields}
    rows["Result"] = row(
        "overall_result_raw",
        "normalized.overall_result",
        normalized.get("overall_result"),
    )
    return _shade(pd.DataFrame(rows, dtype=object).T.fillna(""), "Score")


def variants_table(files: dict[str, Any]) -> pd.DataFrame:
    """Returns the variants of one report, printed next to extracted.

    Each variant of the truth file has a column, and each variant of the
    record one with the IDs that gentrex normalize added. Fields that no
    variant has are left out.
    """
    added = files["normalized"].get("variants") or []
    columns = {}
    for number, variant in enumerate((files["truth"] or {}).get("variants") or [], 1):
        columns[f"Variant {number}, in the report"] = {
            label(f"variants.{field}"): value for field, value in variant.items()
        }
    for number, variant in enumerate(files["data"].get("variants") or []):
        ids = (added[number] if number < len(added) else None) or {}
        columns[f"Variant {number + 1}, extracted"] = {
            label(f"variants.{field}"): value for field, value in variant.items()
        } | {
            "HGNC ID of the gene": ids.get("hgnc_id"),
            "MONDO ID of the condition": ids.get("disease_id"),
            "ClinVar ID of the variant": ids.get("clinvar_variation_id"),
        }
    table = pd.DataFrame(columns, dtype=object).dropna(how="all")
    return table.fillna("")


def features_table(files: dict[str, Any]) -> pd.DataFrame:
    """Returns the clinical features of one report with their HPO terms."""
    terms = files["normalized"].get("patient_phenotypes") or []
    rows = []
    for number, feature in enumerate(files["data"].get("patient_phenotypes") or []):
        term = (terms[number] if number < len(terms) else None) or {}
        rows.append(
            {
                "Feature": feature.get("text"),
                "Present": feature.get("present"),
                "HPO ID": term.get("hpo_id"),
                "HPO label": term.get("label"),
                "Models agree": term.get("models_agree"),
            }
        )
    return pd.DataFrame(rows).fillna("")
