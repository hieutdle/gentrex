"""Builds the HPO index that stage 4 reads, from an HPO release.

The models are normalize.hpo.models in settings.yaml, and the index goes to
the file that normalize.hpo.path names.
"""

import argparse
import pathlib

from gentrex import config
from gentrex.normalize import phenotypes

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "release", type=pathlib.Path, help="HPO release in JSON, such as hp-base.json."
)
release = parser.parse_args().release
settings = config.load_settings()["normalize"]["hpo"]
output = pathlib.Path(settings["path"])
count = phenotypes.build_index(release, output, settings["models"])
print(f"wrote {count} names to {output}")
