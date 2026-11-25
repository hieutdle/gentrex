#!/bin/bash
# Submit the runs of run_pipeline.lsf as one short Minerva job each.
#
#   SERVING=/path/to/serving evaluation/minerva/submit_pipeline.sh [bsub options]
#
# LSF starts short jobs sooner than one long one, and the jobs can run at the
# same time. The seven jobs make the runs that run_pipeline.lsf makes in one
# job: the native PDFs three times, the first also with --select-methods, the
# scan and fax copies, and the native PDFs without gentrex select. The seventh
# job reads the native PDFs with Gemma 4 26B-A4B as the extraction model
# (evaluation/settings-extract-26b.yaml), on one GPU. Each job asks for two
# hours, and the one with --select-methods for three.
# Options after the script's name go to every bsub, such as -P acc_xxx.
# VERSION and OPTIONS reach the jobs as they reach run_pipeline.lsf.
set -euo pipefail
: "${SERVING:?set SERVING to the serving folder}"
[ -f gentrex-bench/run.py ] || { echo "run it from the gentrex folder"; exit 1; }

submit() {
  local hours=$1 gpus=$2
  shift 2
  env "$@" REPEATS=1 NO_SELECT= EXTRACT_26B= bsub -W "$hours" -gpu "num=$gpus" \
    ${options[@]+"${options[@]}"} < evaluation/minerva/run_pipeline.lsf
}
options=("$@")
submit 3:00 2 COPIES=native SELECT_METHODS=native
submit 2:00 2 COPIES=native SELECT_METHODS=
submit 2:00 2 COPIES=native SELECT_METHODS=
submit 2:00 2 COPIES=scan SELECT_METHODS=
submit 2:00 2 COPIES=fax SELECT_METHODS=
submit 2:00 2 COPIES=native SELECT_METHODS= OPTIONS="${OPTIONS:-} --no-select"
# Later options of run.py replace the earlier ones of run_pipeline.lsf.
submit 2:00 1 COPIES=native SELECT_METHODS= OPTIONS="${OPTIONS:-} --settings \
evaluation/settings-extract-26b.yaml --gpus 1 1 1 --label extract-26B-A4B"
