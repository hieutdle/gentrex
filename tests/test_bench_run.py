"""Tests of gentrex-bench/run.py, which runs and scores the benchmark."""

import json
import math
import pathlib
import sys
from unittest import mock

import pytest
import yaml
from openai.types.chat import chat_completion
from openai.types.chat import chat_completion_message
from openai.types.chat import chat_completion_token_logprob as token_logprob

sys.path[:0] = [
    str(pathlib.Path(__file__).parents[1] / "gentrex-bench"),
    str(pathlib.Path(__file__).parent),
]

import run  # noqa: E402
import select_methods  # noqa: E402
import test_bench_scorer as scorer_tests  # noqa: E402

from gentrex import config  # noqa: E402


def test_a_run_is_found_by_its_input_while_other_jobs_run(tmp_path, monkeypatch):
    """Jobs in one Gentrex folder move the latest link, so it can't name a run."""
    monkeypatch.chdir(tmp_path)
    ours, theirs = tmp_path / "ours", tmp_path / "theirs"
    runs_dir = tmp_path / "results" / "select"
    records = {
        "20261124-100000": {"input": str(ours), "seconds": 1.0},
        "20261124-100001": {"input": str(theirs), "seconds": 1.0},
        "20261124-100002": {"input": str(ours / "pages.jsonl"), "crashed": "x"},
    }
    for name, record in records.items():
        (runs_dir / name).mkdir(parents=True)
        (runs_dir / name / "run.yaml").write_text(yaml.safe_dump(record))
    (runs_dir / "latest").symlink_to("20261124-100001")

    found = run.finished_run("select", ours)
    assert found == (runs_dir / "20261124-100000").resolve()


def test_only_pdfs_with_a_truth_file_are_linked(tmp_path):
    """Stray PDFs without a truth file are not passed to Gentrex."""
    truth = tmp_path / "truth" / "SYN-0001.json"
    truth.parent.mkdir()
    truth.write_text(json.dumps({"case": {"case_id": "SYN-0001"}}))
    for name in ("SYN-0001", "SYN-0101"):
        pdf = tmp_path / "pdf" / "scan" / f"{name}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF")

    linked = run.link_pdfs(tmp_path, "scan", tmp_path / "out")

    assert linked == 1
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["SYN-0001.pdf"]
    assert (tmp_path / "out" / "SYN-0001.pdf").read_bytes() == b"%PDF"


def test_a_command_with_failed_files_is_counted(tmp_path):
    """A model server that died halfway must not look like a clean run."""
    folder = tmp_path / "extract" / "20261110-120000"
    folder.mkdir(parents=True)
    (folder / "log.txt").write_text(
        "2026-11-10 12:00:00,000 INFO writing results\n"
        "2026-11-10 12:05:00,000 ERROR failed files: SYN-0001.pdf, SYN-0002.pdf\n"
    )
    scores = {
        "runs": {"extract": {"path": str(folder)}},
        "performance": {"commands": {"extract": {}}},
    }

    failures = run.add_failures(scores, {"extract": 1})

    assert failures == 1
    assert scores["performance"]["commands"]["extract"] == {
        "exit_status": 1,
        "failed_files": 2,
    }


def test_a_run_goes_on_after_the_command_of_a_finished_run_folder(tmp_path):
    """A crash in gentrex extract must not cost the GPU time of the commands before."""
    steps: list[tuple[str, str | None, str | None]] = [
        (name, None, None) for name in ("transcribe", "select", "extract")
    ]
    folder = tmp_path / "select" / "20261110-120000"
    folder.mkdir(parents=True)
    (folder / "run.yaml").write_text("input: x\n")

    assert run.steps_after(steps, folder) == steps[2:]
    with pytest.raises(ValueError, match="not a run folder"):
        run.steps_after(steps, tmp_path)


