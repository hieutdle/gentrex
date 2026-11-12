#!/bin/bash
# Start vLLM with one model in a Minerva job, and serve it until stopped.
#
#   evaluation/minerva/serve.sh <model> <port>
#
# run_pipeline.lsf and generate_reports.lsf start each model they need with
# this script and stop it afterwards. SERVING is the serving folder, which
# holds vllm.sif and the models (docs/minerva/minerva.md, "Pull vLLM"). The
# options are those of the job scripts in docs/minerva/minerva.md.
: "${SERVING:?set SERVING to the serving folder}"

case "$1" in
  lightonai/LightOnOCR-3-4B)
    options=(--max-model-len 18000
      --default-chat-template-kwargs '{"enable_thinking": false}'
      --limit-mm-per-prompt '{"image": 1}'
      --mm-processor-cache-gb 0 --no-enable-prefix-caching) ;;
  google/gemma-4-26B-A4B-it)
    options=(--max-model-len 16384) ;;
  google/gemma-4-31B-it)
    # For two GPUs with 80 GB each. On one B200, remove
    # --tensor-parallel-size 2.
    options=(--tensor-parallel-size 2 --max-model-len 32768
      --gpu-memory-utilization 0.95) ;;
  meta-models/Muse-Glimmer-30B)
    # The model that writes the benchmark reports. The parser keeps its
    # reasoning out of the answer, and needs vLLM 0.28 or newer.
    options=(--max-model-len 20480 --reasoning-parser muse_glimmer) ;;
  *)
    echo "serve.sh has no options for $1" >&2
    exit 1 ;;
esac

mkdir -p "$SERVING/home"
# ${1##*/} is the model's name without its owner, which is its folder.
exec apptainer exec --nv --home "$SERVING/home" --env HF_HUB_OFFLINE=1 \
  -B "$SERVING/models:/models" "$SERVING/vllm.sif" \
  vllm serve "/models/${1##*/}" --served-model-name "$1" --port "$2" \
  "${options[@]}"
