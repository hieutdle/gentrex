"""Print the HTML reports to PDF with headless Chrome."""

import pathlib
import shutil
import subprocess
import tempfile
import time

_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def find_chrome() -> str:
    """Returns the Chrome or Chromium executable.

    Raises:
        FileNotFoundError: Neither is installed.
    """
    for name in ("google-chrome", "chromium", "chromium-browser"):
        if found := shutil.which(name):
            return found
    if pathlib.Path(_MAC_CHROME).exists():
        return _MAC_CHROME
    raise FileNotFoundError("Chrome or Chromium is not installed; pass --chrome")


def chrome_version(chrome: str) -> str:
    """Returns the version line that Chrome prints."""
    return subprocess.run(
        [chrome, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()


def print_pdf(
    chrome: str, html_path: pathlib.Path, pdf_path: pathlib.Path, timeout: float = 120
) -> None:
    """Prints an HTML file to PDF with headless Chrome.

    Headless Chrome can stay alive after writing the PDF (seen on macOS), so it
    is stopped once its log reports the file as written.

    Raises:
        RuntimeError: Chrome wrote no PDF.
    """
    pdf_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        log_path = pathlib.Path(tmp) / "chrome.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [
                    chrome,
                    "--headless",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-pdf-header-footer",
                    f"--user-data-dir={pathlib.Path(tmp) / 'profile'}",
                    f"--print-to-pdf={pdf_path.resolve()}",
                    html_path.resolve().as_uri(),
                ],
                stdout=subprocess.DEVNULL,
                stderr=log,
            )
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            written = "bytes written to file" in log_path.read_text(errors="replace")
            if written or time.monotonic() > deadline:
                process.terminate()
                process.wait(timeout=30)
            else:
                time.sleep(0.2)
        if not pdf_path.exists():
            log_text = log_path.read_text(errors="replace")[-2000:]
            raise RuntimeError(f"Chrome did not write {pdf_path}:\n{log_text}")
