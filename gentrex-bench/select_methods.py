"""Other ways to choose a report's pages, to compare gentrex select with.

gentrex select asks a model three yes/no questions about each page and reads
the probability of "Yes" from the first answer token. run.py --select-methods
tries two other ways on the same pages and the same model server:

  one_question   One general question per page, scored in the same way.
  page_extract   The model fills the extraction schema from each page alone,
                 and the page is kept if its record has a result, a variant,
                 a clinical feature or a date of the test.

Both go through gentrex select's own code with another scorer, so pages are
sent, kept on a failure and written as in gentrex select, and the benchmark's
scorer counts the kept pages in the same way.
"""

import dataclasses
import logging
import os
import pathlib
import time
from typing import Any

from gentrex import config
from gentrex import llm
from gentrex import records
from gentrex.extract import extractor
from gentrex.select import run as select_run
from gentrex.select import score as select_score

_logger = logging.getLogger("run")

# Worded apart from gentrex select's instruction from the first word on, so
# that the server's prefix cache of that run doesn't speed this one up.
_INSTRUCTION = (
    "This is one page from a clinical genetic test report. The text was read"
    " from a PDF and may contain OCR errors."
)
_QUESTION = (
    "Is this page important for a record of the patient's test? Important"
    " pages state the test result, the variants found, the patient's clinical"
    " features or the dates of the specimen and the report."
)
# What gentrex select's three questions ask about, as fields of the schema.
_KEPT_FOR = (
    "overall_result_raw",
    "karyotype",
    "variants",
    "patient_phenotypes",
    "clinical_indication",
    "collection_date",
    "received_date",
    "report_date",
)


class _PageExtract(select_score.PageScorer):
    """Answers 1.0 for a page whose own record has something to keep."""

    def __init__(
        self, select: select_score.SelectConfig, extract: extractor.ReportExtractor
    ) -> None:
        self.config = select
        self._extract = extract

    def ask_or_error(self, text: str, question: str) -> float | Exception:
        page = records.PageRecord(file="", page=1, source="native", text=text)
        answer = self._extract.extract_or_error([page])
        if isinstance(answer, Exception):
            return answer
        return float(any(answer.data.get(field) for field in _KEPT_FOR))


def _scorers(
    settings: dict[str, Any], base_url: str, api_key: str
) -> dict[str, select_score.PageScorer]:
    """Returns the scorer of each method, all on the model of gentrex select."""
    select = select_score.SelectConfig(**settings["select"])
    extract = extractor.ExtractConfig(
        **{**settings["extract"], "model": select.model},
        schema=config.load_schema(),
    )
    return {
        "one_question": select_score.PageScorer(
            dataclasses.replace(
                select, instruction=_INSTRUCTION, questions={"is_important": _QUESTION}
            ),
            llm.make_client(base_url, api_key, select.timeout_seconds),
        ),
        "page_extract": _PageExtract(
            dataclasses.replace(select, questions={"page_extract": ""}),
            extractor.ReportExtractor(
                extract, llm.make_client(base_url, api_key, extract.timeout_seconds)
            ),
        ),
    }


def compare(
    pages_path: pathlib.Path, out: pathlib.Path, settings: dict[str, Any], base_url: str
) -> dict[str, dict[str, Any]]:
    """Chooses the pages of a run of gentrex transcribe with each other method.

    Args:
        pages_path: pages.jsonl of gentrex transcribe.
        out: Folder to create, with a folder for each method that holds its
            decisions.jsonl and the pages.jsonl of the pages it kept.
        settings: Gentrex's settings, as the run's commands read them.
        base_url: Address of the server of gentrex select's model.

    Returns:
        For each method, the path of its `decisions`, and the `seconds`,
        `requests`, `prompt_tokens` and `completion_tokens` it took.
    """
    api_key = os.environ.get("GENTREX_LLM_API_KEY") or "EMPTY"
    found = {}
    for name, scorer in _scorers(settings, base_url, api_key).items():
        folder = out / name
        folder.mkdir(parents=True)
        _logger.info("choosing pages by %s", name)
        before, started = llm.usage(), time.perf_counter()
        select_run.run(
            pages_path, folder / "decisions.jsonl", folder / "pages.jsonl", scorer
        )
        seconds = time.perf_counter() - started
        found[name] = {
            "decisions": folder / "decisions.jsonl",
            "seconds": round(seconds, 1),
            **{key: count - before[key] for key, count in llm.usage().items()},
        }
    return found
