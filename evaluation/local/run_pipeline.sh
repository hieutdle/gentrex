#!/bin/bash
# Run Gentrex on the benchmark reports on this machine, and score it.
#
#   evaluation/local/run_pipeline.sh [option of gentrex-bench/run.py ...]
#
# Downloads the reference files and builds the HPO index if they are
# missing. Then gentrex-bench/run.py runs gentrex transcribe, select, extract
# and normalize on each copy of the reports and scores the records. It
# starts the model server of each command with serve.sh and stops it
# afterwards. The scores go to results/gentrex-bench/.
#
# By default the script makes six runs of the dev reports: one for each copy
# (native, scan, fax, mixed and image), and one more of the native copy
# without gentrex select. VERSION names the benchmark version (v1), COPIES
# the copies to read, SPLIT the split (dev), and NO_SELECT the copies to read
# once more without gentrex select (native, and NO_SELECT= for none).
# Options after the script's name go to every run of run.py. With --no-hpo,
# the runs need neither the HPO index nor the packages that build it.
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSION="${VERSION:-v1}"
settings=evaluation/settings.yaml

evaluation/download_reference_files.sh
hpo="--extra hpo"
case " $* " in
  *" --no-hpo "*)
    hpo="" ;;
  *)
    index=$(uv run python -c "
import pathlib
from gentrex import config
print(config.load_settings(pathlib.Path('$settings'))['normalize']['hpo']['path'])")
    if [ ! -f "$index" ]; then
      uv run --extra hpo python scripts/build_hpo_index.py \
        --settings "$settings" data/ontology/hp-base.json
    fi ;;
esac

status=0
options=("$@")
run() {
  # --gpus names the GPUs that serve.sh gives each model: one for the models
  # of gentrex transcribe and gentrex select, and two for gentrex extract.
  uv run $hpo python gentrex-bench/run.py \
    --version "$VERSION" --split "${SPLIT:-dev}" \
    --gpus 1 1 2 --serve evaluation/local/serve.sh --settings "$settings" \
    ${options[@]+"${options[@]}"} "$@" || status=1
}
for copy in ${COPIES:-native scan fax mixed image}; do
  run --copy "$copy"
done
case " $* " in
  *" --no-select "*) ;;
  *) for copy in ${NO_SELECT-native}; do run --copy "$copy" --no-select; done ;;
esac
exit $status
