"""OCR for scanned pages with an OpenAI-compatible vision model."""

import base64
import dataclasses
import io
import pathlib
from concurrent import futures

import pypdfium2
from PIL import Image

from gentrex import llm


@dataclasses.dataclass(frozen=True)
class OcrConfig:
    """The `transcribe.ocr` settings.

    Attributes:
        model: Vision model name on the server.
        prompt: Text sent after every page image; empty sends the image alone.
        render_dpi: Resolution pages are rendered at.
        longest_dim: Longest image edge in pixels after downscaling; 0 keeps
            the rendered size.
        max_tokens: Cap on one page's transcription.
        temperature: Sampling temperature.
        timeout_seconds: Time allowed for one request.
        concurrency: OCR requests in flight at the same time.
    """

    model: str
    prompt: str
    render_dpi: int
    longest_dim: int
    max_tokens: int
    temperature: float
    timeout_seconds: float
    concurrency: int


class OcrEngine:
    """Transcribes page images with a vision model."""

    def __init__(self, config: OcrConfig, base_url: str, api_key: str) -> None:
        self.config = config
        self._client = llm.make_client(base_url, api_key, config.timeout_seconds)

    def image_to_text(self, image_png: bytes) -> str:
        """Returns the text on a page image.

        Connection, rate-limit and 5xx errors are retried.

        Raises:
            openai.OpenAIError: The request still failed, or cannot succeed.
        """
        return llm.with_retries(lambda: self._request(image_png))

    def text_or_error(self, image_png: bytes) -> str | Exception:
        """Returns the text on a page image, or the error that prevented it.

        Raises:
            openai.OpenAIError: The endpoint is misconfigured (llm.FATAL_ERRORS).
        """
        try:
            return self.image_to_text(image_png)
        except llm.FATAL_ERRORS:
            raise
        except Exception as exc:  # One page's failure must not cost the others.
            return exc

    def _request(self, image_png: bytes) -> str:
        encoded = base64.b64encode(image_png).decode()
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            },
        ]
        if self.config.prompt:
            content.append({"type": "text", "text": self.config.prompt})
        response = self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
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


def submit_pages(
    pdf_path: pathlib.Path,
    page_numbers: list[int],
    ocr: OcrEngine,
    pool: futures.Executor,
) -> dict[int, futures.Future[str | Exception]]:
    """Renders the given 1-indexed pages and queues an OCR call for each.

    Returns:
        The pending result of each page: its text, or the error that page hit,
        so one unreadable page does not cost the report its other pages. A
        misconfigured endpoint (llm.FATAL_ERRORS) is raised by the result instead.
    """
    doc = pypdfium2.PdfDocument(pdf_path)
    try:
        # PDFium is not thread-safe: render here, send from the pool.
        return {
            number: pool.submit(
                ocr.text_or_error, _render_page_png(doc, number - 1, ocr.config)
            )
            for number in page_numbers
        }
    finally:
        doc.close()
