"""Measures how often gentrex normalize finds the MONDO disease of a disease name.

The test set comes from ClinVar's variant_summary file, which names the
conditions of each variant and gives most of them a MONDO ID. The script
looks up every distinct name as gentrex normalize does and counts how often
it gets ClinVar's ID. evaluation/mondo-matching.md explains how to run it.
"""

import argparse
import collections
import datetime
import gzip
import hashlib
import json
import pathlib
import re
from typing import Any

from gentrex import config
from gentrex.normalize import diseases

_MONDO_ID = re.compile(r"MONDO:(MONDO:\d+)")
_MONDO_CLASS = re.compile(r"http://purl\.obolibrary\.org/obo/MONDO_(\d+)")
# Names that say that the submitter gave no condition.
_NO_CONDITION = frozenset({"not provided", "not specified", "see cases"})
_OUTCOMES = ("same ID", "other ID", "ambiguous", "unmapped")
_EXAMPLES = 15


def _current_ids(release: pathlib.Path) -> set[str]:
    """Returns the IDs of the MONDO diseases that are not deprecated."""
    graph = json.loads(release.read_text(encoding="utf-8"))["graphs"][0]
    return {
        f"MONDO:{match[1]}"
        for node in graph["nodes"]
        if (match := _MONDO_CLASS.fullmatch(node["id"]))
        and not node.get("meta", {}).get("deprecated")
    }


