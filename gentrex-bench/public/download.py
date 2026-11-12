"""Download the public sample reports in catalog.csv.

    uv run python gentrex-bench/public/download.py

The PDFs go to data/gentrex-bench/public/pdf/, with a record of each download
in downloads.json next to them. They stay out of git, because the labs
haven't allowed redistribution. A report whose checksum in catalog.csv
differs from the downloaded file is reported, because the lab has then
changed the file since the benchmark was set up.
"""

import argparse
import csv
import datetime
import hashlib
import json
import logging
import pathlib
import sys
import urllib.error
import urllib.request

import pypdfium2 as pdfium

_logger = logging.getLogger("public")
_CATALOG = pathlib.Path(__file__).with_name("catalog.csv")
_USER_AGENT = "Mozilla/5.0 (compatible; gentrex-bench)"


def _fetch(url: str, timeout: float) -> bytes:
    """Returns the body at `url`.

    Raises:
        urllib.error.URLError: The request failed.
        ValueError: The body isn't a PDF.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    if not body.startswith(b"%PDF"):
        raise ValueError("not a PDF")
    return body


def download(row: dict[str, str], out: pathlib.Path, timeout: float) -> dict:
    """Downloads one report, trying its alternate URLs if the first fails.

    A PDF that is already in `out` is kept when no URL works, so a report
    can also be saved by hand from a browser.

    Returns:
        The record of the download: the URL that worked, the checksum, the
        size, the page count and the date, or the errors of every URL.
    """
    path = out / f"{row['id']}.pdf"
    errors = {}
    for url in [row["url"], *row["alternate_urls"].split()]:
        if not url:
            continue
        try:
            body = _fetch(url, timeout)
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            errors[url] = str(exc)
            continue
        path.write_bytes(body)
        return _record(row["id"], url, path)
    if path.is_file() and path.read_bytes().startswith(b"%PDF"):
        return _record(row["id"], "saved by hand", path)
    return {"id": row["id"], "errors": errors}


def _record(report_id: str, url: str, path: pathlib.Path) -> dict:
    body = path.read_bytes()
    return {
        "id": report_id,
        "url": url,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "pages": len(pdfium.PdfDocument(path)),
        "date": datetime.date.today().isoformat(),
    }


def main() -> int:
    """Downloads every report of the catalog that is in scope, or all with --all."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description="Download the public sample reports.")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("data/gentrex-bench/public"),
        help="Folder for the PDFs and downloads.json.",
    )
    parser.add_argument(
        "--all", action="store_true", help="Also download reports out of scope."
    )
    parser.add_argument("--timeout", type=float, default=60, help="Seconds per URL.")
    args = parser.parse_args()
    with _CATALOG.open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if args.all or r["in_scope"] == "yes"]
    (args.out / "pdf").mkdir(parents=True, exist_ok=True)
    records, changed, failed = [], [], []
    for row in rows:
        record = download(row, args.out / "pdf", args.timeout)
        records.append(record)
        if "errors" in record:
            failed.append(row["id"])
            _logger.warning("%s: no URL worked", row["id"])
        elif row["sha256"] and row["sha256"] != record["sha256"]:
            changed.append(row["id"])
            _logger.warning(
                "%s: the file differs from the catalog's checksum", row["id"]
            )
        else:
            _logger.info("%s: %d pages", row["id"], record["pages"])
    (args.out / "downloads.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    _logger.info(
        "downloaded %d of %d reports; failed: %s; changed: %s",
        len(rows) - len(failed),
        len(rows),
        ", ".join(failed) or "none",
        ", ".join(changed) or "none",
    )
    return 1 if failed or changed else 0


if __name__ == "__main__":
    sys.exit(main())
