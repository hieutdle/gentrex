import pathlib
from collections.abc import Callable

import pytest


def _write_pdf(path: pathlib.Path, pages: list[tuple[str, int]]) -> None:
    """Writes a PDF of (text, height in points) pages; no text means a scan."""
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, (text, height) in enumerate(pages):
        stream = b"BT /F1 12 Tf 72 300 Td (%s) Tj ET" % text.encode() if text else b""
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 %d]"
            b" /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (height, 5 + 2 * i)
        )
        objects.append(
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_offset = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_offset,
    )
    path.write_bytes(bytes(pdf))


@pytest.fixture
def make_pdf(tmp_path: pathlib.Path) -> Callable[..., pathlib.Path]:
    """Returns a factory for small PDFs under tmp_path.

    The factory takes a file name, the heights in points of the scanned
    (blank) pages, and optionally the text of a native first page.
    """

    def make(name: str, scan_heights: list[int], native_text: str = "") -> pathlib.Path:
        path = tmp_path / name
        pages = [(native_text, 792)] if native_text else []
        _write_pdf(path, pages + [("", height) for height in scan_heights])
        return path

    return make
