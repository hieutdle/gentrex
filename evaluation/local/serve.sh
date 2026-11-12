#!/bin/bash
# Start vLLM with one model on this machine, and serve it until stopped.
#
#   evaluation/local/serve.sh <model> <port>
#
# run_pipeline.sh and generate_reports.sh start each model they need with
# this script and stop it afterwards. The options are those of each
# command's page in docs/user-guide/. Change them here if your GPUs differ,
# and add a model that you want to try.
case "$1" in
  lightonai/LightOnOCR-3-4B)
    options=(--max-model-len 18000
      --default-chat-template-kwargs '{"enable_thinking": false}') ;;
  google/gemma-4-26B-A4B-it)
    options=(--max-model-len 16384) ;;
  google/gemma-4-31B-it)
    # For two GPUs with 80 GB each. On one GPU with more memory, such as a
    # B200, remove --tensor-parallel-size 2.
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

exec vllm serve "$1" --port "$2" "${options[@]}"
