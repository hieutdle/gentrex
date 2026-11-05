"""Make scanned and faxed copies of the native PDFs.

Each page is rendered as an image and degraded, and the images become an
image-only PDF, so that gentrex transcribe has to OCR them. The damage comes
from a random stream seeded with the case ID and the level, so the same PDF
always gives the same copy.
"""

import io
import pathlib
import random

import numpy as np
import pypdfium2 as pdfium
from PIL import Image
from PIL import ImageFilter

# Pages are rendered at 3 pixels per point, which is 216 dpi.
SCALE = 3
DPI = 72 * SCALE
LEVELS = ("scan", "fax")


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
    source = pdfium.PdfDocument(native)
    result = pdfium.PdfDocument.new()
    for index in range(len(source)):
        if pages is None or index + 1 in pages:
            result.import_pages(
                _image_pdf(degrade(_page_image(source, index), level, rng))
            )
        else:
            result.import_pages(source, [index])
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out)


def mixed_pages(case_id: str, page_count: int) -> list[int]:
    """Returns the pages that a mixed PDF has scanned: some, but never all."""
    rng = random.Random(f"{case_id}:mixed")
    count = max(1, min(page_count - 1, round(page_count / 3)))
    return sorted(rng.sample(range(1, page_count + 1), count))
