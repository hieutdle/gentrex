"""Stage 2 orchestration: stage 1 pages to a JSONL file of PageDecisions."""

import json
import logging
import pathlib
import time
from concurrent import futures

from gentrex import records
from gentrex.pagedecide import score

_logger = logging.getLogger(__name__)


def _decide(page: records.PageRecord, scorer: score.PageScorer) -> records.PageDecision:
    """Asks the page's questions in turn and decides whether to keep it.

    A page is kept when a question's P(yes) reaches the threshold or has no
    answer, so a failure never drops a page unseen. A page without text is
    dropped and a page with a stage 1 error is kept, both without a request.
    """
    config = scorer.config
    if page.error:
        return records.PageDecision(
            page.file,
            page.page,
            dict.fromkeys(config.questions),
            keep=True,
            error=f"stage 1: {page.error}",
        )
    if not page.text:
        return records.PageDecision(
            page.file, page.page, dict.fromkeys(config.questions), keep=False
        )
    p_yes: dict[str, float | None] = {}
    errors: list[str] = []
    for name, question in config.questions.items():
        answer = scorer.ask_or_error(page.text, question)
        if isinstance(answer, Exception):
            p_yes[name] = None
            errors.append(f"{name}: {type(answer).__name__}: {answer}")
        else:
            p_yes[name] = answer
    return records.PageDecision(
        page.file,
        page.page,
        p_yes,
        keep=any(p is None or p >= config.keep_threshold for p in p_yes.values()),
        error="; ".join(errors) or None,
    )


def run(
    input_path: pathlib.Path,
    decisions_path: pathlib.Path,
    kept_path: pathlib.Path,
    scorer: score.PageScorer,
) -> list[str]:
    """Decides which pages of a stage 1 file to keep.

    Up to the config's `concurrency` pages are scored at once, each asking
    its questions in turn. Both outputs are written in input order; existing
    files are replaced.

    Args:
        input_path: JSONL file of PageRecords, from stage 1.
        decisions_path: JSONL file of PageDecisions to write, one per page.
        kept_path: JSONL file to copy the kept PageRecords to, unchanged, so
            the next stage reads its pages from one file.
        scorer: Asks the questions.

    Returns:
        Names of the files with a page error (a failed question or a stage 1
        error), in input order. Their pages are still written.

    Raises:
        openai.OpenAIError: The endpoint is misconfigured (llm.FATAL_ERRORS).
        score.MissingLogprobsError: The server sent no logprobs.
    """
    start = time.perf_counter()
    with input_path.open(encoding="utf-8") as fh:
        pages = [records.PageRecord(**json.loads(line)) for line in fh]
    failed: list[str] = []
    kept = 0
    last_file = None
    pool = futures.ThreadPoolExecutor(scorer.config.concurrency)
    try:
        with (
            decisions_path.open("w", encoding="utf-8") as decisions_fh,
            kept_path.open("w", encoding="utf-8") as kept_fh,
        ):
            decisions = pool.map(lambda page: _decide(page, scorer), pages)
            for page, decision in zip(pages, decisions, strict=True):
                if decision.file != last_file:
                    _logger.info("deciding %s", decision.file)
                    last_file = decision.file
                decisions_fh.write(decision.to_json() + "\n")
                if decision.keep:
                    kept += 1
                    kept_fh.write(page.to_json() + "\n")
                if decision.error and decision.file not in failed:
                    failed.append(decision.file)
    finally:
        # On an error or Ctrl-C, pages still waiting are not sent.
        pool.shutdown(cancel_futures=True)
    seconds = time.perf_counter() - start
    _logger.info(
        "wrote %d pages (%d kept) in %.0f s: %.1f pages per minute",
        len(pages),
        kept,
        seconds,
        len(pages) / seconds * 60,
    )
    return failed
