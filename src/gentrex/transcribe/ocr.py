"""OCR for scanned pages with an OpenAI-compatible vision model."""

import base64
import dataclasses
import io
import logging
import pathlib
import time

import openai
import pypdfium2
from PIL import Image

_logger = logging.getLogger(__name__)

# A shared model server answers 502 while another model loads, which can take
# a minute. Waits before the second, third and fourth attempt.
_RETRY_WAITS_SECONDS = (5, 20, 60)

_RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)

# Misconfiguration: every later call would fail the same way.
FATAL_ERRORS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
)


@dataclasses.dataclass(frozen=True)
class OcrConfig:
    """The `transcribe.ocr` settings.

    Attributes:
        model: Vision model name on the server.
        prompt: Instruction sent with every page image.
        render_dpi: Resolution pages are rendered at.
        longest_dim: Longest image edge in pixels after downscaling; 0 keeps
            the rendered size.
        max_tokens: Cap on one page's transcription.
        timeout_seconds: Time allowed for one request.
    """

    model: str
    prompt: str
    render_dpi: int
    longest_dim: int
    max_tokens: int
    timeout_seconds: float


class OcrEngine:
    """Transcribes page images with a vision model."""

    def __init__(self, config: OcrConfig, base_url: str, api_key: str) -> None:
        self.config = config
        self._client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=config.timeout_seconds,
            max_retries=0,  # image_to_text is the only retry layer.
        )

    def image_to_text(self, image_png: bytes) -> str:
        """Returns the text on a page image.

        Connection, rate-limit and 5xx errors are retried.

        Raises:
            openai.OpenAIError: The request still failed, or cannot succeed.
        """
        for wait in _RETRY_WAITS_SECONDS:
            try:
                return self._request(image_png)
            except _RETRYABLE_ERRORS as exc:
                _logger.warning(
                    "OCR call failed (%s); retrying in %ds",
                    type(exc).__name__,
                    wait,
                )
                time.sleep(wait)
        return self._request(image_png)

    def _request(self, image_png: bytes) -> str:
        encoded = base64.b64encode(image_png).decode()
        content = [
            {"type": "text", "text": self.config.prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            },
        ]
        response = self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return (response.choices[0].message.content or "").strip()


def _render_page_png(
    doc: pypdfium2.PdfDocument, page_index: int, config: OcrConfig
) -> bytes:
    scale = config.render_dpi / 72.0  # PDF canvas units are 1/72 inch.
    # pypdfium2 is unannotated; its docs give `scale` as a float.
    bitmap = doc[page_index].render(scale=scale)  # pyright: ignore[reportArgumentType]
    image = bitmap.to_pil()
    if config.longest_dim:
        # thumbnail() only ever shrinks, keeping the aspect ratio.
        image.thumbnail(
            (config.longest_dim, config.longest_dim),
            resample=Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ocr_pages(
    pdf_path: pathlib.Path, page_numbers: list[int], ocr: OcrEngine
) -> dict[int, str | openai.OpenAIError]:
    """Transcribes the given 1-indexed pages.

    Returns:
        The text of each page, or the error that page hit, so one unreadable
        page does not cost the report its other pages.

    Raises:
        openai.OpenAIError: The endpoint is misconfigured (FATAL_ERRORS).
    """
    results: dict[int, str | openai.OpenAIError] = {}
    doc = pypdfium2.PdfDocument(pdf_path)
    try:
        for number in page_numbers:
            image = _render_page_png(doc, number - 1, ocr.config)
            try:
                results[number] = ocr.image_to_text(image)
            except FATAL_ERRORS:
                raise
            except openai.OpenAIError as exc:
                results[number] = exc
    finally:
        doc.close()
    return results
