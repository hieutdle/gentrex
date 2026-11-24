"""Make scanned and faxed copies of the native PDFs.

Each page is rendered as an image and degraded, and the images become an
image-only PDF, so that gentrex transcribe has to OCR them. The damage comes
from a random stream seeded with the case ID and the level, so the same PDF
always gives the same copy.
"""

import io
import pathlib
import random
import threading

import numpy as np
import pypdfium2 as pdfium
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

    `scan` imitates a good office scanner: a slight skew, a little blur and
    sensor noise, and JPEG compression. `fax` imitates a fax: seven eighths
    of the vertical resolution, a larger skew, black and white only, a few
    speckles and at most one thin streak.
    """
    noise = np.random.default_rng(rng.randrange(2**32))
    if level == "scan":
        image = image.rotate(
            rng.uniform(-0.4, 0.4),
            resample=Image.Resampling.BICUBIC,
            fillcolor=255,
            expand=False,
        )
        image = image.filter(ImageFilter.GaussianBlur(0.4))
        pixels = np.asarray(image, dtype=np.float32)
        pixels += noise.normal(0, 3, pixels.shape)
        image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=75)
        return Image.open(io.BytesIO(buffer.getvalue())).convert("L")
    if level == "fax":
        width, height = image.size
        image = image.resize((width, height * 7 // 8), Image.Resampling.BILINEAR)
        image = image.resize((width, height), Image.Resampling.NEAREST)
        image = image.rotate(
            rng.uniform(-0.9, 0.9),
            resample=Image.Resampling.BILINEAR,
            fillcolor=255,
            expand=False,
        )
        pixels = np.asarray(image, dtype=np.float32)
        pixels += noise.normal(0, 8, pixels.shape)
        black = pixels < 150
        speckles = noise.random(black.shape) < 0.00025
        black ^= speckles
        for _ in range(rng.randint(0, 1)):
            black[rng.randrange(height), :] = True
        return Image.fromarray(np.where(black, 0, 255).astype(np.uint8))
    raise ValueError(f"unknown level {level!r}")


def _page_image(pdf: pdfium.PdfDocument, index: int) -> Image.Image:
    return pdf[index].render(scale=SCALE, grayscale=True).to_pil().convert("L")


def _image_pdf(image: Image.Image) -> pdfium.PdfDocument:
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=DPI)
    return pdfium.PdfDocument(buffer.getvalue())


def copy(native: pathlib.Path, out: pathlib.Path, level: str, case_id: str) -> None:
    """Writes a copy of a native PDF with every page degraded.

    Args:
        native: The native PDF.
        out: The PDF to write.
        level: `scan` or `fax`.
        case_id: Seeds the damage.
    """
    rng = random.Random(f"{case_id}:{level}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with _PDFIUM:
        source = pdfium.PdfDocument(native)
        result = pdfium.PdfDocument.new()
        for index in range(len(source)):
            result.import_pages(
                _image_pdf(degrade(_page_image(source, index), level, rng))
            )
        result.save(out)
