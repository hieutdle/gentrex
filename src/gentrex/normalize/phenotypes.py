"""Phenotypes to HPO terms, by comparing their embeddings with those of HPO names.

Each model in normalize.hpo.models scores the HPO terms by the cosine
similarity of their closest name, and stage 4 adds the models' scores as
z-scores.
"""

import json
import pathlib
import re
from collections.abc import Iterator
from typing import Any

import numpy as np

_HPO_CLASS = re.compile(r"http://purl\.obolibrary\.org/obo/HP_(\d+)")


def load_encoder(model: str) -> Any:
    """Loads the sentence-transformers model named `model`, on the CPU.

    Raises:
        ImportError: sentence-transformers or torchvision, from the hpo extra,
            is not installed.
    """
    import torch  # pyright: ignore[reportMissingImports]
    from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]

    return SentenceTransformer(
        model,
        device="cpu",
        # A model that also reads images and audio, such as EmbeddingGemma 2,
        # loads only its text part.
        config_kwargs={"vision_config": None, "audio_config": None},
        # EmbeddingGemma 2 loads in bfloat16, but its card advises float32 on
        # most CPUs.
        model_kwargs={"dtype": torch.float32},
    )


def embed(encoder: Any, texts: list[str], prompt: str | None) -> np.ndarray:
    """Returns unit-length embeddings of `texts`, lowercased.

    Lowercasing makes "Ataxia" and "ataxia" the same text for models that tell
    case apart. At unit length, a dot product is a cosine similarity.

    Args:
        encoder: A model from load_encoder.
        texts: The texts to embed.
        prompt: Name of the model's prompt to put before each text, or None.
    """
    vectors = encoder.encode([text.lower() for text in texts], prompt_name=prompt)
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def term_starts(hpo_ids: list[str]) -> np.ndarray:
    """Returns the row of each term's first name in an index.

    build_index writes the names of a term one after another.
    """
    ids = np.asarray(hpo_ids)
    return np.flatnonzero(np.r_[True, ids[1:] != ids[:-1]])


def term_scores(similarities: np.ndarray, starts: np.ndarray) -> np.ndarray:
    """Returns each term's score: the similarity of its closest name.

    Args:
        similarities: The similarity of each name, in index order. In a 2D
            array, each row holds the similarities for one text.
        starts: The row of each term's first name, from term_starts.
    """
    return np.maximum.reduceat(similarities, starts, axis=-1)


def fuse(scores: list[np.ndarray]) -> np.ndarray:
    """Combines the term scores of several models into one score per term.

    Each model's scores become z-scores, which say how far a term lies above
    the model's average, in units of the model's spread. The combined score is
    their sum. Models with different similarity scales then count equally,
    and a model that is far surer of one term than of the others counts more.
    In a 2D array, each row is one text.
    """
    z_scores = [
        (s - s.mean(axis=-1, keepdims=True)) / s.std(axis=-1, keepdims=True)
        for s in scores
    ]
    return np.sum(z_scores, axis=0)


