"""Compares ways to map phenotype mentions to HPO terms, on the GSC+ corpus.

GSC+ is a set of 228 PubMed abstracts in which experts marked each phenotype
mention and the HPO term it names. Each setup ranks the HPO terms for every
distinct mention. The script counts how often the experts' term comes first,
and how often it is among the first 5 or 10. evaluation/README.md explains
the setups and how to run the script.
"""

# The hpo extra and the evaluation group provide torch, scipy and
# sentence-transformers.
# pyright: reportMissingImports=false

import argparse
import collections
import datetime
import hashlib
import importlib.metadata
import json
import math
import pathlib
import platform
import re
import tempfile
import time
from typing import Any

import numpy as np
import torch
from scipy import stats

from gentrex import config
from gentrex.normalize import phenotypes

_DEPTH = 50  # Terms each setup ranks per mention.
_HPO_ID = re.compile(r"(?:http://purl\.obolibrary\.org/obo/HP_|HP:)(\d{7})")


def _hpo_id(value: str) -> str | None:
    match = _HPO_ID.fullmatch(value.strip())
    return f"HP:{match[1]}" if match else None


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _label(model: dict[str, str]) -> str:
    prompt = model.get("prompt")
    return f"{model['name']} (prompt {prompt})" if prompt else model["name"]


def _replacements(graph: dict[str, Any]) -> dict[str, str]:
    """Maps alternative and obsolete HPO IDs to the IDs that replace them."""
    replaced_by = {}
    for node in graph["nodes"]:
        term = _hpo_id(node["id"])
        for prop in node.get("meta", {}).get("basicPropertyValues", []):
            target = _hpo_id(prop.get("val", ""))
            if not term or not target:
                continue
            if prop["pred"].endswith("hasAlternativeId"):
                replaced_by[target] = term
            elif prop["pred"].endswith("IAO_0100001"):  # "term replaced by"
                replaced_by[term] = target
    return replaced_by


def _current(
    term: str | None, current: set[str], replaced_by: dict[str, str]
) -> str | None:
    """Returns the current ID of `term`, or None if HPO dropped it."""
    for _ in range(5):  # Replacement chains are short.
        if term is None or term in current:
            return term
        term = replaced_by.get(term)
    return None


