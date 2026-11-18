"""Generate synthetic genetic test reports with a known truth.

    uv run python gentrex-bench/generator/generate.py sample
    uv run --env-file .env python gentrex-bench/generator/generate.py build

`sample` writes the cases. `build` has a model on the OpenAI-compatible
server that GENTREX_BENCH_BASE_URL names write the free text of each report,
fills the report's template, prints it and checks it, and makes the scanned
copies. `recheck` samples the cases again after a fix to the sampler and
renews the truth of the reports that are already printed. All take their
settings from settings.yaml, next to this file.
docs/development/generate-benchmark-reports.md explains them.
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import pathlib
import subprocess
import sys
import threading
from concurrent import futures
from typing import Any

import check
import fill
import labs
import render
import sample
import scan
import sources
import write
import yaml

from gentrex import llm

_logger = logging.getLogger("synthetic")
_BASE_URL_ENV = "GENTREX_BENCH_BASE_URL"
_API_KEY_ENV = "GENTREX_BENCH_API_KEY"
_SETTINGS_PATH = pathlib.Path(__file__).with_name("settings.yaml")
_SOURCES = ("clinvar", "hpo", "hpoa", "mondo", "hgnc")
# Reports are built eight at a time, and each attempt adds a line to one file.
_ATTEMPTS_LOCK = threading.Lock()


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source() -> dict[str, Any]:
    """Returns the commit of the generator and whether its files differ from it.

    Empty if the generator doesn't run from a git clone.
    """
    folder = pathlib.Path(__file__).resolve().parent

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(folder), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    try:
        changed = git("status", "--porcelain", "--untracked-files=no", "--", ".")
        return {"commit": git("rev-parse", "HEAD"), "modified": bool(changed)}
    except (OSError, subprocess.CalledProcessError):
        return {}


def _log_attempt(out: pathlib.Path, line: dict[str, Any]) -> None:
    """Adds one attempt at a report to attempts.jsonl in the version folder."""
    with _ATTEMPTS_LOCK, (out / "attempts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def _write_json(path: pathlib.Path, value) -> None:
    """Writes a JSON file whole or not at all, so that a stopped build leaves no
    half-written truth file for the next one to skip."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    part.replace(path)


def _sampled(settings: dict[str, Any]) -> tuple[list[dict], dict[str, Any]] | None:
    """Samples the cases from the reference files.

    Returns:
        The cases and what the manifest records about their sources, or None
        if a reference file is missing.
    """
    paths = {name: pathlib.Path(settings[name]) for name in _SOURCES}
    for name, path in paths.items():
        if not path.is_file():
            _logger.error("%s not found (sample.%s in settings.yaml)", path, name)
            return None
    genes = {g for area in labs.AREAS for g in area.genes}
    genes |= set(labs.CARRIER_GENES) | set(labs.MITO_GENES) | set(labs.SECONDARY_GENES)
    _logger.info("reading HPO, MONDO and HGNC")
    terms = sources.load_terms(paths["hpo"])
    mondo = sources.load_mondo_labels(paths["mondo"])
    annotations = sources.load_annotations(paths["hpoa"], terms)
    _logger.info("reading ClinVar, which takes about half a minute")
    variants, regions = sources.load_clinvar(
        paths["clinvar"], genes, mondo, annotations
    )
    missing = sorted(genes - set(variants))
    if missing:
        _logger.info("no usable ClinVar variants for %s", ", ".join(missing))
    refs = sources.References(
        variants,
        terms,
        sources.load_previous_symbols(paths["hgnc"]),
        regions,
        sources.load_syndromes(paths["mondo"], paths["hpoa"], terms, sample.SYNDROMES),
    )
    cases = sample.sample(refs, settings["seed"], settings["dev"], settings["test"])
    return cases, {
        "sources": {
            name: {"file": path.name, "sha256": _sha256(path)}
            for name, path in paths.items()
        },
        "usable_variants": sum(len(v) for v in variants.values()),
        "usable_copy_number_changes": len(regions),
    }


