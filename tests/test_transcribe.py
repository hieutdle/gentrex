import dataclasses
import json
import logging
import pathlib
import struct
import threading
import time
from collections.abc import Callable
from unittest import mock

import openai
import pytest

from gentrex.transcribe import ocr
from gentrex.transcribe import run

_NATIVE_TEXT = "Hereditary cancer panel: no variants reported."


class _FakeOcr(ocr.OcrEngine):
    """Answers each page image with its height in pixels.

    Pages are rendered at 72 DPI, so that is the page's height in points,
    which tells the pages of a test apart.
    """

    def __init__(
        self, concurrency: int, on_call: Callable[[int], object] = lambda height: None
    ) -> None:
        config = ocr.OcrConfig(
            model="fake",
            prompt="",
            render_dpi=72,
            longest_dim=0,
            max_tokens=1,
            temperature=0.0,
            timeout_seconds=1,
            concurrency=concurrency,
        )
        super().__init__(config, "http://unused", "EMPTY")
        self._on_call = on_call
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0

    def image_to_text(self, image_png: bytes) -> str:
        (height,) = struct.unpack(">I", image_png[20:24])
        with self._lock:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            self._on_call(height)
            return str(height)
        finally:
            with self._lock:
                self._in_flight -= 1


def _read_pages(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_empty_prompt_sends_the_page_image_alone():
    """LightOnOCR is trained to transcribe a page from its image alone."""
    config = dataclasses.replace(_FakeOcr(1).config, prompt="")
    with mock.patch.object(openai, "OpenAI") as client_class:
        ocr.OcrEngine(config, "http://unused", "EMPTY").image_to_text(b"png")

    create = client_class.return_value.chat.completions.create
    (message,) = create.call_args.kwargs["messages"]
    assert [part["type"] for part in message["content"]] == ["image_url"]


def test_requests_in_flight_span_pdfs(make_pdf, tmp_path):
    """The limit counts requests across PDFs, not within one PDF."""
    pdfs = [make_pdf(f"{i}.pdf", [400, 410]) for i in range(4)]
    all_arrived = threading.Barrier(4)
    fake = _FakeOcr(4, on_call=lambda height: all_arrived.wait(timeout=5))

    failed = run.run(pdfs, tmp_path / "pages.jsonl", 20, fake)

    assert failed == []
    assert fake.max_in_flight == 4


def test_each_page_keeps_its_text_in_input_order(make_pdf, tmp_path):
    """Answers arriving out of order must not move text between pages."""
    pdfs = [
        make_pdf("a.pdf", [400, 410], native_text=_NATIVE_TEXT),
        make_pdf("b.pdf", [420]),
        make_pdf("c.pdf", [430, 440]),
    ]

    def earlier_pages_answer_later(height: int) -> None:
        time.sleep((450 - height) / 1000)

    output = tmp_path / "pages.jsonl"

    failed = run.run(pdfs, output, 20, _FakeOcr(4, earlier_pages_answer_later))

    assert failed == []
    assert [(p["file"], p["page"], p["text"]) for p in _read_pages(output)] == [
        ("a.pdf", 1, _NATIVE_TEXT),
        ("a.pdf", 2, "400"),
        ("a.pdf", 3, "410"),
        ("b.pdf", 1, "420"),
        ("c.pdf", 1, "430"),
        ("c.pdf", 2, "440"),
    ]


def test_last_log_line_counts_pages_for_the_speed(make_pdf, tmp_path, caplog):
    """The pages-per-minute figure is only right if every page is counted."""
    pdfs = [
        make_pdf("a.pdf", [400, 410], native_text=_NATIVE_TEXT),
        make_pdf("b.pdf", [420]),
    ]
    caplog.set_level(logging.INFO, logger="gentrex")

    run.run(pdfs, tmp_path / "pages.jsonl", 20, _FakeOcr(2))

    assert caplog.records[-1].getMessage().startswith("wrote 4 pages (3 scanned) in")


def test_failed_ocr_call_costs_only_that_page(make_pdf, tmp_path):
    pdfs = [make_pdf("a.pdf", [400, 410]), make_pdf("b.pdf", [420])]

    def fail_page_410(height: int) -> None:
        if height == 410:
            raise openai.OpenAIError("server unavailable")

    output = tmp_path / "pages.jsonl"

    failed = run.run(pdfs, output, 20, _FakeOcr(2, fail_page_410))

    assert failed == ["a.pdf"]
    first, broken, other_pdf = _read_pages(output)
    assert (first["text"], first["error"]) == ("400", None)
    assert broken["text"] == "" and "server unavailable" in broken["error"]
    assert (other_pdf["text"], other_pdf["error"]) == ("420", None)


def test_misconfigured_endpoint_stops_the_run(make_pdf, tmp_path):
    """A bad key fails every page the same way, so the run must not go on."""

    def reject(height: int) -> None:
        raise openai.AuthenticationError("bad key", response=mock.Mock(), body=None)

    with pytest.raises(openai.AuthenticationError):
        run.run(
            [make_pdf("a.pdf", [400])],
            tmp_path / "pages.jsonl",
            20,
            _FakeOcr(2, reject),
        )
