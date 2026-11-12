#!/bin/bash
# Download everything that the evaluation jobs need on Minerva. Run it in an
# interactive session, from the gentrex folder:
#
#   SERVING=/path/to/serving evaluation/minerva/prepare.sh
#
# SERVING is the serving folder, which gets vLLM, the models and Chrome.
# Whatever is already there is kept, so the script can run again after it
# was stopped. VERSION names the benchmark version, v1 by default.
set -euo pipefail
: "${SERVING:?set SERVING to the serving folder}"
cd "$(dirname "$0")/../.."
VERSION="${VERSION:-v1}"
settings=evaluation/settings.yaml
chrome=157.0.8103.38

echo "== Gentrex and the packages of gentrex normalize"
uv sync --inexact --extra hpo

echo "== Reference files and the HPO index"
evaluation/download_reference_files.sh
index=$(.venv/bin/python -c "
import pathlib
from gentrex import config
print(config.load_settings(pathlib.Path('$settings'))['normalize']['hpo']['path'])")
if [ ! -f "$index" ]; then
  .venv/bin/python scripts/build_hpo_index.py --settings "$settings" \
    data/ontology/hp-base.json
fi

echo "== The cases of $VERSION"
if [ ! -d "data/gentrex-bench/$VERSION/cases" ]; then
  .venv/bin/python gentrex-bench/generator/generate.py --version "$VERSION" sample
fi

echo "== vLLM"
mkdir -p "$SERVING/models"
if [ ! -f "$SERVING/vllm.sif" ]; then
  command -v apptainer > /dev/null || module load apptainer
  # The download cache would otherwise fill the home folder.
  APPTAINER_CACHEDIR="$SERVING/apptainer-cache" \
    apptainer pull "$SERVING/vllm.sif" docker://vllm/vllm-openai:latest
  rm -rf "$SERVING/apptainer-cache"
fi

echo "== The models of Gentrex and the model that writes the reports"
for model in lightonai/LightOnOCR-3-4B google/gemma-4-26B-A4B-it \
  google/gemma-4-31B-it meta-models/Muse-Glimmer-30B; do
  uvx --from huggingface_hub hf download "$model" \
    --local-dir "$SERVING/models/${model##*/}"
done

echo "== Chrome, which prints the reports"
if [ ! -d "$SERVING/chrome-headless-shell-linux64" ]; then
  curl -f -L -o "$SERVING/chrome.zip" \
    "https://storage.googleapis.com/chrome-for-testing-public/$chrome/linux64/chrome-headless-shell-linux64.zip"
  unzip -q "$SERVING/chrome.zip" -d "$SERVING"
  rm "$SERVING/chrome.zip"
fi
"$SERVING/chrome-headless-shell-linux64/chrome-headless-shell" --version

echo "Minerva is ready for generate_reports.lsf and run_pipeline.lsf"
