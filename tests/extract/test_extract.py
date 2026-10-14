import json
import pathlib
from collections.abc import Callable
from unittest import mock

import openai
import pytest
from openai.types.chat import chat_completion
from openai.types.chat import chat_completion_message

from gentrex import records
from gentrex.extract import extractor
from gentrex.extract import run

_CONFIG = extractor.ExtractConfig(
    model="fake",
    instruction="Extract the report.",
    max_tokens=100,
    timeout_seconds=1,
    concurrency=2,
    schema={
        "type": "object",
        "properties": {
            "test_name": {"type": ["string", "null"]},
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"gene_symbol": {"type": ["string", "null"]}},
                },
            },
        },
    },
)


def _echo(pages: str) -> tuple[str, str]:
    """Answers with the pages the request sent."""
    return json.dumps({"sent": pages}), "stop"


def _client(answer: Callable[[str], tuple[str, str]] = _echo) -> mock.Mock:
    """Returns a client that answers a report's pages with `answer(pages)`.

    `answer` returns the content and the finish reason of the response.
    """

    def create(**kwargs) -> chat_completion.ChatCompletion:
        content, finish_reason = answer(kwargs["messages"][-1]["content"])
        message = chat_completion_message.ChatCompletionMessage.model_construct(
            content=content
        )
        return chat_completion.ChatCompletion.model_construct(
            choices=[
                chat_completion.Choice.model_construct(
                    finish_reason=finish_reason, message=message
                )
            ]
        )

    client = mock.Mock()
    client.chat.completions.create.side_effect = create
    return client


def _run(
    tmp_path: pathlib.Path, client: mock.Mock, *pages: records.PageRecord
) -> tuple[list[str], list[dict]]:
    """Runs stage 3 on `pages`; returns the failed files and the records."""
    input_path = tmp_path / "pages.jsonl"
    input_path.write_text("".join(page.to_json() + "\n" for page in pages))
    output_path = tmp_path / "extractions.jsonl"
    failed = run.run(
        input_path, output_path, extractor.ReportExtractor(_CONFIG, client)
    )
    lines = output_path.read_text().splitlines()
    return failed, [json.loads(line) for line in lines]


def test_pages_of_a_report_go_in_one_request_in_page_order(tmp_path):
    """One record covers a report, so the model must read its pages together."""
    client = _client()

    failed, extractions = _run(
        tmp_path,
        client,
        records.PageRecord("a.pdf", 1, "native", "Patient: A"),
        records.PageRecord("a.pdf", 3, "native", "Result: positive"),
        records.PageRecord("b.pdf", 2, "native", "Result: negative"),
    )

    assert failed == []
    assert client.chat.completions.create.call_count == 2
    assert [(e["file"], e["pages"], e["data"]["sent"]) for e in extractions] == [
        (
            "a.pdf",
            [1, 3],
            "--- PAGE 1 ---\nPatient: A\n\n--- PAGE 3 ---\nResult: positive",
        ),
        ("b.pdf", [2], "--- PAGE 2 ---\nResult: negative"),
    ]


def test_page_with_a_stage_1_error_is_left_out_and_noted(tmp_path):
    """The other pages still give a record, marked as possibly incomplete."""
    failed, (extraction,) = _run(
        tmp_path,
        _client(),
        records.PageRecord("a.pdf", 1, "native", "Result: positive"),
        records.PageRecord("a.pdf", 2, "scanned", "", "OCR failed"),
    )

    assert failed == ["a.pdf"]
    assert extraction["pages"] == [1]
    assert extraction["data"] == {"sent": "--- PAGE 1 ---\nResult: positive"}
    assert extraction["error"] == "page 2: stage 1: OCR failed"


def test_report_without_text_skips_the_model(tmp_path):
    """With every page lost in stage 1, there is nothing to send."""
    client = _client()
    page = records.PageRecord("a.pdf", 1, "scanned", "", "OCR failed")

    failed, (extraction,) = _run(tmp_path, client, page)

    assert failed == ["a.pdf"]
    assert extraction["data"] is None
    assert not client.chat.completions.create.called


def test_every_field_is_required():
    """A field the report does not state must come back null, not go missing."""
    client = _client()
    page = records.PageRecord("a.pdf", 1, "native", "Result: negative")

    extractor.ReportExtractor(_CONFIG, client).extract([page])

    request = client.chat.completions.create.call_args.kwargs
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["required"] == ["test_name", "variants"]
    assert schema["properties"]["variants"]["items"]["required"] == ["gene_symbol"]


def test_cut_off_answer_costs_only_that_report(tmp_path):
    """The report after it still gets its record."""

    def answer(pages: str) -> tuple[str, str]:
        if "LONG" in pages:
            return '{"sent": "--- PA', "length"
        return _echo(pages)

    failed, extractions = _run(
        tmp_path,
        _client(answer),
        records.PageRecord("a.pdf", 1, "native", "LONG"),
        records.PageRecord("b.pdf", 1, "native", "short"),
    )

    assert failed == ["a.pdf"]
    assert [(e["file"], e["data"], e["error"]) for e in extractions] == [
        ("a.pdf", None, "ValueError: answer cut off at max_tokens (100)"),
        ("b.pdf", {"sent": "--- PAGE 1 ---\nshort"}, None),
    ]


def test_answer_with_half_a_surrogate_pair_is_still_written(tmp_path):
    """JSON allows the escape but UTF-8 cannot encode it; the run must go on."""
    _, (extraction,) = _run(
        tmp_path,
        _client(lambda pages: ('{"test_name": "\\ud835"}', "stop")),
        records.PageRecord("a.pdf", 1, "native", "Result: negative"),
    )

    assert extraction["data"] == {"test_name": "\ud835"}


def test_misconfigured_endpoint_stops_the_run(tmp_path):
    """A bad key fails every report the same way, so the run must not go on."""

    def reject(pages: str) -> tuple[str, str]:
        raise openai.AuthenticationError("bad key", response=mock.Mock(), body=None)

    with pytest.raises(openai.AuthenticationError):
        _run(
            tmp_path,
            _client(reject),
            records.PageRecord("a.pdf", 1, "native", "Result: negative"),
        )
