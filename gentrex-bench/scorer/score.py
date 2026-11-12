"""Score a run of Gentrex against the truth files of a benchmark.

    uv run python gentrex-bench/scorer/score.py \
        --truth data/gentrex-bench/v1/truth --run results/normalize/latest

The run is a run folder of gentrex normalize. Its run.yaml names the run of
gentrex extract that it read, and so on back to the PDFs, so the scorer finds
the pages of every command. It writes scores.json with every number,
scores.md with the tables and errors.jsonl with every value that is not right.
docs/development/run-benchmark.md explains them.
"""

import argparse
import collections
import dataclasses
import datetime
import json
import logging
import pathlib
import sys
from typing import Any

import compare
import numpy as np
import yaml

from gentrex import config

_logger = logging.getLogger("score")
_COMMANDS = ("transcribe", "select", "extract", "normalize")
_RESULTS_DIR = pathlib.Path("results/gentrex-bench")
_RESAMPLES = 2000
_SEED = 1


def new_folder() -> pathlib.Path:
    """Creates results/gentrex-bench/<start time>/ and returns it."""
    stem = started = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    number = 2
    while True:
        try:
            (_RESULTS_DIR / stem).mkdir(parents=True)
            return _RESULTS_DIR / stem
        except FileExistsError:
            stem, number = f"{started}-{number}", number + 1


