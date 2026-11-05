"""Pseudonyms for patient keys and file names, for exports that are shared."""

import csv
import hashlib
import hmac
import pathlib


class Pseudonyms:
    """Gives each patient key and file name a pseudonym made with a secret key.

    The same name gets the same pseudonym under the same key, so Phenopackets
    of later runs match those shared before. Without the key, nobody can
    tell which name a pseudonym stands for.

    Attributes:
        issued: Each name that got a pseudonym, with its pseudonym.
    """

    def __init__(self, key: str) -> None:
        self._key = key.encode()
        self.issued: dict[str, str] = {}

    def patient(self, patient_key: str) -> str:
        """Returns the pseudonym of a patient key, such as P-3f2a9c41d07e5b18."""
        return self._issue("P", patient_key)

    def report(self, file: str) -> str:
        """Returns the pseudonym of a report's file name, such as R-9b1e0c2d4a6f8e31."""
        return self._issue("R", file)

    def write(self, path: pathlib.Path) -> None:
        """Writes each name and its pseudonym to a CSV file."""
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["name", "pseudonym"])
            writer.writerows(sorted(self.issued.items()))

    def _issue(self, prefix: str, name: str) -> str:
        digest = hmac.new(self._key, f"{prefix}:{name}".encode(), hashlib.sha256)
        pseudonym = f"{prefix}-{digest.hexdigest()[:16]}"
        self.issued[name] = pseudonym
        return pseudonym
