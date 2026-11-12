"""Make scanned, faxed and image copies of the native PDFs.

For a scan or a fax, each page is rendered as an image and degraded, and the
images become an image-only PDF, so that gentrex transcribe has to OCR them.
The damage comes from a random stream seeded with the case ID and the level,
so the same PDF always gives the same copy. An image copy keeps the pages
clean but has only a document code as text, like some labs' PDFs.
"""

import html
import io
import pathlib
import random
import tempfile
import threading

import numpy as np
import pypdfium2 as pdfium
import render
from PIL import Image
from PIL import ImageFilter

# Pages are rendered at 3 pixels per point, which is 216 dpi.
SCALE = 3
DPI = 72 * SCALE
LEVELS = ("scan", "fax")
# PDFium is not thread-safe, and generate.py builds several reports at once.
_PDFIUM = threading.Lock()


def degrade(image: Image.Image, level: str, rng: random.Random) -> Image.Image:
    """Returns a grayscale page image after scanning or faxing.

    `scan` imitates an office scanner: a slight skew, blur, sensor noise and
    JPEG compression. `fax` imitates a fax at standard resolution: half the
    vertical resolution, a larger skew, black and white only, speckles and a
    few streaks.
    """
    noise = np.random.default_rng(rng.randrange(2**32))
    if level == "scan":
        image = image.rotate(
            rng.uniform(-0.8, 0.8),
            resample=Image.Resampling.BICUBIC,
            fillcolor=255,
            expand=False,
        )
        image = image.filter(ImageFilter.GaussianBlur(0.6))
        pixels = np.asarray(image, dtype=np.float32)
        pixels += noise.normal(0, 6, pixels.shape)
        image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=60)
        return Image.open(io.BytesIO(buffer.getvalue())).convert("L")
    if level == "fax":
        width, height = image.size
        image = image.resize((width, height // 2), Image.Resampling.BILINEAR)
        image = image.resize((width, height), Image.Resampling.NEAREST)
        image = image.rotate(
            rng.uniform(-1.5, 1.5),
            resample=Image.Resampling.BILINEAR,
            fillcolor=255,
            expand=False,
        )
        pixels = np.asarray(image, dtype=np.float32)
        pixels += noise.normal(0, 18, pixels.shape)
        black = pixels < 150
        speckles = noise.random(black.shape) < 0.002
        black ^= speckles
        for _ in range(rng.randint(1, 3)):
            row = rng.randrange(height - 3)
            black[row : row + rng.randint(1, 3), :] = True
        return Image.fromarray(np.where(black, 0, 255).astype(np.uint8))
    raise ValueError(f"unknown level {level!r}")


def _page_image(pdf: pdfium.PdfDocument, index: int) -> Image.Image:
    return pdf[index].render(scale=SCALE, grayscale=True).to_pil().convert("L")


def _image_pdf(image: Image.Image) -> pdfium.PdfDocument:
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=DPI)
    return pdfium.PdfDocument(buffer.getvalue())


def copy(
    native: pathlib.Path,
    out: pathlib.Path,
    level: str,
    case_id: str,
    pages: list[int] | None = None,
) -> None:
    """Writes a copy of a native PDF with degraded pages.

    Args:
        native: The native PDF.
        out: The PDF to write.
        level: `scan` or `fax`.
        case_id: Seeds the damage.
        pages: The 1-based pages to degrade, the others are kept native; None
            degrades every page.
    """
    rng = random.Random(f"{case_id}:{level}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with _PDFIUM:
        source = pdfium.PdfDocument(native)
        result = pdfium.PdfDocument.new()
        for index in range(len(source)):
            if pages is None or index + 1 in pages:
                result.import_pages(
                    _image_pdf(degrade(_page_image(source, index), level, rng))
                )
            else:
                result.import_pages(source, [index])
        result.save(out)


def mixed_pages(case_id: str, page_count: int) -> list[int]:
    """Returns the pages that a mixed PDF has scanned: some, but never all."""
    rng = random.Random(f"{case_id}:mixed")
    count = max(1, min(page_count - 1, round(page_count / 3)))
    return sorted(rng.sample(range(1, page_count + 1), count))


def document_code(case_id: str) -> str:
    """Returns the document code of an image copy, 24 characters without spaces.

    That is more than `transcribe.native_min_chars`, as in some labs' PDFs,
    so only the image that covers the page tells `gentrex transcribe` to OCR
    it.
    """
    number = sum(map(ord, case_id)) * 37 % 100000
    return f"RPT-SPEC-FORM-{number:05d}-EN v1"


def image_copy(
    native: pathlib.Path, out: pathlib.Path, case_id: str, chrome: str, canary: str
) -> None:
    """Writes a copy whose pages are images, with a document code as their only text.

    Chrome prints each page image with the code in small type under it, as
    some labs' PDFs come: the text layer then holds nothing but the code. The
    canary string goes into the PDF's title.
    """
    code = html.escape(document_code(case_id))
    with tempfile.TemporaryDirectory() as tmp:
        folder = pathlib.Path(tmp)
        sections = []
        with _PDFIUM:
            source = pdfium.PdfDocument(native)
            for index in range(len(source)):
                image = source[index].render(scale=2).to_pil().convert("RGB")
                image.save(folder / f"page-{index + 1}.png")
                sections.append(
                    f'<section><img src="page-{index + 1}.png">'
                    f'<div class="code">{code}</div></section>'
                )
        (folder / "pages.html").write_text(
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(case_id)} {html.escape(canary)}</title><style>"
            "@page { size: letter; margin: 0; } body { margin: 0; } "
            "section { position: relative; width: 8.5in; height: 11in; "
            "break-after: page; } section:last-child { break-after: auto; } "
            "img { width: 100%; height: 100%; display: block; } "
            ".code { position: absolute; left: 0.3in; bottom: 0.12in; "
            "font: 5pt Arial, sans-serif; color: #777; }"
            "</style></head><body>" + "".join(sections) + "</body></html>",
            encoding="utf-8",
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        render.print_pdf(chrome, folder / "pages.html", out)