def _read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _runs(run_dir: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Returns the run.yaml of a run and of every run before it, by command."""
    found = {}
    path = run_dir.resolve()
    while (path / "run.yaml").is_file():
        record = yaml.safe_load((path / "run.yaml").read_text(encoding="utf-8"))
        found[path.parent.name] = {"path": str(path), **record}
        path = pathlib.Path(record["input"])
    return found


def _texts(path: pathlib.Path) -> dict[str, list[str]]:
    """Returns the page texts of each report in a pages.jsonl, by file stem."""
    texts = collections.defaultdict(list)
    for page in _read_jsonl(path):
        texts[pathlib.Path(page["file"]).stem].append(page["text"])
    return texts


def _summary(outcomes: list[compare.Outcome]) -> dict[str, Any]:
    """Returns what the main numbers need from one report."""
    variants = collections.Counter(o.result for o in outcomes if o.field == "variants")
    return {
        "correct": all(
            o.result == "correct" for o in outcomes if o.field in compare.CLINICAL
        ),
        "patient_match": all(
            o.result == "correct"
            for o in outcomes
            if o.field in ("mrn", "date_of_birth")
        ),
        "variants": {
            "matched": variants["correct"],
            "missed": variants["missed"],
            "extra": variants["extra"],
        },
    }


def _rows(summaries: list[dict[str, Any]]) -> np.ndarray:
    return np.array(
        [
            [s["correct"], s["patient_match"], *s["variants"].values()]
            for s in summaries
        ],
        dtype=float,
    )


def _numbers(sums: np.ndarray, reports: int) -> dict[str, np.ndarray]:
    """Returns the main numbers from the summed rows of one or more samples."""
    correct, patient, matched, missed, extra = np.moveaxis(sums, -1, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return {
            "report_accuracy": correct / reports,
            "patient_match": patient / reports,
            "variant_precision": matched / (matched + extra),
            "variant_recall": matched / (matched + missed),
            "variant_f1": 2 * matched / (2 * matched + missed + extra),
        }


def _interval(value: Any, samples: np.ndarray) -> dict[str, float | None]:
    """Returns a number with its 95% bootstrap interval, None where undefined."""
    samples = samples[~np.isnan(samples)]
    if np.isnan(value) or not len(samples):
        return {"value": None, "low": None, "high": None}
    low, high = np.percentile(samples, [2.5, 97.5])
    return {
        "value": round(float(value), 4),
        "low": round(float(low), 4),
        "high": round(float(high), 4),
    }


def _main_numbers(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Returns the main numbers, with intervals from resampling whole reports."""
    rows = _rows(summaries)
    picks = np.random.default_rng(_SEED).integers(0, len(rows), (_RESAMPLES, len(rows)))
    values = _numbers(rows.sum(axis=0), len(rows))
    samples = _numbers(rows[picks].sum(axis=1), len(rows))
    return {name: _interval(values[name], samples[name]) for name in values}


def difference(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Compares the report accuracy of two scored runs on the reports they share.

    Args:
        first: The scores.json of one run.
        second: The scores.json of another run.

    Returns:
        The number of shared reports, and the second run's report accuracy
        minus the first's with its 95% interval, from resampling the reports
        in pairs.
    """
    shared = sorted(set(first["by_report"]) & set(second["by_report"]))
    gains = np.array(
        [
            second["by_report"][name]["correct"] - first["by_report"][name]["correct"]
            for name in shared
        ],
        dtype=float,
    )
    picks = np.random.default_rng(_SEED).integers(
        0, len(gains), (_RESAMPLES, len(gains))
    )
    return {
        "reports": len(shared),
        **_interval(gains.mean(), gains[picks].mean(axis=1)),
    }


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _fields(outcomes: list[compare.Outcome]) -> dict[str, dict[str, Any]]:
    """Returns the counts and the accuracy of every field."""
    counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for outcome in outcomes:
        if outcome.field not in compare.ENTITIES:
            counts[outcome.field][outcome.result] += 1
            counts[outcome.field]["strict"] += outcome.strict
    fields = {}
    for field, c in counts.items():
        total = sum(c[result] for result in compare.RESULTS)
        fields[field] = {
            "values": total,
            **{name: c[name] for name in ("correct", "strict", *compare.RESULTS[1:])},
            "accuracy": _ratio(c["correct"], total),
        }
    return fields


def _entities(outcomes: list[compare.Outcome]) -> dict[str, dict[str, Any]]:
    """Returns how many variants and clinical features were found, missed or extra."""
    found = {}
    for name in compare.ENTITIES:
        own = [o for o in outcomes if o.field == name]
        if not own:
            continue
        counts = collections.Counter(o.result for o in own)
        matched, missed, extra = counts["correct"], counts["missed"], counts["extra"]
        found[name] = {
            "matched": matched,
            "missed": missed,
            "extra": extra,
            "precision": _ratio(matched, matched + extra),
            "recall": _ratio(matched, matched + missed),
            "f1": _ratio(2 * matched, 2 * matched + missed + extra),
            "missed_by": collections.Counter(
                o.command or "charged earlier" for o in own if o.result == "missed"
            ),
            "extra_by": collections.Counter(
                o.cause or o.command or "charged earlier"
                for o in own
                if o.result == "extra"
            ),
        }
    return found


def _charges(outcomes: list[compare.Outcome]) -> dict[str, dict[str, int]]:
    """Returns the missed, wrong and extra values charged to each command."""
    counts: dict[str, dict[str, int]] = {
        command: dict.fromkeys(compare.RESULTS[1:], 0) for command in _COMMANDS
    }
    for outcome in outcomes:
        if outcome.command:
            counts[outcome.command][outcome.result] += 1
    return counts


def _not_in_pages(outcomes: list[compare.Outcome]) -> dict[str, Any] | None:
    """Returns how well not_in_pages of gentrex extract tells the values that
    are not right, or None for a run from before it had the check.

    Only the copied values that gentrex extract wrote count. Each is right,
    wrong or extra.
    """
    checked = [o for o in outcomes if o.flagged is not None]
    if not checked:
        return None
    flagged = sum(o.flagged is True for o in checked)
    not_right = sum(o.result != "correct" for o in checked)
    both = sum(o.flagged is True and o.result != "correct" for o in checked)
    return {
        "values": len(checked),
        "flagged": flagged,
        "not_right": not_right,
        "flagged_and_not_right": both,
        "precision": _ratio(both, flagged),
        "recall": _ratio(both, not_right),
    }


def _groups(
    cases: dict[str, dict[str, Any]],
    truths: dict[str, dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Returns the report accuracy of the reports of each lab, tag and so on.

    A lab is held out if the truth folder has no dev case of it.
    """
    seen = {case.get("lab") for case in cases.values() if case.get("split") == "dev"}
    members: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for name in summaries:
        case = truths[name].get("case", {})
        count = len(truths[name]["record"]["variants"])
        labels = [
            ("lab", case.get("lab")),
            ("kind", case.get("kind")),
            ("scenario", case.get("scenario")),
            ("variants", str(count) if count < 2 else "2 or more"),
            *(("tag", tag) for tag in case.get("tags", [])),
        ]
        if seen and case.get("lab"):
            labels.append(
                ("held_out", "seen in dev" if case["lab"] in seen else "held out")
            )
        for group, label in labels:
            if label is not None:
                members[group, label].append(name)
    groups: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    for (group, label), names in sorted(members.items()):
        groups[group][label] = {
            "reports": len(names),
            "report_accuracy": _ratio(
                sum(summaries[name]["correct"] for name in names), len(names)
            ),
        }
    return groups


def _performance(
    runs: dict[str, dict[str, Any]], files: int, gpus: list[int] | None
) -> dict[str, Any]:
    """Returns the time and tokens of each command, and the totals per 1,000 files.

    Args:
        runs: The run.yaml of each command.
        files: The number of PDFs that the run read.
        gpus: The GPUs that the model servers of gentrex transcribe, select
            and extract ran on, or None if they aren't known.
    """
    counts = dict(zip(_COMMANDS, gpus, strict=False)) if gpus else {}
    commands = {
        name: {
            **{
                key: runs[name].get(key)
                for key in ("seconds", "requests", "prompt_tokens", "completion_tokens")
            },
            "gpus": counts.get(name, 0) if gpus else None,
            "retry": "retry" in runs[name],
        }
        for name in _COMMANDS
        if name in runs
    }
    seconds = [c["seconds"] for c in commands.values()]
    timed = bool(files) and None not in seconds
    gpu_seconds = (
        sum(c["seconds"] * c["gpus"] for c in commands.values())
        if timed and gpus
        else None
    )
    return {
        "files": files,
        "commands": commands,
        "seconds_per_1000_files": round(sum(seconds) / files * 1000) if timed else None,
        "gpu_hours_per_1000_files": (
            round(gpu_seconds / 3600 / files * 1000, 2)
            if gpu_seconds is not None
            else None
        ),
    }


def score(
    truth_dir: pathlib.Path,
    run_dir: pathlib.Path,
    split: str,
    gpus: list[int] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Scores a run of gentrex normalize against the truth files of a split.

    A truth file's report is the PDF with the same name. A report that the
    run doesn't have counts as all missed.

    Args:
        truth_dir: Folder of truth files.
        run_dir: Run folder of gentrex normalize.
        split: The split to score, as the truth files name it, or "all".
        gpus: The GPUs that the model servers of gentrex transcribe, select
            and extract ran on, for the GPU-hours.

    Returns:
        The scores, and every value that is not right.

    Raises:
        ValueError: The run folder or the truth files don't fit.
    """
    runs = _runs(run_dir)
    if "normalize" not in runs or "transcribe" not in runs:
        raise ValueError(f"{run_dir} is not a run folder of gentrex normalize")
    truths = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(truth_dir.glob("*.json"))
    }
    cases = {name: truth.get("case", {}) for name, truth in truths.items()}
    chosen = [
        name
        for name, case in cases.items()
        if split == "all" or case.get("split") == split
    ]
    if not chosen:
        raise ValueError(f"{truth_dir} has no truth files of the split {split}")

    transcribed = _texts(pathlib.Path(runs["transcribe"]["path"]) / "pages.jsonl")
    kept = _texts(
        pathlib.Path(runs.get("select", runs["transcribe"])["path"]) / "pages.jsonl"
    )
    reports = {
        pathlib.Path(report["file"]).stem: report
        for report in _read_jsonl(
            pathlib.Path(runs["normalize"]["path"]) / "normalized.jsonl"
        )
    }
    schema = config.load_schema()
    hpo = runs["normalize"]["settings"].get("hpo_version") is not None
    clinvar = runs["normalize"]["settings"].get("clinvar_sha256") is not None

    outcomes: list[compare.Outcome] = []
    summaries = {}
    errors = []
    for name in chosen:
        own = compare.compare(
            truths[name],
            reports.get(name),
            transcribed.get(name, []),
            kept.get(name, []),
            schema,
            hpo,
            clinvar,
        )
        outcomes += own
        summaries[name] = _summary(own)
        for outcome in own:
            if outcome.result != "correct":
                error = {"report": name, **dataclasses.asdict(outcome)}
                del error["strict"]
                errors.append(error)

    manifest = truth_dir.parent / "manifest.json"
    scores = {
        "truth": str(truth_dir.resolve()),
        "benchmark": (
            json.loads(manifest.read_text(encoding="utf-8"))
            if manifest.is_file()
            else None
        ),
        "split": split,
        "pdfs": runs["transcribe"]["input"],
        "reports": len(chosen),
        "without_record": sum(
            not (reports.get(name) or {}).get("data") for name in chosen
        ),
        "main": _main_numbers(list(summaries.values())),
        "entities": _entities(outcomes),
        "fields": _fields(outcomes),
        "charges": _charges(outcomes),
        "not_in_pages": _not_in_pages(outcomes),
        "groups": _groups(cases, truths, summaries),
        "performance": _performance(runs, len(transcribed), gpus),
        "runs": runs,
        "by_report": summaries,
    }
    return scores, errors


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _table(header: list[str], rows: list[list[Any]]) -> str:
    lines = [header, ["---"] * len(header), *rows]
    return "\n".join("| " + " | ".join(map(str, line)) + " |" for line in lines)


_MAIN_LABELS = {
    "report_accuracy": "Report accuracy",
    "patient_match": "MRN and date of birth both right",
    "variant_f1": "Variant F1",
    "variant_precision": "Variant precision",
    "variant_recall": "Variant recall",
}
_ENTITY_LABELS = {
    "variants": "Variants",
    "patient_phenotypes": "Clinical features, by text",
    "normalized.patient_phenotypes": "Clinical features, by HPO ID",
}


def markdown(scores: dict[str, Any]) -> str:
    """Returns the scores as tables."""
    performance = scores["performance"]
    models = {
        name: (run["settings"].get("ocr") or run["settings"]).get("model")
        for name, run in scores["runs"].items()
    }
    check = scores["not_in_pages"]
    checked = []
    if check:
        checked = [
            "## Values not in the pages",
            f"`gentrex extract` copied {check['values']} values and named"
            f" {check['flagged']} of them in `not_in_pages`."
            f" {check['flagged_and_not_right']} of those were wrong or extra"
            f" ({percent(check['precision'])}). In all, {check['not_right']} copied"
            f" values were wrong or extra, so the check named"
            f" {percent(check['recall'])} of them.",
        ]
    parts = [
        "# Scores",
        f"{scores['reports']} reports of the split `{scores['split']}`, read from"
        f" `{scores['pdfs']}`. {scores['without_record']} of them have no record.",
        "## Main numbers",
        _table(
            ["Measure", "Value", "95% interval"],
            [
                [
                    label,
                    percent(scores["main"][name]["value"]),
                    f"{percent(scores['main'][name]['low'])} to"
                    f" {percent(scores['main'][name]['high'])}",
                ]
                for name, label in _MAIN_LABELS.items()
            ],
        ),
        "## Variants and clinical features",
        _table(
            ["", "Matched", "Missed", "Extra", "Precision", "Recall", "F1"],
            [
                [
                    _ENTITY_LABELS[name],
                    e["matched"],
                    e["missed"],
                    e["extra"],
                    percent(e["precision"]),
                    percent(e["recall"]),
                    percent(e["f1"]),
                ]
                for name, e in scores["entities"].items()
            ],
        ),
        _table(
            ["", "Missed, by command", "Extra, by cause"],
            [
                [
                    _ENTITY_LABELS[name],
                    ", ".join(f"{k}: {v}" for k, v in e["missed_by"].items()) or "none",
                    ", ".join(f"{k}: {v}" for k, v in e["extra_by"].items()) or "none",
                ]
                for name, e in scores["entities"].items()
            ],
        ),
        "## Where errors come from",
        _table(
            ["Command", "Missed", "Wrong", "Extra"],
            [
                [f"`gentrex {name}`", c["missed"], c["wrong"], c["extra"]]
                for name, c in scores["charges"].items()
            ],
        ),
        *checked,
        "## Fields",
        _table(
            ["Field", "Values", "Accuracy", "Exact", "Missed", "Extra", "Wrong"],
            [
                [
                    f"`{name}`",
                    f["values"],
                    percent(f["accuracy"]),
                    percent(_ratio(f["strict"], f["values"])),
                    f["missed"],
                    f["extra"],
                    f["wrong"],
                ]
                for name, f in scores["fields"].items()
            ],
        ),
        "## Groups",
        _table(
            ["Group", "Reports", "Report accuracy"],
            [
                [f"{group}: {label}", g["reports"], percent(g["report_accuracy"])]
                for group, labels in scores["groups"].items()
                for label, g in labels.items()
            ],
        ),
        "## Speed and cost",
        _table(
            ["Command", "Model", "Seconds", "Requests", "Tokens in", "Tokens out"],
            [
                [
                    f"`gentrex {name}`" + (" (retry)" if c["retry"] else ""),
                    models[name] or "",
                    c["seconds"],
                    c["requests"],
                    c["prompt_tokens"],
                    c["completion_tokens"],
                ]
                for name, c in performance["commands"].items()
            ],
        ),
        f"The run read {performance['files']} PDFs. That is"
        f" {performance['seconds_per_1000_files']} seconds and"
        f" {performance['gpu_hours_per_1000_files']} GPU-hours per 1,000 PDFs.",
    ]
    return "\n\n".join(parts) + "\n"


def write(
    out: pathlib.Path, scores: dict[str, Any], errors: list[dict[str, Any]]
) -> None:
    """Writes scores.json, scores.md and errors.jsonl to a folder."""
    (out / "scores.json").write_text(
        json.dumps(scores, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "scores.md").write_text(markdown(scores), encoding="utf-8")
    with (out / "errors.jsonl").open("w", encoding="utf-8") as fh:
        for error in errors:
            fh.write(json.dumps(error, ensure_ascii=False) + "\n")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Adds the options that the scorer shares with gentrex-bench/run.py."""
    parser.add_argument(
        "--split",
        default="dev",
        help="Split to score: dev, test or all. The default is dev.",
    )
    parser.add_argument(
        "--gpus",
        type=int,
        nargs=3,
        metavar="N",
        help="GPUs that the model servers of gentrex transcribe, select and"
        " extract ran on, for the GPU-hours.",
    )


def main() -> int:
    """Scores the run named on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description="Score a run of Gentrex.")
    parser.add_argument(
        "--truth",
        type=pathlib.Path,
        default=pathlib.Path("data/gentrex-bench/v1/truth"),
        help="Folder of truth files.",
    )
    parser.add_argument(
        "--run",
        type=pathlib.Path,
        default=pathlib.Path("results/normalize/latest"),
        help="Run folder of gentrex normalize to score.",
    )
    add_arguments(parser)
    args = parser.parse_args()
    try:
        scores, errors = score(args.truth, args.run, args.split, args.gpus)
    except ValueError as exc:
        _logger.error("%s", exc)
        return 1
    out = new_folder()
    write(out, scores, errors)
    main_numbers = scores["main"]
    _logger.info(
        "report accuracy %s on %d reports; wrote %s",
        percent(main_numbers["report_accuracy"]["value"]),
        scores["reports"],
        out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