def _model(**kwargs) -> chat_completion.ChatCompletion:
    """Answers a question with Yes for a result page, and a page with its record.

    The record of every page has the MRN of its header. Only the result page
    has a result, and the page that reads "garbled" gets no JSON.
    """
    text = kwargs["messages"][-1]["content"]
    if "response_format" in kwargs:
        record = {"mrn": "SYN-MRN-0001", "variants": [], "overall_result_raw": None}
        if "POSITIVE" in text:
            record["overall_result_raw"] = "POSITIVE"
        answer = "{" if "garbled" in text else json.dumps(record)
        choice = chat_completion.Choice.model_construct(
            finish_reason="stop",
            message=chat_completion_message.ChatCompletionMessage.model_construct(
                content=answer
            ),
        )
    else:
        word = "Yes" if "POSITIVE" in text else "No"
        first = token_logprob.ChatCompletionTokenLogprob(
            token=word,
            logprob=math.log(0.9),
            top_logprobs=[token_logprob.TopLogprob(token=word, logprob=math.log(0.9))],
        )
        choice = chat_completion.Choice.model_construct(
            logprobs=chat_completion.ChoiceLogprobs(content=[first])
        )
    return chat_completion.ChatCompletion.model_construct(choices=[choice])


def test_the_other_ways_keep_a_page_for_what_gentrex_select_asks_about(
    tmp_path, monkeypatch
):
    """A header value alone keeps no page, and a failed request drops none."""
    texts = ("MRN SYN-MRN-0001 POSITIVE", "MRN SYN-MRN-0001 Methods", "garbled")
    pages = tmp_path / "pages.jsonl"
    pages.write_text(
        "".join(
            json.dumps({"file": "a.pdf", "page": n, "source": "native", "text": text})
            + "\n"
            for n, text in enumerate(texts, 1)
        )
    )
    client = mock.Mock()
    client.chat.completions.create.side_effect = _model
    monkeypatch.setattr(select_methods.llm, "make_client", lambda *_: client)

    found = select_methods.compare(
        pages, tmp_path / "out", config.load_settings(), "http://localhost:1/v1"
    )

    kept = {
        name: [
            json.loads(line)["keep"]
            for line in method["decisions"].read_text().splitlines()
        ]
        for name, method in found.items()
    }
    assert kept == {
        "one_question": [True, False, False],
        "page_extract": [True, False, True],
    }
    assert found["page_extract"]["requests"] == 3


def test_every_way_to_choose_pages_is_scored_like_gentrex_select(tmp_path):
    """The scores of gentrex select itself must be comparable with the others."""
    truth = scorer_tests._truth()
    pages = enumerate(scorer_tests._PAGES, 1)
    truth["pages"] = [{"page": n, "text": text} for n, text in pages]
    truth_dir, run_dir = scorer_tests._write_run(
        tmp_path, [truth], [scorer_tests._report(truth)]
    )
    select_dir = run_dir.parents[1] / "select" / run_dir.name

    def decisions(path: pathlib.Path, kept: tuple[bool, bool]) -> pathlib.Path:
        lines = [
            {"file": "SYN-0001.pdf", "page": page, "p_yes": {"q": float(keep)}}
            | {"keep": keep, "error": None if keep else "page 2 failed"}
            for page, keep in enumerate(kept, 1)
        ]
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        return path

    decisions(select_dir / "decisions.jsonl", (True, True))
    record = yaml.safe_load((select_dir / "run.yaml").read_text())
    record["settings"] |= {"keep_threshold": 0.5, "model": "fake"}
    (select_dir / "run.yaml").write_text(yaml.safe_dump(record))
    scores, _ = run.score.score(truth_dir, run_dir)
    other = {
        "decisions": decisions(tmp_path / "decisions.jsonl", (True, False)),
        "seconds": 9.0,
        "requests": 2,
        "prompt_tokens": 10,
        "completion_tokens": 20,
    }

    run.add_select_methods(scores, {"page_extract": other}, truth_dir)

    methods = scores["select_methods"]["methods"]
    assert (methods["questions"]["needed_dropped"], methods["questions"]["failed"]) == (
        0,
        0,
    )
    assert methods["questions"]["seconds"] == 36.0
    assert (
        methods["page_extract"]["needed_dropped"],
        methods["page_extract"]["failed"],
    ) == (
        1,
        1,
    )
    assert "page_extract" in run.score.markdown(scores)
