#!/bin/bash
# Submit the runs of run_pipeline.lsf as one short 1-GPU Minerva job each.
#
#   SERVING=/path/to/serving evaluation/minerva/submit_pipeline.sh [bsub options]
#
# LSF starts short 1-GPU jobs sooner than one 8-hour job, and separate jobs
# can run at the same time on different GPUs. The six jobs make the runs
# that run_pipeline.lsf makes in one job: the native PDFs three times, the
# first also with --select-methods, the scan and fax copies, and the native
# PDFs without gentrex select. Each job asks for one H100 GPU and two hours (three hours for the one with
# --select-methods). Options after the script's name go to every bsub, such
# as -P acc_xxx. VERSION and OPTIONS reach the jobs as they reach
# run_pipeline.lsf.
set -euo pipefail
: "${SERVING:?set SERVING to the serving folder}"
[ -f gentrex-bench/run.py ] || { echo "run it from the gentrex folder"; exit 1; }

submit() {
  local hours=$1
  shift
  env "$@" REPEATS=1 NO_SELECT= bsub -W "$hours" -gpu "num=1" \
    ${options[@]+"${options[@]}"} < evaluation/minerva/run_pipeline.lsf
}
options=("$@")
submit 3:00 COPIES=native SELECT_METHODS=native
submit 2:00 COPIES=native SELECT_METHODS=
submit 2:00 COPIES=native SELECT_METHODS=
submit 2:00 COPIES=scan SELECT_METHODS=
submit 2:00 COPIES=fax SELECT_METHODS=
submit 2:00 COPIES=native SELECT_METHODS= OPTIONS="${OPTIONS:-} --no-select"
