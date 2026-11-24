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
import math
import pathlib
import re
import statistics
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
# The version of scores.json, for the notebooks that read it.
FORMAT = 3
# Standard values with a fixed list of categories, besides the fields of the
# schema that have one.
_CATEGORIES = ("normalized.overall_result", "normalized.specimen_type")
_PATHOGENIC = frozenset({"pathogenic", "likely_pathogenic"})
_WORD = re.compile(r"[a-z0-9]+")


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


def _is_extracted(outcome: compare.Outcome) -> bool:
    """Whether the value is one of gentrex extract, not a standard value."""
    return not outcome.field.startswith("normalized.")


def _is_stated(outcome: compare.Outcome) -> bool:
    """Whether the report states the value, so that it can be found or lost."""
    return (
        outcome.truth is not None
        and compare.key(outcome.field, outcome.truth) is not None
    )


def _value_counts(outcomes: list[compare.Outcome]) -> dict[str, int]:
    """Returns how many values are right, missed and extra.

    A value that the report doesn't state and the record leaves empty counts
    nowhere. A wrong value is both missed and extra.
    """
    return {
        "right": sum(o.result == "correct" and _is_stated(o) for o in outcomes),
        "missed": sum(o.result in ("missed", "wrong") for o in outcomes),
        "extra": sum(o.result in ("extra", "wrong") for o in outcomes),
    }


def _strict_value_counts(outcomes: list[compare.Outcome]) -> dict[str, int]:
    """Returns exact-match value counts where lenient-only matches count as wrong."""
    counts = _value_counts(outcomes)
    lenient_only = sum(
        o.result == "correct" and not o.strict and _is_stated(o) for o in outcomes
    )
    return {
        "right": counts["right"] - lenient_only,
        "missed": counts["missed"] + lenient_only,
        "extra": counts["extra"] + lenient_only,
    }


def _report_field_counts(
    outcomes: list[compare.Outcome],
) -> dict[str, tuple[int, int, int]]:
    """Returns per-field (right, lost, added) counts for extracted fields."""
    counts: dict[str, list[int]] = {}
    for o in outcomes:
        if not _is_extracted(o) or o.field in compare.ENTITIES:
            continue
        row = counts.setdefault(o.field, [0, 0, 0])
        if o.result == "correct" and _is_stated(o):
            row[0] += 1
        elif o.result == "missed":
            row[1] += 1
        elif o.result == "extra":
            row[2] += 1
        elif o.result == "wrong":
            row[1] += 1
            row[2] += 1
    return {
        field: (right, lost, added) for field, (right, lost, added) in counts.items()
    }


def _summary(outcomes: list[compare.Outcome]) -> dict[str, Any]:
    """Returns what the main numbers need from one report."""
    variant_outcomes = [o for o in outcomes if o.field == "variants"]
    variants = collections.Counter(o.result for o in variant_outcomes)
    clin_bad = sum(
        o.result == "correct" and o.clinical_ok is False for o in variant_outcomes
    )
    extracted = [o for o in outcomes if _is_extracted(o)]
    return {
        "correct": all(
            o.result == "correct" for o in outcomes if o.field in compare.CLINICAL
        ),
        "complete": all(o.result == "correct" for o in outcomes),
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
        "clinical_variants": {
            "matched": variants["correct"] - clin_bad,
            "missed": variants["missed"] + clin_bad,
            "extra": variants["extra"] + clin_bad,
        },
        "values": _value_counts(extracted),
        "strict_values": _strict_value_counts(extracted),
        "errors": sum(o.result != "correct" for o in outcomes),
        # The checks of Gentrex that flagged a value of the report.
        "flags": sorted(
            {"not_in_pages" for o in outcomes if o.flagged}
            | {name for o in outcomes for name, hit in o.checks.items() if hit}
        ),
    }


def _rows(summaries: list[dict[str, Any]]) -> np.ndarray:
    return np.array(
        [
            [
                s["correct"],
                s["complete"],
                s["patient_match"],
                *s["variants"].values(),
                *s["clinical_variants"].values(),
                *s["values"].values(),
                *s["strict_values"].values(),
            ]
            for s in summaries
        ],
        dtype=float,
    )