def _load_gold(
    corpus: pathlib.Path, current: set[str], replaced_by: dict[str, str]
) -> tuple[list[tuple[str, set[str]]], collections.Counter[str]]:
    """Returns each distinct mention with the experts' terms, and counts.

    Mentions that differ only in case or spacing count as one, with every
    term the experts gave them.
    """
    gold: dict[str, set[str]] = collections.defaultdict(set)
    spelling: dict[str, str] = {}
    counts: collections.Counter[str] = collections.Counter()
    for path in sorted(corpus.glob("GSCplus_*_gold.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            if len(fields) < 4:
                continue  # A PubMed ID or abstract line.
            counts["annotations"] += 1
            original = _hpo_id(fields[3])
            term = _current(original, current, replaced_by)
            if term is None:
                counts["annotations without a current HPO term"] += 1
                continue
            counts["annotations mapped to a newer HPO ID"] += term != original
            gold[_norm(fields[2])].add(term)
            spelling.setdefault(_norm(fields[2]), fields[2].strip())
    return [(spelling[key], gold[key]) for key in sorted(gold)], counts


class _Bm25:
    """Okapi BM25 over names, with lowercased words and numbers as tokens."""

    def __init__(self, names: list[str], k1: float = 1.2, b: float = 0.75) -> None:
        tokens = [self._tokens(name) for name in names]
        lengths = np.array([len(words) for words in tokens], dtype=np.float32)
        self._norm = k1 * (1 - b + b * lengths / lengths.mean())
        self._k1 = k1
        postings = collections.defaultdict(lambda: ([], []))
        for row, words in enumerate(tokens):
            for word, count in collections.Counter(words).items():
                postings[word][0].append(row)
                postings[word][1].append(count)
        self._postings = {
            word: (np.array(rows), np.array(counts, dtype=np.float32))
            for word, (rows, counts) in postings.items()
        }
        self._size = len(names)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def scores(self, text: str) -> np.ndarray:
        scores = np.zeros(self._size, dtype=np.float32)
        for word in set(self._tokens(text)):
            if word not in self._postings:
                continue
            rows, counts = self._postings[word]
            idf = math.log(1 + (self._size - len(rows) + 0.5) / (len(rows) + 0.5))
            tf = counts * (self._k1 + 1) / (counts + self._norm[rows])
            scores[rows] += idf * tf
        return scores


def _rankings(scores: np.ndarray, terms: list[str]) -> list[list[str]]:
    """Returns the _DEPTH best terms for each row of term scores, best first."""
    return [[terms[i] for i in np.argsort(-row)[:_DEPTH]] for row in scores]


def _mcnemar(hits: np.ndarray, baseline_hits: np.ndarray) -> float:
    """Returns the two-sided p-value of an exact McNemar test."""
    only_here = int((hits & ~baseline_hits).sum())
    only_baseline = int((baseline_hits & ~hits).sum())
    if only_here + only_baseline == 0:
        return 1.0
    return float(stats.binomtest(only_here, only_here + only_baseline).pvalue)


def _percent(hits: np.ndarray) -> float:
    return round(100 * float(hits.mean()), 1)


def _write_markdown(path: pathlib.Path, results: dict[str, Any]) -> None:
    run, baseline = results["run"], results["run"]["baseline"]
    lines = [
        "# HPO matching on GSC+",
        "",
        f"Written by `evaluation/hpo_normalization.py` on {run['date']}, on"
        f" {run['machine']}. The test set has {run['mentions']} distinct"
        f" mentions, {run['worded_differently']} of them worded differently"
        " from every HPO name. Each p-value is an exact McNemar test against"
        f" `{baseline}`, the setup that settings.yaml names.",
        "",
        "| Setup | Top 1 | Top 1, different wording | Top 5"
        " | Top 5, different wording | Top 10 | p, top 1 | p, top 5 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for setup, row in sorted(
        results["setups"].items(), key=lambda item: -item[1]["top1"]
    ):
        lines.append(
            f"| {setup} | {row['top1']} | {row['top1_different']} | {row['top5']}"
            f" | {row['top5_different']} | {row['top10']} | {row['p_top1']:.2g}"
            f" | {row['p_top5']:.2g} |"
        )
    agreement = results["agreement"]
    lines += [
        "",
        "## When the two models agree",
        "",
        f"The models of `{baseline}` rank the same term first for"
        f" {agreement['agree']}% of the mentions. Then the match is right for"
        f" {agreement['top1_when_agree']}%. When they disagree, it is right for"
        f" {agreement['top1_when_disagree']}%. At least one model ranks the"
        f" experts' term first for {agreement['either_first']}%, and the two"
        f" models' first 5 terms hold it for {agreement['union_top5']}%, in"
        f" {agreement['union_top5_terms']} terms on average.",
        "",
        "## Speed on the CPU",
        "",
        "| Setup | Index build (minutes) | Per clinical feature (ms) |",
        "| --- | --- | --- |",
    ]
    for setup, row in results["speed"].items():
        build = row.get("index_build_minutes", "")
        lines.append(f"| {setup} | {build} | {row['ms_per_feature']} |")
    examples = results["examples"]
    lines += [
        "",
        f"## Top matches where {examples['other']} alone and {baseline} differ",
        "",
        f"| Mention | Experts' term | {examples['other']} alone | {baseline} |",
        "| --- | --- | --- | --- |",
    ]
    for row in examples["mentions"]:
        lines.append(
            f"| {row['mention']} | {', '.join(row['experts'])}"
            f" | {row['other']} | {row['baseline']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Runs every setup and writes evaluation_results/hpo_normalization.*."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release",
        type=pathlib.Path,
        default=pathlib.Path("data/ontology/hp-base.json"),
        help="HPO release in JSON, as stage 4, step 2 downloads it.",
    )
    parser.add_argument(
        "--corpus",
        type=pathlib.Path,
        default=pathlib.Path("data/evaluation/corpus/GSC"),
        help="Folder with GSCplus_dev_gold.tsv and GSCplus_test_gold.tsv.",
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=pathlib.Path("evaluation_results")
    )
    args = parser.parse_args()
    if not args.release.is_file():
        parser.error(f"{args.release} not found; see stage 4, step 2")
    if not list(args.corpus.glob("GSCplus_*_gold.tsv")):
        parser.error(f"no GSC+ files in {args.corpus}; see evaluation/README.md")
    started = time.perf_counter()
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    configured = config.load_settings()["normalize"]["hpo"]["models"]
    baseline = " + ".join(_label(model) for model in configured)
    graph = json.loads(args.release.read_text(encoding="utf-8"))["graphs"][0]
    setups: dict[str, list[list[str]]] = {}
    speed: dict[str, dict[str, float]] = {}

    # The models that settings.yaml names, through stage 4's own index and
    # search, on the CPU.
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "hpo.npz"
        for model in configured:
            phenotypes.load_encoder(model["name"])  # Downloads it before timing.
        start = time.perf_counter()
        phenotypes.build_index(args.release, path, configured)
        build_seconds = time.perf_counter() - start
        with np.load(path) as index:
            term_of = index["hpo_id"].tolist()
            label = dict(zip(term_of, index["label"].tolist(), strict=True))
            names = index["name"].tolist()
        starts = phenotypes.term_starts(term_of)
        terms = [term_of[row] for row in starts]
        gold, counts = _load_gold(args.corpus, set(term_of), _replacements(graph))
        mentions = [mention for mention, _ in gold]
        name_keys = {_norm(name) for name in names}
        exact = np.array([_norm(mention) in name_keys for mention in mentions])
        hpo = phenotypes.HpoIndex(path, configured, _DEPTH)
        start = time.perf_counter()
        matches = [hpo.map(mention) for mention in mentions]
        speed[baseline] = {
            "index_build_minutes": round(build_seconds / 60, 1),
            "ms_per_feature": round(
                1000 * (time.perf_counter() - start) / len(mentions), 1
            ),
        }
        del hpo
    setups[baseline] = [
        [term["hpo_id"] for term in match["candidates"]] for match in matches
    ]
    agree = np.array([bool(match["models_agree"]) for match in matches])
    print(f"ranked the mentions with {baseline}", flush=True)

    # Each model on its own, and a model with a prompt also without it, on the
    # fastest device, timed on the CPU.
    without_prompts = [
        {"name": model["name"]} for model in configured if "prompt" in model
    ]
    model_scores: dict[str, np.ndarray] = {}
    for model in [*configured, *without_prompts]:
        encoder = phenotypes.load_encoder(model["name"])
        prompt = model.get("prompt")
        phenotypes.embed(encoder, names[:32], prompt)
        start = time.perf_counter()
        phenotypes.embed(encoder, names[:2000], prompt)
        names_per_second = 2000 / (time.perf_counter() - start)
        start = time.perf_counter()
        for mention in mentions[:100]:
            phenotypes.embed(encoder, [mention], prompt)
        speed[_label(model)] = {
            "index_build_minutes": round(len(names) / names_per_second / 60, 1),
            "ms_per_feature": round(10 * (time.perf_counter() - start), 1),
        }
        encoder = encoder.to(device)
        similarities = (
            phenotypes.embed(encoder, mentions, prompt)
            @ phenotypes.embed(encoder, names, prompt).T
        )
        model_scores[_label(model)] = phenotypes.term_scores(similarities, starts)
        setups[_label(model)] = _rankings(model_scores[_label(model)], terms)
        print(f"ranked the mentions with {_label(model)}", flush=True)

    # Fusing the models' own scores must give stage 4's terms, apart from rare
    # ties that the CPU and the GPU break differently.
    fused = phenotypes.fuse([model_scores[_label(model)] for model in configured])
    differ = sum(
        a[:5] != b[:5]
        for a, b in zip(_rankings(fused, terms), setups[baseline], strict=True)
    )
    print(f"{differ} mentions where the fused rankings differ from stage 4's")

    # BM25 scores each name by the words it shares with the mention, and its
    # z-scores are added as a further model's. A mention that shares no word
    # with any name adds nothing.
    bm25 = _Bm25(names)
    by_words = phenotypes.term_scores(
        np.array([bm25.scores(mention) for mention in mentions]), starts
    )
    spread = by_words.std(axis=1, keepdims=True)
    centered = by_words - by_words.mean(axis=1, keepdims=True)
    bm25_z = np.divide(centered, spread, out=np.zeros_like(centered), where=spread > 0)
    setups[f"{baseline} + BM25"] = _rankings(fused + bm25_z, terms)
    print(f"ranked the mentions with {baseline} + BM25", flush=True)
    own = [setups[_label(model)] for model in configured]

    def hits(setup: str, n: int) -> np.ndarray:
        return np.array(
            [
                bool(set(ranking[:n]) & terms)
                for ranking, (_, terms) in zip(setups[setup], gold, strict=True)
            ]
        )

    baseline_hits = {n: hits(baseline, n) for n in (1, 5)}
    table = {}
    for setup in setups:
        top1, top5, top10 = hits(setup, 1), hits(setup, 5), hits(setup, 10)
        table[setup] = {
            "top1": _percent(top1),
            "top1_different": _percent(top1[~exact]),
            "top5": _percent(top5),
            "top5_different": _percent(top5[~exact]),
            "top10": _percent(top10),
            "p_top1": _mcnemar(top1, baseline_hits[1]),
            "p_top5": _mcnemar(top5, baseline_hits[5]),
        }
    firsts = [hits(_label(model), 1) for model in configured]
    union = [
        set().union(*(ranking[:5] for ranking in rankings))
        for rankings in zip(*own, strict=True)
    ]
    agreement = {
        "agree": _percent(agree),
        "top1_when_agree": _percent(baseline_hits[1][agree]),
        "top1_when_disagree": _percent(baseline_hits[1][~agree]),
        "either_first": _percent(np.any(firsts, axis=0)),
        "union_top5": _percent(
            np.array(
                [bool(u & terms) for u, (_, terms) in zip(union, gold, strict=True)]
            )
        ),
        "union_top5_terms": round(float(np.mean([len(u) for u in union])), 1),
    }
    other = _label(configured[0])
    examples = []
    for i, (mention, terms) in enumerate(gold):
        first = setups[other][i][0], setups[baseline][i][0]
        if (first[0] in terms) != (first[1] in terms) and len(examples) < 16:
            examples.append(
                {
                    "mention": mention,
                    "experts": [f"{term} {label[term]}" for term in sorted(terms)],
                    "other": label[first[0]],
                    "baseline": label[first[1]],
                }
            )
    corpus_files = sorted(args.corpus.glob("GSCplus_*_gold.tsv"))
    results = {
        "run": {
            "date": datetime.date.today().isoformat(),
            "machine": f"{platform.platform()}, {device}",
            "minutes": round((time.perf_counter() - started) / 60),
            "packages": {
                package: importlib.metadata.version(package)
                for package in ("torch", "transformers", "sentence-transformers")
            },
            "hpo_release": graph.get("meta", {}).get("version"),
            "corpus_sha256": hashlib.sha256(
                b"".join(path.read_bytes() for path in corpus_files)
            ).hexdigest(),
            **counts,
            "mentions": len(mentions),
            "worded_differently": int((~exact).sum()),
            "baseline": baseline,
            "fused_rankings_differing_from_stage_4": differ,
        },
        "setups": table,
        "agreement": agreement,
        "speed": speed,
        "examples": {"other": other, "mentions": examples},
    }
    args.output.mkdir(exist_ok=True)
    (args.output / "hpo_normalization.json").write_text(
        json.dumps(results, indent=1) + "\n", encoding="utf-8"
    )
    _write_markdown(args.output / "hpo_normalization.md", results)
    print(f"wrote {args.output}/hpo_normalization.json and .md", flush=True)


if __name__ == "__main__":
    main()