def current_terms(graph: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yields the HPO ID and node of each current term of an HPO release.

    A current term is an HPO class that has a label and is not deprecated.

    Args:
        graph: The graph of an HPO release in obographs JSON.
    """
    for node in graph["nodes"]:
        match = _HPO_CLASS.fullmatch(node["id"])
        if node.get("type") != "CLASS" or not match or not node.get("lbl"):
            continue
        if not node.get("meta", {}).get("deprecated"):
            yield f"HP:{match[1]}", node


def build_index(
    release: pathlib.Path, output: pathlib.Path, models: list[dict[str, str]]
) -> int:
    """Embeds the labels and synonyms of the current terms of an HPO release.

    The index records each model's name and prompt, so that HpoIndex can check
    that it embeds phenotypes the same way.

    Args:
        release: HPO release in obographs JSON, such as hp-base.json.
        output: .npz file to write; an existing file is replaced.
        models: normalize.hpo.models from settings.yaml: each with the `name`
            of a sentence-transformers model and an optional `prompt`.

    Returns:
        The number of names, one per label or synonym of a term.
    """
    graph = json.loads(release.read_text(encoding="utf-8"))["graphs"][0]
    rows: list[tuple[str, str, str]] = []
    for hpo_id, node in current_terms(graph):
        meta = node.get("meta", {})
        spellings = [
            node["lbl"],
            *(synonym["val"] for synonym in meta.get("synonyms", [])),
        ]
        for name in dict.fromkeys(spellings):
            rows.append((hpo_id, node["lbl"], name))
    hpo_ids, labels, names = zip(*rows, strict=True)
    arrays: dict[str, Any] = {
        "models": [model["name"] for model in models],
        "prompts": [model.get("prompt") or "" for model in models],
        "hpo_id": hpo_ids,
        "label": labels,
        "name": names,
    }
    for i, model in enumerate(models):
        encoder = load_encoder(model["name"])
        arrays[f"vectors_{i}"] = embed(encoder, list(names), model.get("prompt"))
    np.savez_compressed(output, **arrays)
    return len(rows)


def _describe(models: list[tuple[str, str]]) -> str:
    return " and ".join(
        f"{name} (prompt {prompt})" if prompt else name for name, prompt in models
    )


class HpoIndex:
    """The labels and synonyms of the HPO terms, with each model's embeddings."""

    def __init__(
        self, path: pathlib.Path, models: list[dict[str, str]], top_k: int
    ) -> None:
        """Reads the index that build_index wrote and loads its models.

        Args:
            path: The index file.
            models: normalize.hpo.models from settings.yaml.
            top_k: Terms returned per phenotype.

        Raises:
            ValueError: The index was built with other models or prompts, so
                its embeddings can't be compared with the phenotypes'.
            ImportError: sentence-transformers or torchvision, from the hpo
                extra, is not installed.
        """
        wanted = [(model["name"], model.get("prompt") or "") for model in models]
        with np.load(path) as index:
            if "models" in index.files:
                built = list(
                    zip(
                        index["models"].tolist(), index["prompts"].tolist(), strict=True
                    )
                )
            else:  # An index from before stage 4 combined models.
                built = [(index["model"].item(), "")]
            if built != wanted:
                raise ValueError(
                    f"the index {path} was built with {_describe(built)}, but"
                    f" settings.yaml names {_describe(wanted)}"
                )
            hpo_ids = index["hpo_id"].tolist()
            labels = index["label"].tolist()
            self._names = index["name"].tolist()
            self._vectors = [index[f"vectors_{i}"] for i in range(len(models))]
        self._starts = term_starts(hpo_ids)
        self._ends = np.append(self._starts[1:], len(hpo_ids))
        self._terms = [hpo_ids[row] for row in self._starts]
        self._labels = [labels[row] for row in self._starts]
        self._models = wanted
        self._encoders = [load_encoder(name) for name, _ in wanted]
        self._top_k = top_k

    def map(self, text: str) -> dict[str, Any]:
        """Returns the HPO term for `text`, and the top_k terms that fuse ranks highest.

        Each candidate gives, for each model, the closest name of the term and
        its cosine similarity. `models_agree` says whether all models score the
        same term highest, and is None with a single model.
        """
        similarities = [
            vectors @ embed(encoder, [text], prompt or None)[0]
            for vectors, encoder, (_, prompt) in zip(
                self._vectors, self._encoders, self._models, strict=True
            )
        ]
        scores = [term_scores(sims, self._starts) for sims in similarities]
        candidates = []
        for term in np.argsort(-fuse(scores))[: self._top_k]:
            by_model = {}
            for (name, _), sims in zip(self._models, similarities, strict=True):
                start = self._starts[term]
                row = start + int(np.argmax(sims[start : self._ends[term]]))
                by_model[name] = {
                    "name": self._names[row],
                    "similarity": round(float(sims[row]), 4),
                }
            candidates.append(
                {
                    "hpo_id": self._terms[term],
                    "label": self._labels[term],
                    "models": by_model,
                }
            )
        agree = len({int(np.argmax(term_score)) for term_score in scores}) == 1
        return {
            "hpo_id": candidates[0]["hpo_id"],
            "label": candidates[0]["label"],
            "models_agree": agree if len(scores) > 1 else None,
            "candidates": candidates,
        }