def _numbers(sums: np.ndarray, reports: int) -> dict[str, np.ndarray]:
    """Returns the main numbers from the summed rows of one or more samples."""
    (
        correct,
        complete,
        patient,
        matched,
        missed,
        extra,
        clin_matched,
        clin_missed,
        clin_extra,
        right,
        lost,
        added,
        strict_right,
        strict_lost,
        strict_added,
    ) = np.moveaxis(sums, -1, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return {
            "report_accuracy": correct / reports,
            "record_accuracy": complete / reports,
            "patient_match": patient / reports,
            "value_precision": right / (right + added),
            "value_recall": right / (right + lost),
            "value_f1": 2 * right / (2 * right + lost + added),
            "strict_value_f1": (
                2 * strict_right / (2 * strict_right + strict_lost + strict_added)
            ),
            "variant_precision": matched / (matched + extra),
            "variant_recall": matched / (matched + missed),
            "variant_f1": 2 * matched / (2 * matched + missed + extra),
            "clinical_variant_precision": clin_matched / (clin_matched + clin_extra),
            "clinical_variant_recall": clin_matched / (clin_matched + clin_missed),
            "clinical_variant_f1": (
                2 * clin_matched / (2 * clin_matched + clin_missed + clin_extra)
            ),
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


def _macro_field_f1(
    field_counts: list[dict[str, tuple[int, int, int]]], picks: np.ndarray
) -> dict[str, float | None]:
    """Returns macro-averaged F1 over extracted fields with its 95% interval."""
    fields = sorted({f for counts in field_counts for f in counts})
    if not fields:
        return {"value": None, "low": None, "high": None}
    arr = np.array(
        [[counts.get(field, (0, 0, 0)) for field in fields] for counts in field_counts],
        dtype=float,
    )

    def macro(sums: np.ndarray) -> np.ndarray:
        right, lost, added = np.moveaxis(sums, -1, 0)
        denom = 2 * right + lost + added
        with np.errstate(invalid="ignore", divide="ignore"):
            f1 = np.where(denom > 0, 2 * right / denom, np.nan)
            return np.nanmean(f1, axis=-1)

    return _interval(macro(arr.sum(axis=0)), macro(arr[picks].sum(axis=1)))


def _main_numbers(
    summaries: list[dict[str, Any]],
    field_counts: list[dict[str, tuple[int, int, int]]] | None = None,
) -> dict[str, Any]:
    """Returns the main numbers, with intervals from resampling whole reports."""
    rows = _rows(summaries)
    picks = np.random.default_rng(_SEED).integers(0, len(rows), (_RESAMPLES, len(rows)))
    values = _numbers(rows.sum(axis=0), len(rows))
    samples = _numbers(rows[picks].sum(axis=1), len(rows))
    found = {name: _interval(values[name], samples[name]) for name in values}
    if field_counts is not None:
        found["macro_field_f1"] = _macro_field_f1(field_counts, picks)
    return found


def _mcnemar_exact(b: int, c: int) -> float:
    """Returns the exact two-sided McNemar p-value from discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return round(min(1.0, 2.0 * tail), 4)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Returns the exact two-sided Fisher's exact p-value for a 2x2 table."""
    row1, row2 = a + b, c + d
    col1, total = a + c, a + b + c + d
    if not row1 or not row2 or not col1 or col1 == total:
        return 1.0
    denom = math.comb(total, col1)

    def prob(x: int) -> float:
        return math.comb(row1, x) * math.comb(row2, col1 - x) / denom

    observed = prob(a)
    low, high = max(0, col1 - row2), min(row1, col1)
    p = sum(prob(x) for x in range(low, high + 1) if prob(x) <= observed + 1e-12)
    return round(min(1.0, p), 4)


def difference(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Compares the report accuracy of two scored runs on the reports they share.

    Args:
        first: The scores.json of one run.
        second: The scores.json of another run.

    Returns:
        The number of shared reports, the second run's report accuracy minus
        the first's with its 95% paired bootstrap interval, and the exact
        two-sided McNemar p-value.
    """
    shared = sorted(set(first["by_report"]) & set(second["by_report"]))
    if not shared:
        return {"reports": 0, "value": None, "low": None, "high": None, "p_value": None}
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
    b = int((gains == 1).sum())
    c = int((gains == -1).sum())
    return {
        "reports": len(shared),
        **_interval(gains.mean(), gains[picks].mean(axis=1)),
        "p_value": _mcnemar_exact(b, c),
    }


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _fields(outcomes: list[compare.Outcome]) -> dict[str, dict[str, Any]]:
    """Returns the counts, the accuracy and the F1 of every field.

    The accuracy counts every report, also one that rightly leaves the field
    empty. Precision, recall and F1 count only stated and written values.
    """
    counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    kinds: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for outcome in outcomes:
        if outcome.field not in compare.ENTITIES:
            counts[outcome.field][outcome.result] += 1
            counts[outcome.field]["strict"] += outcome.strict
            counts[outcome.field]["right"] += (
                outcome.result == "correct" and _is_stated(outcome)
            )
            counts[outcome.field]["lost_earlier"] += outcome.result in (
                "missed",
                "wrong",
            ) and outcome.command in ("transcribe", "select")
            if outcome.result != "correct" and _is_extracted(outcome):
                kinds[outcome.field][_error_kind(outcome)] += 1
    fields = {}
    for field, c in counts.items():
        total = sum(c[result] for result in compare.RESULTS)
        right = c["right"]
        lost, added = c["missed"] + c["wrong"], c["extra"] + c["wrong"]
        fields[field] = {
            "values": total,
            **{name: c[name] for name in ("correct", "strict", *compare.RESULTS[1:])},
            "accuracy": _ratio(c["correct"], total),
            "stated": right + lost,
            "precision": _ratio(right, right + added),
            "recall": _ratio(right, right + lost),
            "f1": _ratio(2 * right, 2 * right + lost + added),
            # Recall and F1 of the values that reached gentrex extract.
            "recall_given_input": _ratio(right, right + lost - c["lost_earlier"]),
            "f1_given_input": _ratio(
                2 * right, 2 * right + lost - c["lost_earlier"] + added
            ),
            "kinds": dict(kinds[field]),
        }
    return fields


def _error_kind(outcome: compare.Outcome) -> str:
    """Returns the kind of a value that isn't right.

    A missed value is missed. A wrong or extra text has the kind that
    compare gives it, and another wrong or extra value is a wrong category
    or number.
    """
    if outcome.result == "missed":
        return "missed"
    return outcome.cause or "category"


def _categories(schema: dict[str, Any]) -> set[str]:
    """Returns the fields whose values come from a fixed list of categories."""
    variant = schema["properties"]["variants"]["items"]["properties"]
    return (
        {name for name, field in schema["properties"].items() if "enum" in field}
        | {f"variants.{name}" for name, field in variant.items() if "enum" in field}
        | set(_CATEGORIES)
    )


def _confusions(
    outcomes: list[compare.Outcome], fields: set[str]
) -> dict[str, dict[str, dict[str, int]]]:
    """Returns how often each true category was written as each category.

    No category is written as "none".
    """
    found: dict[str, dict[str, collections.Counter[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter)
    )
    for outcome in outcomes:
        if outcome.field in fields:
            truth = "none" if outcome.truth is None else str(outcome.truth)
            written = "none" if outcome.found is None else str(outcome.found)
            found[outcome.field][truth][written] += 1
    return {
        field: {truth: dict(written) for truth, written in rows.items()}
        for field, rows in found.items()
    }


def _normalize(outcomes: list[compare.Outcome]) -> dict[str, Any]:
    """Returns the accuracy of each standard value, end to end and on its own.

    `given_right_source` leaves out the values whose source gentrex extract
    already got wrong, which no command is charged for. The HGNC IDs are
    also split by whether the report prints the gene's approved symbol.
    """
    found: dict[str, Any] = {}
    groups: dict[str, list[compare.Outcome]] = collections.defaultdict(list)
    for outcome in outcomes:
        if outcome.field.startswith("normalized.") and outcome.field not in (
            compare.ENTITIES
        ):
            groups[outcome.field].append(outcome)
            if outcome.subgroup:
                groups[f"{outcome.field} ({outcome.subgroup})"].append(outcome)
    for name, own in groups.items():
        right = sum(o.result == "correct" for o in own)
        source_wrong = sum(o.result != "correct" and o.command is None for o in own)
        found[name] = {
            "values": len(own),
            "right": right,
            "source_wrong": source_wrong,
            "accuracy": _ratio(right, len(own)),
            "given_right_source": _ratio(right, len(own) - source_wrong),
        }
    return found


def _hpo(outcomes: list[compare.Outcome]) -> dict[str, Any] | None:
    """Returns how well gentrex normalize found the HPO term of each feature.

    Only the clinical features whose text gentrex extract found count. The
    first candidate is the term unless the models' similarity was too low,
    and then the feature has no term. `top_5` counts the features whose
    true term is among the candidates. A run without HPO terms gives None.
    """
    own = [
        o
        for o in outcomes
        if o.field == "normalized.patient_phenotypes" and o.subgroup is not None
    ]
    if not own:
        return None

    def numbers(chosen: list[compare.Outcome]) -> dict[str, Any]:
        return {
            "features": len(chosen),
            "top_1": _ratio(
                sum(o.rank == 1 and o.subgroup == "term" for o in chosen), len(chosen)
            ),
            "first_candidate": _ratio(sum(o.rank == 1 for o in chosen), len(chosen)),
            "top_5": _ratio(sum(o.rank is not None for o in chosen), len(chosen)),
            "no_term": _ratio(
                sum(o.subgroup == "no term" for o in chosen), len(chosen)
            ),
        }

    found = {"all": numbers(own)}
    for name, hit in (("models agree", False), ("models disagree", True)):
        chosen = [o for o in own if o.checks.get("hpo_models_disagree") is hit]
        if chosen:
            found[name] = numbers(chosen)
    return found


def _variant_kinds(outcomes: list[compare.Outcome]) -> dict[str, dict[str, Any]]:
    """Returns how well each kind of variant was found and described.

    The accuracy of the classification, the zygosity and the copy number
    counts the variants of the kind that were found.
    """
    found = {}
    for kind in compare.check.VARIANT_KINDS:
        own = [o for o in outcomes if o.kind == kind]
        whole = collections.Counter(o.result for o in own if o.field == "variants")
        if not whole:
            continue
        matched, missed, extra = whole["correct"], whole["missed"], whole["extra"]
        found[kind] = {
            "stated": matched + missed,
            "found": matched,
            "missed": missed,
            "extra": extra,
            "recall": _ratio(matched, matched + missed),
            "precision": _ratio(matched, matched + extra),
            "f1": _ratio(2 * matched, 2 * matched + missed + extra),
        }
        for name in ("classification", "zygosity", "copy_number"):
            values = [o for o in own if o.field == f"variants.{name}"]
            right = sum(o.result == "correct" for o in values)
            found[kind][name] = _ratio(right, len(values))
    return found


def _funnel(outcomes: list[compare.Outcome]) -> dict[str, Any]:
    """Returns what became of the values that the reports state.

    Each stated value is right in the record, or lost by gentrex transcribe,
    select or extract. `extra` counts the values of the records that no
    report states.
    """
    own = [o for o in outcomes if _is_extracted(o)]
    lost = collections.Counter(
        o.command for o in own if o.result in ("missed", "wrong")
    )
    right = sum(o.result == "correct" and _is_stated(o) for o in own)
    reached = right + lost["extract"]
    written = right + sum(o.result in ("extra", "wrong") for o in own)
    return {
        "stated": right + sum(lost.values()),
        "right": right,
        "lost": {command: lost[command] for command in _COMMANDS[:3]},
        "extra": sum(o.result == "extra" for o in own),
        # Of the values that reached gentrex extract, the share it got right.
        "extract_recall": _ratio(right, reached),
        "extract_precision": _ratio(right, written),
    }


def _words(text: str) -> collections.Counter[str]:
    return collections.Counter(_WORD.findall(text.casefold()))


def _pages(
    truths: dict[str, dict[str, Any]],
    chosen: list[str],
    transcribed: list[dict[str, Any]],
    kept: list[dict[str, Any]] | None,
    value_pages: list[set["Page"]] | None = None,
) -> dict[str, Any]:
    """Returns what gentrex transcribe and gentrex select did to the pages.

    The words of each page that went to OCR are compared with the words of
    the same page in the truth file, whatever their order. `ocr_word_recall`
    is the share of the true words that OCR wrote, and `ocr_word_precision`
    the share of OCR's words that are true.

    A page is `needed` if it is the only page of its report that prints one
    of the stated values. `needed_kept` counts the needed pages that gentrex
    select kept, and `other_dropped` the other pages that it dropped.

    Args:
        truths: The truth files, by report.
        chosen: The reports that are scored.
        transcribed: The lines of pages.jsonl of gentrex transcribe.
        kept: The lines of pages.jsonl of gentrex select, or None if the run
            skipped it.
    """
    names = set(chosen)
    pages = [p for p in transcribed if pathlib.Path(p["file"]).stem in names]
    true_words = written = shared = 0
    for page in pages:
        if page.get("source") != "scanned":
            continue
        truth = truths[pathlib.Path(page["file"]).stem].get("pages") or []
        text = next((t["text"] for t in truth if t["page"] == page["page"]), None)
        if text is None:
            continue
        expected, found = _words(text), _words(page["text"])
        true_words += sum(expected.values())
        written += sum(found.values())
        shared += sum((expected & found).values())
    by_report: dict[str, list[str]] = collections.defaultdict(list)
    for page in pages:
        by_report[pathlib.Path(page["file"]).stem].append(page["text"])
    critical_fields = {
        "mrn",
        "date_of_birth",
        "karyotype",
        "overall_result_raw",
        "gene_symbol",
        "hgvs_c",
        "dna_change_raw",
    }
    values_stated = values_preserved = 0
    critical_stated = critical_preserved = 0
    for name in chosen:
        lines = [compare.check.page_lines(t) for t in by_report.get(name, [])]
        for path, value in compare.check._printed(truths[name]["record"]):
            preserved = any(compare.check.locate(value, lines))
            values_stated += 1
            values_preserved += preserved
            if path.rsplit("/", 1)[-1] in critical_fields:
                critical_stated += 1
                critical_preserved += preserved
    needed = _needed(
        _value_pages(truths, chosen) if value_pages is None else value_pages
    )
    every = _every_page(truths, chosen)
    selected = (
        None
        if kept is None
        else {(pathlib.Path(p["file"]).stem, p["page"]) for p in kept}
    )
    return {
        "total": len(pages),
        "ocr": sum(page.get("source") == "scanned" for page in pages),
        "empty": sum(not page["text"] for page in pages),
        "kept": (
            None
            if kept is None
            else sum(pathlib.Path(p["file"]).stem in names for p in kept)
        ),
        "ocr_word_recall": _ratio(shared, true_words),
        "ocr_word_precision": _ratio(shared, written),
        "values_stated": values_stated,
        "values_preserved": values_preserved,
        "values_preserved_rate": _ratio(values_preserved, values_stated),
        "critical_values_stated": critical_stated,
        "critical_values_preserved": critical_preserved,
        "critical_values_preserved_rate": _ratio(critical_preserved, critical_stated),
        "needed": len(needed),
        "needed_kept": None if selected is None else len(needed & selected),
        "other": len(every - needed),
        "other_dropped": (
            None if selected is None else len((every - needed) - selected)
        ),
    }


Page = tuple[str, int]


def _value_pages(
    truths: dict[str, dict[str, Any]], chosen: list[str]
) -> list[set[Page]]:
    """Returns the pages that print each stated value, by report and page.

    A value that no page prints whole or line by line is left out.
    """
    found = []
    for name in chosen:
        texts = [
            compare.check.page_lines(page["text"])
            for page in truths[name].get("pages") or []
        ]
        for _, value in compare.check._printed(truths[name]["record"]):
            whole, split = compare.check.locate(value, texts)
            if whole or split:
                found.append({(name, page) for page in whole or split})
    return found


def _needed(value_pages: list[set[Page]]) -> set[Page]:
    """Returns the pages that are the only page to print some stated value."""
    return {next(iter(pages)) for pages in value_pages if len(pages) == 1}


def _every_page(truths: dict[str, dict[str, Any]], chosen: list[str]) -> set[Page]:
    return {
        (name, page["page"])
        for name in chosen
        for page in truths[name].get("pages") or []
    }


_THRESHOLDS = (0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98)


def _select_scores(
    answers: dict[Page, dict[str, Any]], needed: set[Page]
) -> dict[str, float | None]:
    """Returns AUROC, AUPRC, Brier score, and 10-bin ECE of max(p_yes)."""
    by_score: dict[float, list[bool]] = collections.defaultdict(list)
    pairs: list[tuple[float, int]] = []
    for page, decision in answers.items():
        probs = [p for p in decision["p_yes"].values() if p is not None]
        if probs:
            prob = max(probs)
            label = page in needed
            by_score[prob].append(label)
            pairs.append((prob, int(label)))
    if not pairs:
        return {"auroc": None, "auprc": None, "brier": None, "ece": None}
    brier = round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 4)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(10)]
    for prob, label in pairs:
        bins[min(int(prob * 10), 9)].append((prob, label))
    ece = round(
        sum(
            len(bucket)
            / len(pairs)
            * abs(
                sum(y for _, y in bucket) / len(bucket)
                - sum(p for p, _ in bucket) / len(bucket)
            )
            for bucket in bins
            if bucket
        ),
        4,
    )
    pos = sum(y for _, y in pairs)
    neg = len(pairs) - pos
    if not pos or not neg:
        return {"auroc": None, "auprc": None, "brier": brier, "ece": ece}
    wins = seen_neg = 0.0
    for score_value in sorted(by_score):
        flags = by_score[score_value]
        n_pos = sum(flags)
        n_neg = len(flags) - n_pos
        wins += n_pos * (seen_neg + 0.5 * n_neg)
        seen_neg += n_neg
    ap = tp = total = 0.0
    for score_value in sorted(by_score, reverse=True):
        flags = by_score[score_value]
        n_pos = sum(flags)
        tp += n_pos
        total += len(flags)
        if n_pos:
            ap += (n_pos / pos) * (tp / total)
    return {
        "auroc": round(wins / (pos * neg), 4),
        "auprc": round(ap, 4),
        "brier": brier,
        "ece": ece,
    }


def _select(
    truths: dict[str, dict[str, Any]],
    chosen: list[str],
    decisions: list[dict[str, Any]],
    threshold: float,
    value_pages: list[set[Page]] | None = None,
) -> dict[str, Any]:
    """Returns how well gentrex select chose the pages, and at other thresholds.

    A page is needed if it is the only page that prints a stated value. A
    value is reachable if gentrex select kept a page that prints it. The
    sweep keeps the pages again for each threshold from the probabilities
    of "yes" that the run wrote, so it needs no new run.

    Args:
        truths: The truth files, by report.
        chosen: The reports that are scored.
        decisions: The lines of decisions.jsonl of gentrex select.
        threshold: The run's select.keep_threshold.
    """
    if value_pages is None:
        value_pages = _value_pages(truths, chosen)
    needed = _needed(value_pages)
    names = set(chosen)
    answers = {
        (pathlib.Path(d["file"]).stem, d["page"]): d
        for d in decisions
        if pathlib.Path(d["file"]).stem in names
    }

    def kept(at: float) -> set[Page]:
        """The pages that gentrex select keeps at a threshold.

        A page without answers keeps the decision of the run, as a page
        without text, which is never kept.
        """
        found = set()
        for page, decision in answers.items():
            p_yes = list(decision["p_yes"].values())
            if all(p is None for p in p_yes):
                keep = decision["keep"]
            else:
                keep = any(p is None or p >= at for p in p_yes)
            if keep:
                found.add(page)
        return found

    def numbers(at: float) -> dict[str, Any]:
        chosen_pages = kept(at)
        reachable = sum(bool(pages & chosen_pages) for pages in value_pages)
        return {
            "threshold": at,
            "pages_kept": _ratio(len(chosen_pages), len(answers)),
            "needed_kept": _ratio(len(needed & chosen_pages), len(needed)),
            "values_reachable": _ratio(reachable, len(value_pages)),
        }

    now = kept(threshold)
    pages = set(answers)
    other = pages - needed
    only = collections.Counter()
    only_needed = collections.Counter()
    for page in now:
        p_yes = answers[page]["p_yes"]
        above = [name for name, p in p_yes.items() if p is not None and p >= threshold]
        if len(above) == 1:
            only[above[0]] += 1
            only_needed[above[0]] += page in needed
    return {
        "threshold": threshold,
        "pages": len(pages),
        **_select_scores(answers, needed),
        "needed_kept": len(needed & now),
        "needed_dropped": len(needed & pages - now),
        "other_kept": len(other & now),
        "other_dropped": len(other - now),
        "values": len(value_pages),
        "values_reachable": sum(bool(pages & now) for pages in value_pages),
        "only_by": {
            name: {"pages": count, "needed": only_needed[name]}
            for name, count in only.items()
        },
        "sweep": [numbers(at) for at in sorted({*_THRESHOLDS, threshold})],
    }


def _data(truths: dict[str, dict[str, Any]], chosen: list[str]) -> dict[str, Any]:
    """Returns what the scored reports are made of."""
    pages = [len(truths[name]["pages"]) for name in chosen if truths[name].get("pages")]
    words = [
        sum(
            len(_WORD.findall(page["text"].casefold()))
            for page in truths[name]["pages"]
        )
        for name in chosen
        if truths[name].get("pages")
    ]
    records = [truths[name]["record"] for name in chosen]
    ids = [ids for name in chosen for ids in truths[name]["normalized"]["variants"]]
    attempts = [
        (truths[name].get("case", {}).get("writer") or {}).get("attempt")
        for name in chosen
    ]

    def _iqr(values: list[int]) -> list[float] | None:
        if not values:
            return None
        q25, q75 = np.percentile(values, [25, 75])
        return [round(float(q25), 1), round(float(q75), 1)]

    return {
        "reports": len(chosen),
        # Reports whose first text failed the generator's check.
        "rewritten": (
            sum(attempt > 1 for attempt in attempts if attempt)
            if any(attempts)
            else None
        ),
        "pages": sum(pages) if pages else None,
        "pages_median": statistics.median(pages) if pages else None,
        "pages_iqr": _iqr(pages),
        "pages_most": max(pages) if pages else None,
        "words_median": statistics.median(words) if words else None,
        "words_iqr": _iqr(words),
        "variants": sum(len(record["variants"]) for record in records),
        "negative_reports": sum(not record["variants"] for record in records),
        "multi_variant_reports": sum(
            len(record["variants"]) >= 2 for record in records
        ),
        "genes": len({i.get("gene_symbol") for i in ids if i.get("gene_symbol")}),
        "conditions": len({i.get("disease_id") for i in ids if i.get("disease_id")}),
        "features": sum(len(record["patient_phenotypes"]) for record in records),
        "distractors": sum(
            len(truths[name].get("distractors") or []) for name in chosen
        ),
    }


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


def _check(checked: list[tuple[bool, compare.Outcome]]) -> dict[str, Any]:
    """Returns how well a check tells the values that are not right.

    Args:
        checked: Whether the check flagged each value that it looked at, with
            the value's outcome.
    """
    flagged = sum(hit for hit, _ in checked)
    not_right = sum(o.result != "correct" for _, o in checked)
    both = sum(hit and o.result != "correct" for hit, o in checked)
    return {
        "values": len(checked),
        "flagged": flagged,
        "not_right": not_right,
        "flagged_and_not_right": both,
        "precision": _ratio(both, flagged),
        "recall": _ratio(both, not_right),
    }


def _checks(outcomes: list[compare.Outcome]) -> dict[str, dict[str, Any]]:
    """Returns how well each check of Gentrex tells the values that are not right.

    `not_in_pages` of gentrex extract looks at the copied values that it
    wrote. `hpo_models_disagree` looks at the HPO term of each clinical
    feature that was found, `result_conflict` at the result of each report
    with a record, and `hgvs_invalid` at each variant that was found or
    added. A check that a run didn't make is left out.
    """
    found = {
        name: _check([(o.checks[name], o) for o in outcomes if name in o.checks])
        for name in compare.CHECKS
    }
    found["not_in_pages"] = _check(
        [(o.flagged, o) for o in outcomes if o.flagged is not None]
    )
    return {name: numbers for name, numbers in found.items() if numbers["values"]}


def _review(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Returns how many reports a person would check, and how many wrong ones.

    A report is checked if any check of Gentrex flagged one of its values. It
    is wrong if it doesn't count as correct.
    """
    wrong = {name for name, summary in summaries.items() if not summary["correct"]}
    names = sorted(
        {flag for summary in summaries.values() for flag in summary["flags"]}
    )
    found = {}
    for name in [*names, "any"]:
        flagged = {
            report
            for report, summary in summaries.items()
            if (summary["flags"] if name == "any" else name in summary["flags"])
        }
        unflagged = len(summaries) - len(flagged)
        unflagged_wrong = len(wrong) - len(flagged & wrong)
        found[name] = {
            "flagged": len(flagged),
            "flagged_and_wrong": len(flagged & wrong),
            "precision": _ratio(len(flagged & wrong), len(flagged)),
            "recall": _ratio(len(flagged & wrong), len(wrong)),
            "unflagged_accuracy": _ratio(unflagged - unflagged_wrong, unflagged),
        }
    return {"reports": len(summaries), "wrong": len(wrong), "checks": found}


def _category_macro_f1(matrix: dict[str, dict[str, int]]) -> float | None:
    """Returns unweighted macro-F1 across non-empty classes of a confusion matrix."""
    classes = sorted(
        (set(matrix) | {pred for row in matrix.values() for pred in row}) - {"none"}
    )
    if not classes:
        return None
    f1s = []
    for cls in classes:
        tp = matrix.get(cls, {}).get(cls, 0)
        fn = sum(count for pred, count in matrix.get(cls, {}).items() if pred != cls)
        fp = sum(row.get(cls, 0) for truth, row in matrix.items() if truth != cls)
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return round(sum(f1s) / len(f1s), 4)


def _actionable_acmg_f1(matrix: dict[str, dict[str, int]]) -> float | None:
    """Returns binary F1 separating P/LP from other variant classifications."""
    tp = fp = fn = 0
    for truth, row in matrix.items():
        truth_pos = truth in _PATHOGENIC
        for pred, count in row.items():
            pred_pos = pred in _PATHOGENIC
            if truth_pos and pred_pos:
                tp += count
            elif not truth_pos and pred_pos:
                fp += count
            elif truth_pos and not pred_pos:
                fn += count
    if not (tp + fp + fn):
        return None
    denom = 2 * tp + fp + fn
    return round(2 * tp / denom, 4) if denom else 0.0


def _safety(
    truths: dict[str, dict[str, Any]],
    chosen: list[str],
    summaries: dict[str, dict[str, Any]],
    outcomes: list[compare.Outcome],
    confusions: dict[str, dict[str, dict[str, int]]],
) -> dict[str, Any]:
    """Returns clinical safety, grounding, and category macro-F1 metrics."""
    negatives = [name for name in chosen if not truths[name]["record"]["variants"]]
    neg_right = sum(summaries[name]["correct"] for name in negatives)
    fp_variants = sum(summaries[name]["variants"]["extra"] > 0 for name in negatives)
    pathogenic = [o for o in outcomes if o.field == "variants" and o.pathogenic is True]
    pathogenic_found = sum(o.result == "correct" for o in pathogenic)
    pathogenic_clinical = sum(
        o.result == "correct" and o.clinical_ok is True for o in pathogenic
    )
    written = sum(
        s["values"]["right"] + s["values"]["extra"] for s in summaries.values()
    )
    hallucinations = sum(
        _is_extracted(o)
        and o.result in ("wrong", "extra")
        and o.cause in ("not_in_pages", "hallucination")
        for o in outcomes
    )
    distractor_entities = sum(
        o.field in compare.ENTITIES and o.result == "extra" and o.cause == "distractor"
        for o in outcomes
    )
    return {
        "pathogenic_variants": len(pathogenic),
        "pathogenic_variant_recall": _ratio(pathogenic_found, len(pathogenic)),
        "pathogenic_clinical_recall": _ratio(pathogenic_clinical, len(pathogenic)),
        "actionable_acmg_f1": _actionable_acmg_f1(
            confusions.get("variants.classification", {})
        ),
        "negative_reports": len(negatives),
        "negative_specificity": _ratio(neg_right, len(negatives)),
        "false_positive_variant_rate": _ratio(fp_variants, len(negatives)),
        "written_values": written,
        "hallucinations": hallucinations,
        "hallucination_rate": _ratio(hallucinations, written),
        "distractor_entities": distractor_entities,
        "classification_macro_f1": _category_macro_f1(
            confusions.get("variants.classification", {})
        ),
        "result_macro_f1": _category_macro_f1(
            confusions.get("normalized.overall_result", {})
        ),
    }


def _clinical_errors(outcomes: list[compare.Outcome]) -> dict[str, int]:
    """Returns counts of clinical errors by clinical severity category."""
    counts = {
        "missed_pathogenic_variant": 0,
        "missed_other_variant": 0,
        "extra_variant": 0,
        "actionable_acmg_flip": 0,
        "other_acmg_error": 0,
        "wrong_zygosity_or_cn": 0,
        "wrong_result_or_karyotype": 0,
    }
    for o in outcomes:
        if o.field not in compare.CLINICAL or o.result == "correct":
            continue
        if o.field == "variants":
            if o.result == "extra":
                counts["extra_variant"] += 1
            elif o.pathogenic:
                counts["missed_pathogenic_variant"] += 1
            else:
                counts["missed_other_variant"] += 1
        elif o.field == "variants.classification":
            if (o.truth in _PATHOGENIC) != (o.found in _PATHOGENIC):
                counts["actionable_acmg_flip"] += 1
            else:
                counts["other_acmg_error"] += 1
        elif o.field in ("variants.zygosity", "variants.copy_number"):
            counts["wrong_zygosity_or_cn"] += 1
        else:
            counts["wrong_result_or_karyotype"] += 1
    return counts


def _groups(
    truths: dict[str, dict[str, Any]],
    summaries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Returns the report accuracy of the reports of each lab, tag and so on."""
    members: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for name in summaries:
        case = truths[name].get("case", {})
        count = len(truths[name]["record"]["variants"])
        length = len(truths[name].get("pages") or [])
        labels = [
            ("lab", case.get("lab")),
            ("laboratory", case.get("laboratory")),
            ("kind", case.get("kind")),
            ("scenario", case.get("scenario")),
            ("variants", str(count) if count < 2 else "2 or more"),
            ("pages", (str(length) if length < 4 else "4 or more") if length else None),
            *(("challenge", name) for name in case.get("challenges", [])),
        ]
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


def _truths(truth_dir: pathlib.Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Returns the truth files of a folder by report, and their sorted names.

    Raises:
        ValueError: `truth_dir` has no truth files.
    """
    truths = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(truth_dir.glob("*.json"))
    }
    chosen = list(truths)
    if not chosen:
        raise ValueError(f"{truth_dir} has no truth files")
    return truths, chosen


def page_choice(
    truth_dir: pathlib.Path, decisions: pathlib.Path, threshold: float
) -> dict[str, Any]:
    """Returns how well a decisions.jsonl chose the pages.

    The numbers are those of `select` in the scores, for a decisions.jsonl
    that another way of choosing pages wrote (select_methods.py).
    """
    truths, chosen = _truths(truth_dir)
    return _select(truths, chosen, _read_jsonl(decisions), threshold)


def score(
    truth_dir: pathlib.Path,
    run_dir: pathlib.Path,
    gpus: list[int] | None = None,
    label: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Scores a run of gentrex normalize against a folder of truth files.

    A truth file's report is the PDF with the same name. A report that the
    run doesn't have counts as all missed.

    Args:
        truth_dir: Folder of truth files.
        run_dir: Run folder of gentrex normalize.
        gpus: The GPUs that the model servers of gentrex transcribe, select
            and extract ran on, for the GPU-hours.
        label: A name of the run's setup, such as the model it tried.

    Returns:
        The scores, and every value that is not right.

    Raises:
        ValueError: The run folder or the truth files don't fit.
    """
    runs = _runs(run_dir)
    if "normalize" not in runs or "transcribe" not in runs:
        raise ValueError(f"{run_dir} is not a run folder of gentrex normalize")
    truths, chosen = _truths(truth_dir)
    cases = {name: truth.get("case", {}) for name, truth in truths.items()}

    transcribe_dir = pathlib.Path(runs["transcribe"]["path"])
    select_dir = pathlib.Path(runs.get("select", runs["transcribe"])["path"])
    transcribed = _texts(transcribe_dir / "pages.jsonl")
    kept = _texts(select_dir / "pages.jsonl")
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
    field_counts = []
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
        field_counts.append(_report_field_counts(own))
        case = cases[name]
        summaries[name] = _summary(own) | {
            "case": {
                key: case.get(key) for key in ("lab", "kind", "scenario", "challenges")
            }
        }
        for outcome in own:
            if outcome.result != "correct":
                error = {"report": name, **dataclasses.asdict(outcome)}
                del error["strict"]
                del error["clinical_ok"]
                del error["pathogenic"]
                errors.append(error)

    performance = _performance(runs, len(transcribed), gpus)
    extractions = pathlib.Path(runs["extract"]["path"]) / "extractions.jsonl"
    seconds = [
        record["seconds"]
        for record in (_read_jsonl(extractions) if extractions.is_file() else [])
        if record.get("seconds") is not None
        and pathlib.Path(record["file"]).stem in summaries
    ]
    # How long gentrex extract took for one report, if the run recorded it.
    performance["extract_seconds_per_report"] = (
        {
            "median": round(statistics.median(seconds), 2),
            "p90": round(float(np.percentile(seconds, 90)), 2),
            "most": round(max(seconds), 2),
        }
        if seconds
        else None
    )
    manifest = truth_dir.parent / "manifest.json"
    confusions = _confusions(outcomes, _categories(schema))
    value_pages = _value_pages(truths, chosen)
    scores = {
        "format": FORMAT,
        "truth": str(truth_dir.resolve()),
        "benchmark": (
            json.loads(manifest.read_text(encoding="utf-8"))
            if manifest.is_file()
            else None
        ),
        "label": label,
        "pdfs": runs["transcribe"]["input"],
        "reports": len(chosen),
        "without_record": sum(
            not (reports.get(name) or {}).get("data") for name in chosen
        ),
        "data": _data(truths, chosen),
        "main": _main_numbers(list(summaries.values()), field_counts),
        "safety": _safety(truths, chosen, summaries, outcomes, confusions),
        "clinical_errors": _clinical_errors(outcomes),
        "entities": _entities(outcomes),
        "variant_kinds": _variant_kinds(outcomes),
        "fields": _fields(outcomes),
        "confusions": confusions,
        "funnel": _funnel(outcomes),
        "charges": _charges(outcomes),
        "pages": _pages(
            truths,
            chosen,
            _read_jsonl(transcribe_dir / "pages.jsonl"),
            _read_jsonl(select_dir / "pages.jsonl") if "select" in runs else None,
            value_pages,
        ),
        "select": (
            _select(
                truths,
                chosen,
                _read_jsonl(select_dir / "decisions.jsonl"),
                runs["select"]["settings"]["keep_threshold"],
                value_pages,
            )
            if "select" in runs and (select_dir / "decisions.jsonl").is_file()
            else None
        ),
        "normalize": _normalize(outcomes),
        "hpo": _hpo(outcomes),
        "checks": _checks(outcomes),
        "review": _review(summaries),
        "groups": _groups(truths, summaries),
        "performance": performance,
        "runs": runs,
        "by_report": summaries,
    }
    return scores, errors


def setup(scores: dict[str, Any]) -> str:
    """Returns the setup of a scored run, as "scan, no select, Qwen".

    That is the copy of the reports that it read, whether it skipped
    gentrex select, and its label.
    """
    parts = [pathlib.Path(scores["pdfs"]).name]
    if "select" not in scores["runs"]:
        parts.append("no select")
    if scores.get("label"):
        parts.append(scores["label"])
    return ", ".join(parts)


def list_runs(folder: pathlib.Path = _RESULTS_DIR) -> list[str]:
    """Returns one line per scored run in a folder, oldest first."""
    lines = []
    for path in sorted(folder.glob("*/scores.json")):
        scores = json.loads(path.read_text(encoding="utf-8"))
        main = scores["main"]
        value_f1 = main.get("value_f1", {}).get("value")
        lines.append(
            f"{path.parent.name}  {setup(scores):<24}"
            f"  {scores['reports']:>4} reports"
            f"  report accuracy {percent(main['report_accuracy']['value']):>6}"
            f"  value F1 {percent(value_f1):>6}"
        )
    return lines


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _table(header: list[str], rows: list[list[Any]]) -> str:
    lines = [header, ["---"] * len(header), *rows]
    return "\n".join("| " + " | ".join(map(str, line)) + " |" for line in lines)


_MAIN_LABELS = {
    "report_accuracy": "Report accuracy",
    "record_accuracy": "Reports with every value right",
    "patient_match": "MRN and date of birth both right",
    "value_f1": "Value F1 (micro)",
    "macro_field_f1": "Field F1 (macro)",
    "strict_value_f1": "Exact-match value F1",
    "value_precision": "Value precision",
    "value_recall": "Value recall",
    "variant_f1": "Variant detection F1",
    "clinical_variant_f1": "Clinical variant F1",
    "variant_precision": "Variant precision",
    "variant_recall": "Variant recall",
}
_ENTITY_LABELS = {
    "variants": "Variants",
    "patient_phenotypes": "Clinical features, by text",
    "normalized.patient_phenotypes": "Clinical features, by HPO ID",
}


def _pages_text(scores: dict[str, Any]) -> str:
    """Returns what became of the pages and of the stated values, as sentences."""
    pages, funnel = scores["pages"], scores["funnel"]
    lost = ", ".join(
        f"{count} in `gentrex {command}`" for command, count in funnel["lost"].items()
    )
    text = [
        f"The run read {pages['total']} pages and sent {pages['ocr']} of them to OCR."
    ]
    if pages["ocr_word_recall"] is not None:
        text.append(
            f"OCR wrote {percent(pages['ocr_word_recall'])} of the words of those"
            f" pages, and {percent(pages['ocr_word_precision'])} of its words are"
            " on the pages."
        )
    if pages["kept"] is not None:
        text.append(f"`gentrex select` kept {pages['kept']} pages.")
    text.append(
        f"The reports state {funnel['stated']} values, and {funnel['right']} of"
        f" them are right in the records. Lost were {lost}. The records hold"
        f" {funnel['extra']} values that no report states."
    )
    return " ".join(text)


def _select_methods_text(scores: dict[str, Any]) -> list[str]:
    """Returns the table of the ways to choose pages, if the run compared them."""
    compared = scores.get("select_methods")
    if not compared:
        return []
    rows = []
    for name, m in compared["methods"].items():
        needed = m["needed_kept"] + m["needed_dropped"]
        rows.append(
            [
                f"`{name}`",
                percent(_ratio(m["needed_kept"], needed)),
                percent(_ratio(m["needed_kept"] + m["other_kept"], m["pages"])),
                m["seconds"],
                m["requests"],
                m["prompt_tokens"],
                m["completion_tokens"],
            ]
        )
    header = ["Way to choose pages", "Needed pages kept", "Pages kept", "Seconds"]
    return [
        f"The ways to choose pages, each on `{compared['model']}`:",
        _table([*header, "Requests", "Tokens in", "Tokens out"], rows),
    ]


def markdown(scores: dict[str, Any]) -> str:
    """Returns the scores as tables."""
    performance = scores["performance"]
    models = {
        name: (run["settings"].get("ocr") or run["settings"]).get("model")
        for name, run in scores["runs"].items()
    }
    review = scores["review"]
    every = review["checks"]["any"]
    checked = [
        "## Checks",
        "The checks of Gentrex flag values for a person to look at. Precision is"
        " the share of the flagged values that are wrong, and recall the share of"
        " the wrong values that are flagged.",
        _table(
            ["Check", "Values", "Flagged", "Wrong", "Precision", "Recall"],
            [
                [
                    f"`{name}`",
                    c["values"],
                    c["flagged"],
                    c["not_right"],
                    percent(c["precision"]),
                    percent(c["recall"]),
                ]
                for name, c in scores["checks"].items()
            ],
        ),
        f"A person who looks at every report with a flag looks at {every['flagged']}"
        f" of {review['reports']} reports, and finds"
        f" {every['flagged_and_wrong']} of the {review['wrong']} reports that"
        " count as wrong.",
    ]
    parts = [
        "# Scores",
        f"{scores['reports']} reports, read from"
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
        "## Clinical safety and grounding",
        _table(
            ["Measure", "Value"],
            [
                [
                    "Pathogenic / likely pathogenic variant recall",
                    percent(scores["safety"].get("pathogenic_variant_recall")),
                ],
                [
                    "Pathogenic / likely pathogenic clinical recall",
                    percent(scores["safety"].get("pathogenic_clinical_recall")),
                ],
                [
                    "Actionable ACMG F1 (P/LP vs. other)",
                    percent(scores["safety"].get("actionable_acmg_f1")),
                ],
                [
                    "Negative-report specificity",
                    percent(scores["safety"]["negative_specificity"]),
                ],
                [
                    "False-positive variant rate on negative reports",
                    percent(scores["safety"]["false_positive_variant_rate"]),
                ],
                [
                    "Ungrounded hallucination rate",
                    percent(scores["safety"]["hallucination_rate"]),
                ],
                [
                    "Distractor entities copied",
                    scores["safety"]["distractor_entities"],
                ],
                [
                    "ACMG classification macro-F1",
                    percent(scores["safety"]["classification_macro_f1"]),
                ],
                [
                    "Overall result macro-F1",
                    percent(scores["safety"]["result_macro_f1"]),
                ],
            ],
        ),
        _table(
            ["Clinical error type", "Count"],
            [
                [name.replace("_", " "), count]
                for name, count in (scores.get("clinical_errors") or {}).items()
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
        "## Pages",
        _pages_text(scores),
        *_select_methods_text(scores),
        "## Fields",
        _table(
            ["Field", "Values", "Accuracy", "F1", "Exact", "Missed", "Extra", "Wrong"],
            [
                [
                    f"`{name}`",
                    f["values"],
                    percent(f["accuracy"]),
                    percent(f["f1"]),
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
    starts = [c.get("server_start_seconds") for c in performance["commands"].values()]
    if any(starts):
        parts.append(
            f"The model servers took {sum(filter(None, starts)):.0f} seconds more to"
            " start, which these numbers leave out."
        )
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
        "--gpus",
        type=int,
        nargs=3,
        metavar="N",
        help="GPUs that the model servers of gentrex transcribe, select and"
        " extract ran on, for the GPU-hours.",
    )
    parser.add_argument(
        "--label",
        help="A name of the run's setup, such as the model it tried. Runs with"
        " the same copy and label are compared as one setup.",
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
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the scored runs in results/gentrex-bench instead.",
    )
    add_arguments(parser)
    args = parser.parse_args()
    if args.list:
        print("\n".join(list_runs()))
        return 0
    try:
        scores, errors = score(args.truth, args.run, args.gpus, args.label)
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
