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
# VERSION names the benchmark version (v1 by default), COPIES the copies of
# the reports to read one after another (native), and SPLIT the split (dev).
# Options after the script's name go to run.py. With --no-hpo, the run needs
# neither the HPO index nor the packages that build it.
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
for copy in ${COPIES:-native}; do
  # --gpus names the GPUs that serve.sh gives each model: one for the models
  # of gentrex transcribe and gentrex select, and two for gentrex extract.
  uv run $hpo python gentrex-bench/run.py \
    --version "$VERSION" --copy "$copy" --split "${SPLIT:-dev}" \
    --gpus 1 1 2 --serve evaluation/local/serve.sh --settings "$settings" \
    "$@" || status=1
done
exit $status