def _sample(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    out = args.out / args.version
    if (out / "cases").exists():
        _logger.error("%s already has cases; choose another --version", out)
        return 1
    sampled = _sampled(settings)
    if sampled is None:
        return 1
    cases, sources_used = sampled
    for case in cases:
        _write_json(
            out / "cases" / f"{case['case_id']}.json", {"canary": fill.CANARY, **case}
        )
    _write_json(
        out / "manifest.json",
        {
            "canary": fill.CANARY,
            "version": args.version,
            "generator": sample._VERSION,
            "sampled": {
                "date": datetime.datetime.now().isoformat(timespec="seconds"),
                **_source(),
            },
            "settings": settings,
            **sources_used,
        },
    )
    _logger.info("wrote %d cases to %s", len(cases), out / "cases")
    return 0


def _recheck(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    """Samples the cases again and renews the truth of the printed reports.

    After a fix to the sampler that changes no printed value, the reports
    stay and only their truth changes. A report whose PDF doesn't print its
    new case keeps its old case and truth, and is named in the log.
    """
    out = args.out / args.version
    sampled = _sampled(settings)
    if sampled is None:
        return 1
    renewed, failed = [], []
    for case in sampled[0]:
        case_id = case["case_id"]
        truth_path = out / "truth" / f"{case_id}.json"
        if truth_path.exists():
            old = json.loads(truth_path.read_text(encoding="utf-8"))
            native = out / "pdf" / "native" / f"{case_id}.pdf"
            result = check.check(case, native, old["case"]["writer"])
            if result.truth is None:
                for error in result.errors:
                    _logger.warning("%s: %s", case_id, error)
                failed.append(case_id)
                continue
            for name in ("mixed_scanned_pages", "image_document_code"):
                result.truth["case"][name] = old["case"][name]
            truth = {"canary": fill.CANARY, **result.truth}
            if truth != old:
                _write_json(truth_path, truth)
                renewed.append(case_id)
        _write_json(out / "cases" / f"{case_id}.json", {"canary": fill.CANARY, **case})
    _logger.info(
        "renewed the truth of %d reports; reports that don't print their new case: %s",
        len(renewed),
        ", ".join(failed) or "none",
    )
    return 1 if failed else 0


def _build_one(
    case: dict,
    out: pathlib.Path,
    settings: dict[str, Any],
    client,
    chrome: str,
    chrome_version: str,
) -> bool:
    """Writes, fills, prints and checks one report until it passes, then scans it.

    An attempt that raises fails like one that doesn't pass the check, so one
    report's error doesn't end the build. Only an error that every request
    would get is raised.
    """
    case_id = case["case_id"]
    for attempt in range(1, settings["attempts"] + 1):
        try:
            if _attempt(case, out, settings, client, chrome, chrome_version, attempt):
                return True
        except llm.FATAL_ERRORS:
            raise
        except Exception as exc:
            _logger.warning("%s, attempt %d: %r", case_id, attempt, exc)
            _log_attempt(
                out,
                {
                    "case": case_id,
                    "attempt": attempt,
                    "passed": False,
                    "errors": [repr(exc)],
                },
            )
    _logger.error("%s failed all %d attempts", case_id, settings["attempts"])
    return False


def _attempt(
    case: dict,
    out: pathlib.Path,
    settings: dict[str, Any],
    client,
    chrome: str,
    chrome_version: str,
    attempt: int,
) -> bool:
    """Makes one attempt at a report and returns whether it passed the check."""
    case_id = case["case_id"]
    native = out / "pdf" / "native" / f"{case_id}.pdf"
    response = write.write(client, case, settings["model"], settings["max_tokens"])
    _write_json(
        out / "responses" / f"{case_id}-{attempt}.json",
        {"canary": fill.CANARY, **response},
    )
    html = out / "html" / f"{case_id}.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text(fill.fill(case, response["prose"]), encoding="utf-8")
    native.parent.mkdir(parents=True, exist_ok=True)
    render.print_pdf(chrome, html, native)
    writer = {k: response[k] for k in ("model", "prompt_sha256", "date")}
    writer["max_tokens"] = settings["max_tokens"]
    writer["output_tokens"] = response["output_tokens"]
    writer["attempt"] = attempt
    writer["chrome"] = chrome_version
    writer["generator"] = settings.get("source") or {}
    result = check.check(case, native, writer)
    for warning in result.warnings:
        _logger.info("%s: %s", case_id, warning)
    _log_attempt(
        out,
        {
            "case": case_id,
            "attempt": attempt,
            "passed": result.truth is not None,
            "errors": result.errors,
            "warnings": result.warnings,
            "output_tokens": response["output_tokens"],
        },
    )
    if result.truth is None:
        for error in result.errors:
            _logger.warning("%s, attempt %d: %s", case_id, attempt, error)
        return False
    for level in scan.LEVELS:
        scan.copy(native, out / "pdf" / level / f"{case_id}.pdf", level, case_id)
    mixed = scan.mixed_pages(case_id, len(result.truth["pages"]))
    scan.copy(native, out / "pdf" / "mixed" / f"{case_id}.pdf", "scan", case_id, mixed)
    scan.image_copy(
        native,
        out / "pdf" / "image" / f"{case_id}.pdf",
        case_id,
        chrome,
        fill.CANARY,
    )
    result.truth["case"]["mixed_scanned_pages"] = mixed
    result.truth["case"]["image_document_code"] = scan.document_code(case_id)
    _write_json(
        out / "truth" / f"{case_id}.json", {"canary": fill.CANARY, **result.truth}
    )
    _logger.info(
        "%s passed on attempt %d (%d output tokens)",
        case_id,
        attempt,
        response["output_tokens"],
    )
    return True


def _build(args: argparse.Namespace, settings: dict[str, Any]) -> int:
    out = args.out / args.version
    paths = sorted((out / "cases").glob("*.json"))
    if args.cases:
        paths = [p for p in paths if p.stem in set(args.cases)]
    if not paths:
        _logger.error("no cases in %s; run sample first", out / "cases")
        return 1
    base_url = os.environ.get(_BASE_URL_ENV)
    if not base_url:
        _logger.error(
            "%s is not set (see docs/development/generate-benchmark-reports.md)",
            _BASE_URL_ENV,
        )
        return 2
    chrome = args.chrome or render.find_chrome()
    chrome_version = render.chrome_version(chrome)
    client = llm.make_client(
        base_url, os.environ.get(_API_KEY_ENV, "EMPTY"), settings["timeout_seconds"]
    )
    settings = {**settings, "source": _source()}
    todo = [p for p in paths if not (out / "truth" / p.name).exists()]
    failed = []
    with futures.ThreadPoolExecutor(settings["concurrency"]) as pool:
        jobs = {
            pool.submit(
                _build_one,
                json.loads(path.read_text(encoding="utf-8")),
                out,
                settings,
                client,
                chrome,
                chrome_version,
            ): path.stem
            for path in todo
        }
        for job in futures.as_completed(jobs):
            try:
                built = job.result()
            except llm.FATAL_ERRORS as exc:
                _logger.error("the model server refused the request: %s", exc)
                pool.shutdown(cancel_futures=True)
                return 2
            if not built:
                failed.append(jobs[job])
    done = len(list((out / "truth").glob("*.json")))
    _logger.info(
        "%d of %d cases have a truth file; failed: %s",
        done,
        len(list((out / "cases").glob("*.json"))),
        ", ".join(sorted(failed)) or "none",
    )
    return 1 if failed else 0


def main() -> int:
    """Runs the command named on the command line."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate synthetic genetic test reports."
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("data/gentrex-bench"),
        help="Folder of the generated versions.",
    )
    parser.add_argument(
        "--version", default="v1", help="Name of the version, a folder under --out."
    )
    commands = parser.add_subparsers(required=True)
    sampler = commands.add_parser("sample", help="Sample the cases.")
    sampler.set_defaults(func=_sample, section="sample")
    builder = commands.add_parser(
        "build", help="Write, fill, print, check and scan the reports."
    )
    builder.add_argument("cases", nargs="*", help="Case IDs; all cases by default.")
    builder.add_argument("--chrome", help="Chrome or Chromium executable.")
    builder.set_defaults(func=_build, section="build")
    rechecker = commands.add_parser(
        "recheck", help="Sample the cases again and renew the truth files."
    )
    rechecker.set_defaults(func=_recheck, section="sample")
    args = parser.parse_args()
    settings = yaml.safe_load(_SETTINGS_PATH.read_text(encoding="utf-8"))
    return args.func(args, settings[args.section])


if __name__ == "__main__":
    sys.exit(main())