def _names(clinvar: pathlib.Path) -> collections.Counter[tuple[str, str]]:
    """Returns each condition name with its MONDO ID, and the variants that have it.

    A variant has one row for each genome build, so only the rows of GRCh38
    are read. The conditions of a row are separated by "|" and ";", in the
    same order in the names and in the IDs.
    """
    found: collections.Counter[tuple[str, str]] = collections.Counter()
    with gzip.open(clinvar, "rt", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").lstrip("#").split("\t")
        ids, names, assembly = (
            header.index(column)
            for column in ("PhenotypeIDS", "PhenotypeList", "Assembly")
        )
        for line in fh:
            row = line.rstrip("\n").split("\t")
            if row[assembly] != "GRCh38":
                continue
            condition_ids = re.split(r"[|;]", row[ids])
            condition_names = re.split(r"[|;]", row[names])
            if len(condition_ids) != len(condition_names):
                continue
            for one_ids, name in zip(condition_ids, condition_names, strict=True):
                match = _MONDO_ID.search(one_ids)
                if match and name.casefold() not in _NO_CONDITION:
                    found[name, match[1]] += 1
    return found


def _shares(counts: collections.Counter[str]) -> dict[str, float]:
    total = counts.total()
    return {name: round(100 * counts[name] / total, 1) for name in counts}


def evaluate(clinvar: pathlib.Path, release: pathlib.Path) -> dict[str, Any]:
    """Looks up ClinVar's condition names in a MONDO release.

    Args:
        clinvar: ClinVar's variant_summary file.
        release: MONDO release in obographs JSON.

    Returns:
        The shares of names that got ClinVar's ID, another ID or none, among
        the distinct names and among the variants, with examples.
    """
    index = diseases.MondoIndex.from_release(release)
    current = _current_ids(release)
    names = _names(clinvar)
    outdated = sum(1 for _, mondo_id in names if mondo_id not in current)
    by_name: collections.Counter[str] = collections.Counter()
    by_variant: collections.Counter[str] = collections.Counter()
    how: collections.Counter[str] = collections.Counter()
    without: list[tuple[int, str, str]] = []
    other: list[tuple[int, str, str, str]] = []
    for (name, mondo_id), variants in names.items():
        if mondo_id not in current:
            continue
        match = index.normalize(name)
        if match["disease_id"] == mondo_id:
            outcome = "same ID"
            how[match["disease_status"] or ""] += 1
        elif match["disease_id"]:
            outcome = "other ID"
            other.append((variants, name, mondo_id, match["disease_id"]))
        else:
            outcome = match["disease_status"] or "unmapped"
            without.append((variants, name, mondo_id))
        by_name[outcome] += 1
        by_variant[outcome] += variants
    with clinvar.open("rb") as fh:
        clinvar_sha256 = hashlib.file_digest(fh, "sha256").hexdigest()
    return {
        "run": {
            "date": datetime.date.today().isoformat(),
            "clinvar": clinvar.name,
            "clinvar_sha256": clinvar_sha256,
            "mondo_version": index.version,
            "names": by_name.total(),
            "variants": by_variant.total(),
            "names_with_an_outdated_id": outdated,
        },
        "names": _shares(by_name),
        "variants": _shares(by_variant),
        "matched_by": _shares(how),
        "most_frequent_without_a_match": [
            {"name": name, "mondo_id": mondo_id, "variants": variants}
            for variants, name, mondo_id in sorted(without, reverse=True)[:_EXAMPLES]
        ],
        "most_frequent_with_another_id": [
            {"name": name, "clinvar": mondo_id, "gentrex": got, "variants": variants}
            for variants, name, mondo_id, got in sorted(other, reverse=True)[:_EXAMPLES]
        ],
    }


def _write_markdown(path: pathlib.Path, results: dict[str, Any]) -> None:
    run = results["run"]
    lines = [
        "# MONDO matching on ClinVar's condition names",
        "",
        f"Written by `evaluation/mondo_normalization.py` on {run['date']}, from"
        f" `{run['clinvar']}` and MONDO {run['mondo_version']}. The test set has"
        f" {run['names']:,} distinct condition names with a current MONDO ID, on"
        f" {run['variants']:,} variants. {run['names_with_an_outdated_id']} more"
        " names have an ID that MONDO no longer uses and are left out.",
        "",
        "| Outcome | Distinct names | Weighted by variants |",
        "| --- | --- | --- |",
    ]
    for outcome in _OUTCOMES:
        lines.append(
            f"| {outcome} | {results['names'].get(outcome, 0.0)}%"
            f" | {results['variants'].get(outcome, 0.0)}% |"
        )
    matched = results["matched_by"]
    lines += [
        "",
        f"Of the names that got ClinVar's ID, {matched.get('label', 0.0)}% are the"
        f" disease's MONDO label and {matched.get('synonym', 0.0)}% one of its"
        " exact synonyms.",
        "",
        "## Most frequent names without a match",
        "",
        "| Name | ClinVar's ID | Variants |",
        "| --- | --- | --- |",
    ]
    for row in results["most_frequent_without_a_match"]:
        lines.append(f"| {row['name']} | {row['mondo_id']} | {row['variants']:,} |")
    lines += [
        "",
        "## Most frequent names with another ID",
        "",
        "| Name | ClinVar's ID | Gentrex's ID | Variants |",
        "| --- | --- | --- | --- |",
    ]
    for row in results["most_frequent_with_another_id"]:
        lines.append(
            f"| {row['name']} | {row['clinvar']} | {row['gentrex']}"
            f" | {row['variants']:,} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Runs the test and writes evaluation_results/mondo_normalization.*."""
    settings = config.load_settings(pathlib.Path(__file__).with_name("settings.yaml"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clinvar",
        type=pathlib.Path,
        default=pathlib.Path(settings["normalize"]["clinvar_path"]),
        help="ClinVar's variant_summary file.",
    )
    parser.add_argument(
        "--release",
        type=pathlib.Path,
        default=pathlib.Path(settings["normalize"]["mondo_path"]),
        help="MONDO release in JSON.",
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=pathlib.Path("evaluation_results")
    )
    args = parser.parse_args()
    for path in (args.clinvar, args.release):
        if not path.is_file():
            parser.error(
                f"{path} not found; run evaluation/download_reference_files.sh"
            )
    results = evaluate(args.clinvar, args.release)
    (args.output / "mondo_normalization.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_markdown(args.output / "mondo_normalization.md", results)
    print(f"wrote {args.output}/mondo_normalization.json and .md")


if __name__ == "__main__":
    main()
