"""Builds the HPO index that gentrex normalize reads, from an HPO release.

The models are normalize.hpo.models in settings.yaml, and the index goes to
the file that normalize.hpo.path names. --settings names a file of your own
that changes them, as for gentrex normalize.
"""

import argparse
import pathlib

from gentrex import config
from gentrex.normalize import phenotypes

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "release", type=pathlib.Path, help="HPO release in JSON, such as hp-base.json."
)
parser.add_argument(
    "--settings",
    type=pathlib.Path,
    help="YAML file with the settings that differ from Gentrex's defaults.",
)
args = parser.parse_args()
try:
    settings = config.load_settings(args.settings)["normalize"]["hpo"]
except config.SettingsError as exc:
    parser.error(str(exc))
output = pathlib.Path(settings["path"])
count = phenotypes.build_index(args.release, output, settings["models"])
print(f"wrote {count} names to {output}")
