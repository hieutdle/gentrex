#!/bin/bash
# Download the reference files that the benchmark generator and gentrex
# normalize read, into data/. A file that is already there is kept.
#
#   evaluation/download_reference_files.sh
set -euo pipefail
cd "$(dirname "$0")/.."

download() {
  if [ ! -f "$1" ]; then
    echo "downloading $1"
    mkdir -p "$(dirname "$1")"
    # Under another name first, so that a download that stops halfway
    # doesn't count as the file.
    curl -f -L -o "$1.part" "$2"
    mv "$1.part" "$1"
  fi
}

hpo=https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-09-01
download data/clinvar/variant_summary_2026-11.txt.gz \
  https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/variant_summary_2026-11.txt.gz
download data/ontology/hp-base.json "$hpo/hp-base.json"
download data/ontology/phenotype-v2026-09-01.hpoa "$hpo/phenotype.hpoa"
download data/ontology/mondo-base.json \
  https://github.com/monarch-initiative/mondo/releases/download/v2026-11-03/mondo-base.json
download data/ontology/hgnc_complete_set_2026-10-06.txt \
  https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/hgnc_complete_set_2026-10-06.txt
